# app/bot/handlers/suggestion_feedback_handlers.py
"""
AI Gate for Artificial Intelligence Applications
Suggestion and Feedback Handlers Module for Institution Bot

This module provides handler functions for the suggestion/feedback flow within
the unified conversation system. It includes an entry point function and 
processing handlers for collecting and confirming user suggestions.

The module is designed to work as part of the main conversation handler and
does not manage its own conversation state.

Refactored to use Pydantic AppConfig model with attribute-style access
instead of dictionary-style configuration access.
"""

import logging
from typing import Optional

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes,
    ConversationHandler
)

from app.bot.institution_bot_logic import InstitutionBot, ComplaintData
from app.bot import states
from app.bot.utils import (
    get_message,
    get_user_preferred_language_is_arabic,
    get_final_submission_inline_keyboard
)

logger = logging.getLogger(__name__)

# --- Helper functions ---

def _get_suggestion_data(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> ComplaintData:
    """
    Retrieves or initializes ComplaintData for suggestions/feedback.
    Uses context.user_data as the sole source of truth for state management.
    
    Args:
        context: The conversation context containing user_data
        user_id: The ID of the current user
        
    Returns:
        ComplaintData: The initialized or existing complaint data object
    """
    if 'complaint_data' not in context.user_data:
        logger.info(f"Initializing new suggestion data for user {user_id}")
        context.user_data['complaint_data'] = ComplaintData(user_id=user_id)
    
    if not isinstance(context.user_data['complaint_data'], ComplaintData):
        logger.error(f"Invalid data type for user {user_id}, reinitializing")
        context.user_data['complaint_data'] = ComplaintData(user_id=user_id)

    return context.user_data['complaint_data']

async def _send_or_edit(update: Update, text: str, reply_markup=None):
    """
    Helper function to send or edit messages based on update type.
    
    Args:
        update: The incoming update object
        text: The message text to send or edit
        reply_markup: Optional reply markup for the message
    """
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
        elif update.message:
            await update.message.reply_text(text=text, reply_markup=reply_markup)
        elif update.effective_chat:
            await update.effective_chat.send_message(text=text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in _send_or_edit: {e}")

# --- Entry Point Function ---

async def prompt_enter_suggestion_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point function for the suggestion/feedback flow.
    
    This function initiates the suggestion collection process by prompting the user
    to enter their suggestion or feedback text. It serves as the explicit starting
    point for this conversation flow within the unified conversation handler.
    
    Args:
        update: The incoming update that triggered this flow
        context: The conversation context containing bot instance and user data
        
    Returns:
        int: states.COLLECTING_SUGGESTION_TEXT to transition to the next conversation state
    """
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    
    user = update.effective_user
    if not user:
        logger.error("No user in prompt_enter_suggestion_text")
        return ConversationHandler.END

    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    
    try:
        # Initialize suggestion data for this user
        _get_suggestion_data(context, user.id)
        
        # Send prompt message asking user to enter their suggestion
        prompt_message = get_message('prompt_enter_suggestion_text', bot_instance, is_arabic)
        await _send_or_edit(update, prompt_message)
        
        return states.COLLECTING_SUGGESTION_TEXT
        
    except Exception as e:
        logger.error(f"Error prompting for suggestion text for user {user.id}: {e}")
        error_message = get_message('error_generic', bot_instance, is_arabic)
        await _send_or_edit(update, error_message)
        return ConversationHandler.END

# --- State Handler Functions ---

async def process_suggestion_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Processes the user's suggestion/feedback text input.
    State: states.COLLECTING_SUGGESTION_TEXT
    
    Validates the input against minimum length requirements defined in the
    AppConfig model and stores the suggestion data for confirmation.
    
    Args:
        update: The incoming update containing the user's message
        context: The conversation context containing bot instance and user data
        
    Returns:
        int: The next conversation state (CONFIRM_SUGGESTION_SUBMISSION) or END
    """
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    
    user = update.effective_user
    if not user:
        logger.error("No user in process_suggestion_text")
        return ConversationHandler.END

    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    suggestion_data = _get_suggestion_data(context, user.id)

    try:
        # Retrieve and validate user input
        suggestion_text = update.message.text.strip()
        
        # Get minimum length requirement from AppConfig using attribute access
        min_length = bot_instance.config.application_settings.validation.min_suggestion_length
        
        # Implement validation logic
        if len(suggestion_text) < min_length:
            error_message = get_message('input_too_short', bot_instance, is_arabic)
            await update.message.reply_text(error_message)
            return states.COLLECTING_SUGGESTION_TEXT
        
        # Store user input and metadata
        suggestion_data.original_complaint_text = suggestion_text
        suggestion_data.is_critical = False
        suggestion_data.telegram_message_date = update.message.date

        # Get preview length from AppConfig using attribute access
        preview_length = bot_instance.config.application_settings.flow_control.summary_preview_length

        # Prepare confirmation message with truncated preview
        confirmation_text = get_message(
            'confirm_suggestion_text',
            bot_instance,
            is_arabic,
            suggestion_text=suggestion_data.original_complaint_text[:preview_length] + 
            ("..." if len(suggestion_data.original_complaint_text) > preview_length else "")
        )
        reply_markup = get_final_submission_inline_keyboard(bot_instance, is_arabic)

        await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
        return states.CONFIRM_SUGGESTION_SUBMISSION

    except Exception as e:
        logger.error(f"Error processing suggestion for user {user.id}: {e}")
        await update.message.reply_text(get_message('error_generic', bot_instance, is_arabic))
        return ConversationHandler.END

async def handle_suggestion_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles confirmation/cancellation of suggestion submission.
    State: states.CONFIRM_SUGGESTION_SUBMISSION
    
    Processes the user's decision to confirm or cancel their suggestion submission.
    On confirmation, logs the complaint through the bot instance and provides
    appropriate feedback messages.
    
    Args:
        update: The incoming callback query update
        context: The conversation context containing bot instance and user data
        
    Returns:
        int: ConversationHandler.END (conversation completed)
    """
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    
    query = update.callback_query
    if not query:
        return ConversationHandler.END
        
    await query.answer()
    user = update.effective_user
    if not user:
        return ConversationHandler.END

    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    suggestion_data = _get_suggestion_data(context, user.id)
    action = query.data.split(":")[1]  # Extract "confirm" or "cancel" from callback data

    try:
        if action == "confirm":
            # Attempt to log the suggestion through the bot instance
            success = await bot_instance._log_complaint(suggestion_data)
            if success:
                message = get_message('suggestion_submitted_successfully', bot_instance, is_arabic)
            else:
                message = get_message('error_submission_failed', bot_instance, is_arabic)
        else:
            # User cancelled the submission
            message = get_message('suggestion_submission_cancelled', bot_instance, is_arabic)

        await query.edit_message_text(message)

        # Cleanup user data to prevent memory leaks and state conflicts
        context.user_data.pop('complaint_data', None)

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in confirmation for user {user.id}: {e}")
        await query.edit_message_text(get_message('error_generic', bot_instance, is_arabic))
        return ConversationHandler.END