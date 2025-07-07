"""
AI Gate for Artificial Intelligence Applications
Common Command Handlers Module for Institution Complaint Management Bot

This module contains handler functions for standard bot commands (/start, /help, /contact)
and shared conversation cancellation logic that can be used as a fallback by
various ConversationHandlers in the application.

Key Features:
- Stateless command handlers for common bot commands
- Standalone /start command providing welcome message
- Shared conversation cancellation mechanism with enhanced state cleanup
- Consistent message localization using utils.get_message
- Clean user data cleanup on cancellation
- Type-safe configuration access using Pydantic AppConfig model
- Integration with centralized conversation state management
"""

import logging
from typing import Optional

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from app.bot.institution_bot_logic import InstitutionBot
from app.bot.utils import get_message, get_user_preferred_language_is_arabic
from app.bot.handlers.main_conversation_handler import cleanup_conversation_state

logger = logging.getLogger(__name__)


async def start_command_standalone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /start command to provide users with a welcome message.
    
    This is a standalone, stateless command handler that displays an informative
    welcome message without initiating any conversation state. It's completely
    separate from any ConversationHandler to prevent state-related conflicts.
    
    Args:
        update: Telegram Update object containing the user's message
        context: Callback context containing bot data and user context
        
    Returns:
        None (implicitly, no state constant returned)
    """
    # Retrieve bot_instance from shared application context
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    
    try:
        # Determine user's preferred language using utility function
        is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
        
        # Get the welcome message using the new configuration key
        welcome_text = get_message(
            'start_command_response', 
            bot_instance, 
            is_arabic
        )
        
        # Send the welcome message to the user
        await update.message.reply_text(welcome_text)
        
        logger.info(f"Start command processed for user {update.effective_user.id if update.effective_user else 'unknown'}")
        
    except Exception as e:
        logger.error(f"Error in start_command_standalone: {e}")
        # Fallback to simple welcome message in case of any issues
        fallback_msg = (
            "مرحباً بك! يرجى المحاولة مرة أخرى لاحقاً." 
            if get_user_preferred_language_is_arabic(update, bot_instance) 
            else "Welcome! Please try again later."
        )
        await update.message.reply_text(fallback_msg)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /help command to provide users with information about bot capabilities.
    
    This command retrieves the bot instance from the shared application context and
    provides localized help information based on the user's preferred language.
    
    Args:
        update: Telegram Update object containing the user's message
        context: Callback context containing bot data and user context
        
    Returns:
        None
    """
    # Retrieve bot_instance from shared application context
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    
    try:
        # Determine user's preferred language using utility function
        is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
        
        # Get contact info to include in help message using type-safe attribute access
        contact_info = _format_contact_info(bot_instance, is_arabic)
        
        # Get formatted help message with contact info
        help_text = get_message(
            'help_main', 
            bot_instance, 
            is_arabic,
            contact_info=contact_info
        )
        
        # Send the help message to the user
        await update.message.reply_text(help_text)
        
        logger.info(f"Help command processed for user {update.effective_user.id if update.effective_user else 'unknown'}")
        
    except Exception as e:
        logger.error(f"Error in help_command: {e}")
        # Fallback to simple error message in case of any issues
        error_msg = "Sorry, I couldn't retrieve the help information. Please try again later."
        await update.message.reply_text(error_msg)


async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /contact command to provide users with institution contact details.
    
    This command retrieves comprehensive contact information from the institution
    configuration and presents it in a localized format based on user preference.
    
    Args:
        update: Telegram Update object containing the user's message
        context: Callback context containing bot data and user context
        
    Returns:
        None
    """
    # Retrieve bot_instance from shared application context
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    
    try:
        # Determine user's preferred language using utility function
        is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
        
        # Get comprehensive contact details using type-safe attribute access
        contact_details = _format_contact_info(bot_instance, is_arabic)
        
        # Send the contact information to the user
        await update.message.reply_text(contact_details)
        
        logger.info(f"Contact command processed for user {update.effective_user.id if update.effective_user else 'unknown'}")
        
    except Exception as e:
        logger.error(f"Error in contact_command: {e}")
        # Fallback to simple error message in case of any issues
        error_msg = "Sorry, I couldn't retrieve the contact information. Please try again later."
        await update.message.reply_text(error_msg)


def _format_contact_info(bot_instance: InstitutionBot, is_arabic: bool) -> str:
    """
    Format institution contact information based on language preference.
    
    This helper function uses type-safe attribute access to retrieve contact
    information from the Pydantic AppConfig model and formats it appropriately.
    
    Args:
        bot_instance: The bot instance containing configuration
        is_arabic: Boolean indicating if Arabic language is preferred
        
    Returns:
        str: Formatted contact information string
    """
    try:
        # Access institution contact details using type-safe attribute access
        institution = bot_instance.config.institution
        contact = institution.contact
        
        if is_arabic:
            # Format Arabic contact information
            contact_info = f"""
