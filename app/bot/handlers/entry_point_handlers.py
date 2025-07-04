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
- Removed start_command function as it's now handled by common_command_handlers.py
- Simplified AI workflow - removed "fast path" logic
- Standardized conversation start for all complaint flows
- Updated initial intent handling to support standardized signals (COMPLAINT_START, SUGGESTION_START, GENERAL_INQUIRY, IRRELEVANT)
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


async def handle_initial_text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> Optional[int]:
    """
    Handle initial text messages from users and route them appropriately.
    
    This function processes text messages from users who interact directly
    without using the /start command. It uses LLM analysis to determine
    user intent and directly transitions to the appropriate conversation flow.
    
    The function now follows a simplified workflow where all complaint-related
    messages are routed to the first step of the complaint process, removing
    the deprecated "fast path" logic.
    """
    try:
        # Safety check: Exit immediately if a conversation is already in progress
        if context.user_data.get('conversation_state') is not None:
            return None 
        
        bot_instance: InstitutionBot = context.bot_data['bot_instance']
        user = update.effective_user
        message_text = update.message.text

        if not user or not message_text:
            logger.error("Missing user or message text in initial text handler", exc_info=True)
            return ConversationHandler.END

        await bot_instance.ensure_beneficiary_record(user.id, user.first_name)
        is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)

        # Analyze user intent using LLM - simplified response with only signal and response_text
        signal, response_text = await bot_instance.analyze_first_contact_message(
            message_text, user.first_name
        )

        logger.info(f"LLM analysis result for user {user.id}: signal={signal}")

        if signal == "COMPLAINT_START":
            # Simplified complaint flow - always start from the beginning
            await update.message.reply_text(response_text)
            
            # Initialize basic complaint data without detailed information
            complaint_data = ComplaintData(user_id=user.id)
            context.user_data['complaint_data'] = complaint_data

            logger.info(f"LLM detected complaint start for user {user.id} - routing to first step")
            
            # Direct transition to the first step of complaint flow
            from app.bot.handlers.complaint_flow_handlers import ask_new_or_reminder
            return await ask_new_or_reminder(update, context)

        elif signal == "SUGGESTION_START":
            await update.message.reply_text(response_text)

            # Initialize basic complaint data for suggestion flow
            complaint_data = ComplaintData(user_id=user.id)
            context.user_data['complaint_data'] = complaint_data

            logger.info(f"LLM detected suggestion start for user {user.id}")
            
            # Direct transition to suggestion flow
            from app.bot.handlers.suggestion_feedback_handlers import prompt_enter_suggestion_text
            return await prompt_enter_suggestion_text(update, context)

        elif signal == "GENERAL_INQUIRY":
            # Handle greetings and general questions
            await update.message.reply_text(response_text)
            # Display main action buttons to guide the user
            reply_markup = get_initial_action_buttons_keyboard(bot_instance, is_arabic)
            follow_up_message = get_message('how_can_i_help_today', bot_instance, is_arabic)
            await update.message.reply_text(follow_up_message, reply_markup=reply_markup)
            return SELECTING_INITIAL_ACTION

        elif signal == "IRRELEVANT":
            # Handle nonsensical or unrelated messages
            await update.message.reply_text(response_text)
            return ConversationHandler.END

        else:
            # Fallback for unexpected or unhandled signals
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

        # Initialize basic complaint data for all flows
        complaint_data = ComplaintData(user_id=user.id)
        context.user_data['complaint_data'] = complaint_data

        if action == "complaint":
            # Direct transition to complaint flow - always start from the beginning
            from app.bot.handlers.complaint_flow_handlers import ask_new_or_reminder
            return await ask_new_or_reminder(update, context)
            
        elif action in ["suggestion", "feedback"]:
            # Direct transition to suggestion/feedback flow
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