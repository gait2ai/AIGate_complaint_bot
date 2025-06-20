"""
AI Gate for Artificial Intelligence Applications
app.bot.handlers package initialization and handler registration.

This module serves as the central hub for importing and registering all Telegram bot handlers
(Commands, Conversations, Messages, Callbacks, Errors) with the main Application object.
It promotes modularity by organizing handler logic into separate modules while providing
a single entry point for registration.
"""

from typing import TYPE_CHECKING
from telegram.ext import Application
import logging

if TYPE_CHECKING:
    from app.bot.institution_bot_logic import InstitutionBot

# Import handler registration functions from individual modules
from .entry_point_handlers import register_entry_handlers
from .complaint_flow_handlers import get_complaint_conversation_handler
from .suggestion_feedback_handlers import get_suggestion_feedback_handler
from .admin_handlers import get_admin_conversation_handler
from .common_command_handlers import register_common_commands
from .error_handlers import global_error_handler

logger = logging.getLogger(__name__)

def register_all_handlers(application: Application, bot_instance: 'InstitutionBot') -> None:
    """
    Register all bot handlers with the Telegram Application.

    This function:
    1. Stores the bot instance in application context
    2. Registers all conversation handlers
    3. Registers entry point handlers
    4. Registers common commands
    5. Sets up error handling

    Args:
        application: The Telegram Bot Application instance
        bot_instance: The InstitutionBot instance containing business logic
    """
    # Store bot_instance in application context for access in handlers
    application.bot_data['bot_instance'] = bot_instance

    # Register the admin conversation handler
    admin_conv = get_admin_conversation_handler()
    application.add_handler(admin_conv, group=1)  # Using a distinct group for admin handlers

    # Register conversation handlers (these still require bot_instance as they return handlers)
    complaint_conv = get_complaint_conversation_handler()
    application.add_handler(complaint_conv)

    suggestion_conv = get_suggestion_feedback_handler()
    application.add_handler(suggestion_conv)

    # Register entry point handlers (handlers now retrieve bot_instance from context)
    register_entry_handlers(application)

    # Register common commands (handlers now retrieve bot_instance from context)
    register_common_commands(application)

    # Register global error handler
    application.add_error_handler(global_error_handler)

    logger.info("All bot handlers have been successfully registered")