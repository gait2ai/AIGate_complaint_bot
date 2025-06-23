"""
AI Gate for Artificial Intelligence Applications
Unified Conversation Handler Module for the Institution Complaint Bot

This module defines the primary ConversationHandler for the bot. It consolidates
the entry points (e.g., /start, initial text), the complaint submission flow,
and the suggestion/feedback flow into a single, cohesive state machine.

Core Philosophy:
- A single entry point for all user-initiated conversation flows.
- Centralized state management for easier debugging and maintenance.
- Clear separation from administrative handlers.
- Leverages shared states and utilities for consistency.
"""

from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

# Import all state constants
from app.bot.states import (
    SELECTING_INITIAL_ACTION,
    ASK_NEW_OR_REMINDER,
    CONFIRM_EXISTING_PROFILE,
    COLLECTING_NAME,
    COLLECTING_PHONE,
    COLLECTING_EMAIL,
    COLLECTING_DEPARTMENT,
    COLLECTING_POSITION,
    COLLECTING_COMPLAINT_TYPE,
    CHOOSING_COMPLAINT_TEXT,
    COLLECTING_COMPLAINT_TEXT,
    CONFIRM_SUBMISSION,
    CRITICAL_COLLECTING_NAME,
    CRITICAL_COLLECTING_PHONE,
    CRITICAL_COLLECTING_EMAIL,
    CRITICAL_COLLECTING_DEPARTMENT,
    CRITICAL_COLLECTING_POSITION,
    CRITICAL_COLLECTING_COMPLAINT_TYPE,
    CRITICAL_CHOOSING_COMPLAINT_TEXT,
    CRITICAL_COLLECTING_COMPLAINT_TEXT,
    CRITICAL_CONFIRM_SUBMISSION,
    COLLECTING_SUGGESTION_TEXT,
    CONFIRM_SUGGESTION_SUBMISSION
)

# Import entry point handlers
from app.bot.handlers.entry_point_handlers import (
    start_command,
    handle_initial_text_message,
    handle_initial_action_selection
)

# Import complaint flow handlers
from app.bot.handlers.complaint_flow_handlers import (
    handle_new_or_reminder_choice,
    handle_profile_confirmation,
    process_name,
    process_phone,
    process_email,
    process_department,
    process_position,
    process_complaint_type,
    handle_complaint_text_choice,
    process_complaint_text,
    handle_submission_confirmation,
    process_critical_name,
    process_critical_phone,
    process_critical_email,
    process_critical_department,
    process_critical_position,
    process_critical_complaint_type,
    handle_critical_complaint_text_choice,
    process_critical_complaint_text,
    handle_critical_submission_confirmation
)

# Import suggestion/feedback handlers
from app.bot.handlers.suggestion_feedback_handlers import (
    process_suggestion_text,
    handle_suggestion_confirmation
)

# Import common command handlers
from app.bot.handlers.common_command_handlers import cancel_conversation


def get_main_conversation_handler():
    """
    Creates and returns the main ConversationHandler that unifies all primary
    user interaction flows into a single, cohesive state machine.
    
    Returns:
        ConversationHandler: The configured main conversation handler
    """
    
    return ConversationHandler(
        entry_points=[
            # Only explicit conversation starters should be entry points
            CommandHandler('start', start_command)
        ],
        
        states={
            # Initial Action State
            SELECTING_INITIAL_ACTION: [
                CallbackQueryHandler(handle_initial_action_selection, pattern=r'^initial_action:')
            ],
            
            # Complaint Flow States
            ASK_NEW_OR_REMINDER: [
                CallbackQueryHandler(handle_new_or_reminder_choice, pattern=r'^complaint_flow:')
            ],
            
            CONFIRM_EXISTING_PROFILE: [
                CallbackQueryHandler(handle_profile_confirmation, pattern=r'^profile_confirm:')
            ],
            
            # Profile Collection States
            COLLECTING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_name)
            ],
            
            COLLECTING_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_phone)
            ],
            
            COLLECTING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_email)
            ],
            
            COLLECTING_DEPARTMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_department)
            ],
            
            COLLECTING_POSITION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_position)
            ],
            
            COLLECTING_COMPLAINT_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_complaint_type)
            ],
            
            # Complaint Text States
            CHOOSING_COMPLAINT_TEXT: [
                CallbackQueryHandler(handle_complaint_text_choice, pattern=r'^complaint_text:')
            ],
            
            COLLECTING_COMPLAINT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_complaint_text)
            ],
            
            CONFIRM_SUBMISSION: [
                CallbackQueryHandler(handle_submission_confirmation, pattern=r'^submission:')
            ],
            
            # Critical States (for users who need to complete missing information)
            CRITICAL_COLLECTING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_critical_name)
            ],
            
            CRITICAL_COLLECTING_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_critical_phone)
            ],
            
            CRITICAL_COLLECTING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_critical_email)
            ],
            
            CRITICAL_COLLECTING_DEPARTMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_critical_department)
            ],
            
            CRITICAL_COLLECTING_POSITION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_critical_position)
            ],
            
            CRITICAL_COLLECTING_COMPLAINT_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_critical_complaint_type)
            ],
            
            CRITICAL_CHOOSING_COMPLAINT_TEXT: [
                CallbackQueryHandler(handle_critical_complaint_text_choice, pattern=r'^critical_complaint_text:')
            ],
            
            CRITICAL_COLLECTING_COMPLAINT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_critical_complaint_text)
            ],
            
            CRITICAL_CONFIRM_SUBMISSION: [
                CallbackQueryHandler(handle_critical_submission_confirmation, pattern=r'^critical_submission:')
            ],
            
            # Suggestion/Feedback Flow States
            COLLECTING_SUGGESTION_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_suggestion_text)
            ],
            
            CONFIRM_SUGGESTION_SUBMISSION: [
                CallbackQueryHandler(handle_suggestion_confirmation, pattern=r'^suggestion:')
            ]
        },
        
        fallbacks=[
            # Handle conversation cancellation
            CommandHandler('cancel', cancel_conversation),
            # Handle users who send text messages without starting with /start
            # This will only trigger if user is NOT currently in an active conversation
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_initial_text_message)
        ],
        
        name="main_user_conversation",
        persistent=True,
        allow_reentry=True,
        per_message=False  # Prevents tracking every message, reduces state conflicts
    )