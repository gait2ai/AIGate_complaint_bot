"""
AI Gate for Artificial Intelligence Applications
Global Error Handlers Module for Institution Complaint Management Bot

This module provides centralized error handling for the Telegram bot, ensuring:
- Comprehensive error logging for debugging
- Graceful user notification when errors occur
- Clean state management during error conditions
- Consistent error messaging across the application

Key Features:
- Global error handler that catches all unhandled exceptions
- Detailed error logging with context information
- User-friendly error messages in appropriate language
- Safe handling of sensitive data in logs
"""

import logging
import traceback
import html
import json
from typing import Optional, Dict, Any

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes

from app.bot.institution_bot_logic import InstitutionBot
from app.bot.utils import get_message, get_user_preferred_language_is_arabic

logger = logging.getLogger(__name__)

async def global_error_handler(update: Optional[object], context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Global error handler that catches all unhandled exceptions in the bot.
    
    Args:
        update: The update that triggered the error (may be None in some cases)
        context: Callback context containing error information
    """
    try:
        # Log the error with full traceback
        logger.error("Exception while handling an update:", exc_info=context.error)
        
        # Prepare detailed error information for logging
        error_details = {
            "error_type": str(type(context.error)),
            "error_message": str(context.error),
            "update_id": getattr(update, 'update_id', None),
            "user_id": getattr(getattr(update, 'effective_user', None), 'id', None),
            "chat_id": getattr(getattr(update, 'effective_chat', None), 'id', None),
            "traceback": traceback.format_exc()
        }
        
        # Log the error details (excluding potentially sensitive user/chat data)
        logger.error("Error details: %s", json.dumps(error_details, indent=2, default=str))
        
        # Try to notify the user if possible
        await _notify_user_of_error(update, context)
        
    except Exception as inner_error:
        # If something goes wrong in the error handler itself
        logger.critical("Error in global_error_handler: %s", str(inner_error), exc_info=True)

async def _notify_user_of_error(update: Optional[object], context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Attempt to notify the user about the error in a user-friendly way.
    
    Args:
        update: The update that triggered the error
        context: Callback context
    """
    try:
        # Only proceed if we have a valid Update with a message/chat
        if not isinstance(update, Update) or not update.effective_message:
            return
            
        # Get the bot instance from application context
        bot_instance = None
        if (hasattr(context, 'application') and hasattr(context.application, 'bot_data'):
            bot_instance = context.application.bot_data.get('bot_instance')
        
        # Determine user's preferred language
        is_arabic = True  # Default to Arabic if we can't determine
        if bot_instance:
            is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
        
        # Get appropriate error message
        error_msg = "[Error message not available]"
        if bot_instance:
            try:
                error_msg = get_message('error_generic_unexpected', bot_instance, is_arabic)
            except:
                # Fallback if message retrieval fails
                error_msg = ("عذراً، حدث خطأ غير متوقع. يرجى المحاولة لاحقاً." 
                            if is_arabic else 
                            "Sorry, an unexpected error occurred. Please try again later.")
        else:
            error_msg = ("عذراً، حدث خطأ غير متوقع. يرجى المحاولة لاحقاً." 
                        if is_arabic else 
                        "Sorry, an unexpected error occurred. Please try again later.")
        
        # Send the error message to the user
        await update.effective_message.reply_text(
            error_msg,
            reply_markup=ReplyKeyboardRemove()
        )
        
    except Exception as e:
        logger.error("Failed to notify user about error: %s", str(e), exc_info=True)