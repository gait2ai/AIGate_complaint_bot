"""
AI Gate for Artificial Intelligence Applications
Entry Point Handlers Module for Institution Complaint Management Bot
"""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
    Application
)

from app.bot.institution_bot_logic import InstitutionBot, ComplaintData
from app.bot.states import (
    SELECTING_INITIAL_ACTION,
    ASK_NEW_OR_REMINDER,
    COLLECTING_SUGGESTION_TEXT
)
from app.bot.utils import (
    get_message,
    get_user_preferred_language_is_arabic,
    get_initial_action_buttons_keyboard
)

logger = logging.getLogger(__name__)


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle the /start command and initialize conversation."""
    try:
        bot_instance: InstitutionBot = context.bot_data['bot_instance']
        user = update.effective_user
        if not user:
            logger.error("No effective user found in start command")
            is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
            error_msg = get_message('error_no_user_context', bot_instance, is_arabic)
            await update.message.reply_text(error_msg)
            return ConversationHandler.END

        context.user_data.clear()
        await bot_instance.ensure_beneficiary_record(user.id, user.first_name)
        is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)

        reply_markup = get_initial_action_buttons_keyboard(bot_instance, is_arabic)
        welcome_message = get_message(
            'welcome_options',
            bot_instance,
            is_arabic,
            user_first_name=user.first_name
        )

        await update.message.reply_text(welcome_message, reply_markup=reply_markup)
        logger.info(f"Start command processed for user {user.id}")
        return SELECTING_INITIAL_ACTION

    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        bot_instance = context.bot_data['bot_instance']
        is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
        error_message = get_message('error_start_command', bot_instance, is_arabic)
        await update.message.reply_text(error_message)
        return ConversationHandler.END


async def handle_initial_text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> Optional[int]:
    """Handle initial text messages from users and route them appropriately."""
    try:
        bot_instance: InstitutionBot = context.bot_data['bot_instance']
        user = update.effective_user
        message_text = update.message.text

        if not user or not message_text:
            logger.error("Missing user or message text in initial text handler")
            return ConversationHandler.END

        await bot_instance.ensure_beneficiary_record(user.id, user.first_name)
        is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)

        signal, llm_response_text, user_facing_summary = await bot_instance.analyze_first_contact_message(
            message_text, user.first_name
        )

        logger.info(f"LLM analysis result for user {user.id}: signal={signal}")

        if signal == "GREETING_START":
            await update.message.reply_text(llm_response_text)
            reply_markup = get_initial_action_buttons_keyboard(bot_instance, is_arabic)
            follow_up_message = get_message('how_can_i_help_today', bot_instance, is_arabic)
            await update.message.reply_text(follow_up_message, reply_markup=reply_markup)
            return SELECTING_INITIAL_ACTION

        elif signal in ["OFF_TOPIC_REPLY", "CLARIFICATION_NEEDED"]:
            await update.message.reply_text(llm_response_text)
            return ConversationHandler.END

        elif signal in ["COMPLAINT_NORMAL", "COMPLAINT_CRITICAL"]:
            if user_facing_summary:
                await update.message.reply_text(user_facing_summary)

            complaint_data = ComplaintData(
                user_id=user.id,
                original_complaint_text=message_text,
                is_critical=(signal == "COMPLAINT_CRITICAL"),
                complaint_details=llm_response_text
            )
            context.user_data['complaint_data'] = complaint_data

            logger.info(f"LLM detected complaint ({'critical' if signal == 'COMPLAINT_CRITICAL' else 'normal'}) for user {user.id}")
            return ASK_NEW_OR_REMINDER

        elif signal == "SUGGESTION_RECEIVED":
            await update.message.reply_text(llm_response_text)

            complaint_data = ComplaintData(
                user_id=user.id,
                original_complaint_text=message_text,
                is_critical=False
            )
            context.user_data['complaint_data'] = complaint_data

            logger.info(f"LLM detected suggestion for user {user.id}")
            return COLLECTING_SUGGESTION_TEXT

        else:
            logger.warning(f"Unknown signal received from LLM: {signal}")
            error_message = get_message('error_unknown_intent', bot_instance, is_arabic)
            await update.message.reply_text(error_message)
            return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in handle_initial_text_message: {e}")
        bot_instance = context.bot_data['bot_instance']
        is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
        error_message = get_message('error_processing_message', bot_instance, is_arabic)
        await update.message.reply_text(error_message)
        return ConversationHandler.END


async def handle_initial_action_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> Optional[int]:
    """Handle the user's selection from the initial action buttons."""
    try:
        bot_instance: InstitutionBot = context.bot_data['bot_instance']
        query = update.callback_query
        user = query.from_user

        if not query or not user:
            logger.error("Missing query or user in callback handler")
            return ConversationHandler.END

        await query.answer()
        await query.edit_message_reply_markup(reply_markup=None)

        callback_data = query.data
        if not callback_data or not callback_data.startswith("initial_action:"):
            logger.error(f"Invalid callback data: {callback_data}")
            return ConversationHandler.END

        action = callback_data.split(":", 1)[1]
        logger.info(f"User {user.id} selected action: {action}")

        complaint_data = ComplaintData(user_id=user.id)
        context.user_data['complaint_data'] = complaint_data

        if action == "complaint":
            return ASK_NEW_OR_REMINDER
        elif action in ["suggestion", "feedback"]:
            return COLLECTING_SUGGESTION_TEXT
        else:
            logger.error(f"Unknown action: {action}")
            is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
            error_message = get_message('error_invalid_selection', bot_instance, is_arabic)
            await query.edit_message_text(error_message)
            return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in handle_initial_action_selection: {e}")
        try:
            bot_instance = context.bot_data['bot_instance']
            is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
            error_message = get_message('error_processing_selection', bot_instance, is_arabic)
            await update.callback_query.edit_message_text(error_message)
        except Exception as nested_e:
            logger.error(f"Nested error sending error message: {nested_e}")
        return ConversationHandler.END


def register_entry_handlers(application: Application) -> None:
    """Register all entry point handlers with the application."""
    try:
        # Conversation handler for the initial /start -> button-press flow
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start_command)],
            states={
                SELECTING_INITIAL_ACTION: [
                    CallbackQueryHandler(
                        handle_initial_action_selection,
                        pattern=r'^initial_action:'
                    )
                ]
            },
            fallbacks=[CommandHandler('start', start_command)],
            name="initial_choice_conversation",
            persistent=False  # This conversation is short-lived
        )
        application.add_handler(conv_handler)

        # General message handler for users who type directly instead of using /start
        # It runs in group 1 to be checked after the ConversationHandler
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                handle_initial_text_message
            ),
            group=1
        )

        logger.info("Entry point handlers registered successfully")

    except Exception as e:
        logger.error(f"Error registering handlers: {e}")
        raise