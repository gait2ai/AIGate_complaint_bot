"""
AI Gate for Artificial Intelligence Applications
Entry Point Handlers Module for Institution Complaint Management Bot

This module contains the entry point handler functions that serve as the initial
contact points for users. These functions are designed to be called directly by
the main ConversationHandler and handle seamless transitions to subsequent flows.

Key Changes:
- Removed conversation management logic (register_entry_handlers)
- Enhanced handlers to directly invoke next steps in the conversation flow
- Imports are placed inside functions to prevent circular import issues
- Maintained core functionality while enabling unified conversation flow
- Added safety check to prevent conversation hijacking
"""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

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
    """
    Handle the /start command and initialize conversation.
    
    This function serves as the primary entry point for users starting
    a conversation with the bot. It clears any existing user data,
    ensures beneficiary records exist, and presents the initial action options.
    """
    try:
        bot_instance: InstitutionBot = context.bot_data['bot_instance']
        user = update.effective_user
        
        if not user:
            logger.error("No effective user found in start command", exc_info=True)
            is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
            error_msg = get_message('error_no_user_context', bot_instance, is_arabic)
            await update.message.reply_text(error_msg)
            return ConversationHandler.END

        # Clear any existing user data to ensure fresh start
        context.user_data.clear()
        await bot_instance.ensure_beneficiary_record(user.id, user.first_name)
        is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)

        # Present initial action options to the user
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
        logger.error(f"Error in start_command: {e}", exc_info=True)
        try:
            bot_instance = context.bot_data['bot_instance']
            is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
            error_message = get_message('error_start_command', bot_instance, is_arabic)
            await update.message.reply_text(error_message)
        except Exception as nested_e:
            logger.error(f"Nested error in start_command error handling: {nested_e}", exc_info=True)
        return ConversationHandler.END


async def handle_initial_text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> Optional[int]:
    """
    Handle initial text messages from users and route them appropriately.
    
    This function processes text messages from users who interact directly
    without using the /start command. It uses LLM analysis to determine
    user intent and directly transitions to the appropriate conversation flow.
    """
    try:
        # Safety check: Exit immediately if a conversation is already in progress
        if 'complaint_data' in context.user_data:
            logger.debug(f"Active conversation detected for user {update.effective_user.id if update.effective_user else 'unknown'}, yielding control to state-specific handler")
            return None
        
        bot_instance: InstitutionBot = context.bot_data['bot_instance']
        user = update.effective_user
        message_text = update.message.text

        if not user or not message_text:
            logger.error("Missing user or message text in initial text handler", exc_info=True)
            return ConversationHandler.END

        await bot_instance.ensure_beneficiary_record(user.id, user.first_name)
        is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)

        # Analyze user intent using LLM
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
            
            # Direct transition to complaint flow - import inside function to prevent circular imports
            from app.bot.handlers.complaint_flow_handlers import ask_new_or_reminder
            return await ask_new_or_reminder(update, context)

        elif signal == "SUGGESTION_RECEIVED":
            await update.message.reply_text(llm_response_text)

            complaint_data = ComplaintData(
                user_id=user.id,
                original_complaint_text=message_text,
                is_critical=False
            )
            context.user_data['complaint_data'] = complaint_data

            logger.info(f"LLM detected suggestion for user {user.id}")
            
            # Direct transition to suggestion flow - import inside function to prevent circular imports
            from app.bot.handlers.suggestion_feedback_handlers import prompt_enter_suggestion_text
            return await prompt_enter_suggestion_text(update, context)

        else:
            logger.warning(f"Unknown signal received from LLM: {signal}")
            error_message = get_message('error_unknown_intent', bot_instance, is_arabic)
            await update.message.reply_text(error_message)
            return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in handle_initial_text_message: {e}", exc_info=True)
        try:
            bot_instance = context.bot_data['bot_instance']
            is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
            error_message = get_message('error_processing_message', bot_instance, is_arabic)
            await update.message.reply_text(error_message)
        except Exception as nested_e:
            logger.error(f"Nested error in handle_initial_text_message error handling: {nested_e}", exc_info=True)
        return ConversationHandler.END


async def handle_initial_action_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> Optional[int]:
    """
    Handle the user's selection from the initial action buttons.
    
    This function processes callback queries from the initial action buttons
    and directly transitions users to their selected flow (complaint, suggestion, 
    or feedback) without returning intermediate states.
    """
    try:
        bot_instance: InstitutionBot = context.bot_data['bot_instance']
        query = update.callback_query
        user = query.from_user

        if not query or not user:
            logger.error("Missing query or user in callback handler", exc_info=True)
            return ConversationHandler.END

        await query.answer()
        await query.edit_message_reply_markup(reply_markup=None)

        callback_data = query.data
        if not callback_data or not callback_data.startswith("initial_action:"):
            logger.error(f"Invalid callback data: {callback_data}", exc_info=True)
            return ConversationHandler.END

        action = callback_data.split(":", 1)[1]
        logger.info(f"User {user.id} selected action: {action}")

        # Initialize complaint data for all flows
        complaint_data = ComplaintData(user_id=user.id)
        context.user_data['complaint_data'] = complaint_data

        if action == "complaint":
            # Direct transition to complaint flow - import inside function to prevent circular imports
            from app.bot.handlers.complaint_flow_handlers import ask_new_or_reminder
            return await ask_new_or_reminder(update, context)
            
        elif action in ["suggestion", "feedback"]:
            # Direct transition to suggestion/feedback flow - import inside function to prevent circular imports
            from app.bot.handlers.suggestion_feedback_handlers import prompt_enter_suggestion_text
            return await prompt_enter_suggestion_text(update, context)
            
        else:
            logger.error(f"Unknown action: {action}", exc_info=True)
            is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
            error_message = get_message('error_invalid_selection', bot_instance, is_arabic)
            await query.edit_message_text(error_message)
            return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in handle_initial_action_selection: {e}", exc_info=True)
        try:
            bot_instance = context.bot_data['bot_instance']
            is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
            error_message = get_message('error_processing_selection', bot_instance, is_arabic)
            await update.callback_query.edit_message_text(error_message)
        except Exception as nested_e:
            logger.error(f"Nested error in handle_initial_action_selection error handling: {nested_e}", exc_info=True)
        return ConversationHandler.END