📞 الهاتف: {contact.phone}
📧 البريد الإلكتروني: {contact.email}
📍 العنوان: {contact.address}
🌐 الموقع الإلكتروني: {institution.website}

{institution.description}
            """.strip()
        else:
            # Format English contact information
            contact_info = f"""
📞 Phone: {contact.phone}
📧 Email: {contact.email}
📍 Address: {contact.address_en}
🌐 Website: {institution.website}

Institution: {institution.name_en}
            """.strip()
        
        return contact_info
        
    except Exception as e:
        logger.error(f"Error formatting contact info: {e}")
        # Return basic fallback contact info
        return "Please contact us for assistance." if not is_arabic else "يرجى التواصل معنا للحصول على المساعدة."


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Shared conversation cancellation handler to be used as a fallback by ConversationHandlers.
    
    This function provides a centralized way to handle conversation cancellation across
    different conversation flows. It cleans up conversation data from context.user_data
    and notifies the user of the cancellation with appropriate localization.
    
    Now integrates with the centralized conversation state management system from
    main_conversation_handler for consistent state cleanup.
    
    Args:
        update: Telegram Update object containing the user's message
        context: Callback context containing bot data and user context
        
    Returns:
        int: ConversationHandler.END to terminate the conversation
    """
    # Retrieve bot_instance from shared application context
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    
    try:
        # Log the cancellation for monitoring purposes
        user_id = user.id if user else 'unknown'
        logger.info(f"Conversation cancelled by user {user_id}")
        
        # Clear conversation-specific data from context (single source of truth)
        # This ensures no stale data remains in the user's context
        context.user_data.pop('complaint_data', None)
        context.user_data.pop('suggestion_data', None)
        context.user_data.pop('feedback_data', None)
        context.user_data.pop('current_step', None)
        
        # Use centralized conversation state cleanup from main_conversation_handler
        cleanup_conversation_state(context)
        
        # Send cancellation confirmation message using localized messaging
        cancellation_msg = get_message('conversation_cancelled', bot_instance, is_arabic)
        await update.message.reply_text(
            cancellation_msg,
            reply_markup=ReplyKeyboardRemove()  # Remove any custom keyboards
        )
        
        logger.debug(f"Conversation data cleared for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error in cancel_conversation: {e}")
        # Fallback to simple cancellation message in case of any issues
        fallback_msg = "العملية ملغاة." if is_arabic else "Operation cancelled."
        await update.message.reply_text(
            fallback_msg,
            reply_markup=ReplyKeyboardRemove()
        )
        # Ensure cleanup even on error
        cleanup_conversation_state(context)
    
    return ConversationHandler.END


def register_common_commands(application) -> None:
    """
    Register common command handlers with the Telegram application.
    
    This function adds the standard command handlers (/start, /help, /contact) to the
    Telegram bot application. These commands are available globally and don't
    interfere with conversation flows.
    
    Args:
        application: PTB Application instance to register handlers with
        
    Returns:
        None
    """
    from telegram.ext import CommandHandler
    
    try:
        # Register /start command handler (standalone, stateless)
        application.add_handler(CommandHandler("start", start_command_standalone))
        logger.info("Registered /start command handler")
        
        # Register /help command handler
        application.add_handler(CommandHandler("help", help_command))
        logger.info("Registered /help command handler")
        
        # Register /contact command handler
        application.add_handler(CommandHandler("contact", contact_command))
        logger.info("Registered /contact command handler")
        
        # Note: cancel_conversation is not registered as a command here,
        # as it's meant to be used as a fallback in ConversationHandlers
        # It should be added to ConversationHandler instances using:
        # fallbacks=[CommandHandler('cancel', cancel_conversation)]
        
    except Exception as e:
        logger.error(f"Error registering common command handlers: {e}")
        raise
