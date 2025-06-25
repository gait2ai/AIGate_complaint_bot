"""
AI Gate for Artificial Intelligence Applications
app.bot.handlers package initialization and handler registration.

This module serves as the central hub for importing and registering all Telegram bot handlers
(Commands, Conversations, Messages, Callbacks, Errors) with the main Application object.
It promotes modularity by organizing handler logic into separate modules while providing
a single entry point for registration.
"""

from typing import TYPE_CHECKING
from telegram.ext import Application, MessageHandler, filters
import logging

if TYPE_CHECKING:
    from app.bot.institution_bot_logic import InstitutionBot

# Import handler registration functions from individual modules
from .main_conversation_handler import get_main_conversation_handler
from .admin_handlers import get_admin_conversation_handler
from .common_command_handlers import register_common_commands
from .error_handlers import global_error_handler
from .entry_point_handlers import handle_initial_text_message

logger = logging.getLogger(__name__)

def register_all_handlers(application: Application, bot_instance: 'InstitutionBot') -> None:
    """
    Register all bot handlers with the Telegram Application.

    This function:
    1. Stores the bot instance in application context
    2. Registers the main unified conversation handler
    3. Registers the standalone initial text handler with low priority
    4. Registers the admin conversation handler
    5. Registers common commands
    6. Sets up error handling

    Args:
        application: The Telegram Bot Application instance
        bot_instance: The InstitutionBot instance containing business logic
    """
    # Store bot_instance in application context for access in handlers
    application.bot_data['bot_instance'] = bot_instance

    # Register the main unified conversation handler
    main_conv = get_main_conversation_handler()
    application.add_handler(main_conv, group=0)
    logger.info("Main unified conversation handler registered.")

    # Register the initial text handler with a lower priority
    initial_text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_initial_text_message)
    application.add_handler(initial_text_handler, group=10)
    logger.info("Standalone initial text handler registered with low priority.")

    # Register the admin conversation handler
    admin_conv = get_admin_conversation_handler()
    application.add_handler(admin_conv, group=1)  # Using a distinct group for admin handlers

    # Register common commands (handlers now retrieve bot_instance from context)
    register_common_commands(application)

    # Register global error handler
    application.add_error_handler(global_error_handler)

    logger.info("All bot handlers have been successfully registered")