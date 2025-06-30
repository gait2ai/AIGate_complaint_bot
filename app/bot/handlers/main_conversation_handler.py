"""
AI Gate for Artificial Intelligence Applications
Unified Conversation Handler Module for the Institution Complaint Bot

This module defines the primary ConversationHandler for the bot. It consolidates
all user interaction flows into a single, cohesive state machine with a unified
entry point that eliminates conversation state conflicts.

Core Philosophy:
- A single, unambiguous entry point for all user-initiated conversation flows.
- Centralized state management for easier debugging and maintenance.
- Clear separation from administrative handlers.
- Leverages shared states and utilities for consistency.
- Eliminates competing handlers and resolves infinite loop problems.
"""

from telegram.ext import (
    ConversationHandler,
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
    COLLECTING_SEX,
    COLLECTING_RESIDENCE,
    COLLECTING_GOVERNORATE,
    COLLECTING_GOVERNORATE_OTHER,
    COLLECTING_DIRECTORATE,
    COLLECTING_VILLAGE,
    COLLECTING_DEPARTMENT,
    COLLECTING_POSITION,
    COLLECTING_COMPLAINT_TYPE,
    COLLECTING_COMPLAINT_TEXT,
    CONFIRM_COMPLAINT_SUBMISSION,
    CRITICAL_COLLECTING_NAME,
    CRITICAL_COLLECTING_PHONE,
    CRITICAL_COLLECTING_COMPLAINT_TYPE,
    CRITICAL_COLLECTING_COMPLAINT_TEXT,
    CRITICAL_CONFIRM_COMPLAINT_SUBMISSION,
    COLLECTING_SUGGESTION_TEXT,
    CONFIRM_SUGGESTION_SUBMISSION
)

# Import unified entry point handler
from app.bot.handlers.entry_point_handlers import (
    handle_unified_entry_point,
    handle_initial_action_selection
)

# Import complaint flow handlers
from app.bot.handlers.complaint_flow_handlers import (
    handle_new_or_reminder_choice,
    handle_profile_confirmation,
    process_name,
    process_phone,
    process_email,
    process_sex,
    process_residence_status,
    process_governorate,
    process_governorate_other,
    process_directorate,
    process_village,
    process_department,
    process_position,
    process_complaint_type,
    process_complaint_text,
    handle_submission_confirmation,
    process_critical_name,
    process_critical_phone,
    process_critical_complaint_type,
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
    
    This handler serves as the central nervous system for the bot, managing:
    - Initial user entry and action selection via unified entry point
    - Complete complaint submission flow (regular and critical)
    - Suggestion/feedback collection flow
    - Profile management and confirmation
    
    Returns:
        ConversationHandler: The configured main conversation handler with
                           persistent state management and proper fallback handling
    """
    
    return ConversationHandler(
        # Entry points - single, unified handler that accepts all text messages
        entry_points=[
            # Unified entry point that handles both /start commands and generic text messages
            # This eliminates conversation state conflicts by providing one unambiguous entry point
            MessageHandler(filters.TEXT, handle_unified_entry_point)
        ],
        
        # States dictionary - maps each state to its corresponding handler(s)
        states={
            # ===== INITIAL ACTION SELECTION =====
            SELECTING_INITIAL_ACTION: [
                CallbackQueryHandler(handle_initial_action_selection, pattern=r'^initial_action:')
            ],
            
            # ===== COMPLAINT FLOW STATES =====
            ASK_NEW_OR_REMINDER: [
                CallbackQueryHandler(handle_new_or_reminder_choice, pattern=r'^complaint_flow:')
            ],
            
            CONFIRM_EXISTING_PROFILE: [
                CallbackQueryHandler(handle_profile_confirmation, pattern=r'^profile_confirm:')
            ],
            
            # ===== REGULAR PROFILE COLLECTION STATES =====
            COLLECTING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_name)
            ],
            
            COLLECTING_SEX: [
                CallbackQueryHandler(process_sex, pattern=r'^sex:')
            ],
            
            COLLECTING_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_phone)
            ],
            
            COLLECTING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_email)
            ],
            
            COLLECTING_RESIDENCE: [
                CallbackQueryHandler(process_residence_status, pattern=r'^residence:')
            ],
            
            COLLECTING_GOVERNORATE: [
                CallbackQueryHandler(process_governorate, pattern=r'^governorate:')
            ],
            
            COLLECTING_GOVERNORATE_OTHER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_governorate_other)
            ],
            
            COLLECTING_DIRECTORATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_directorate)
            ],
            
            COLLECTING_VILLAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_village)
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
            
            # ===== REGULAR COMPLAINT TEXT STATES =====
            COLLECTING_COMPLAINT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_complaint_text)
            ],
            
            CONFIRM_COMPLAINT_SUBMISSION: [
                CallbackQueryHandler(handle_submission_confirmation, pattern=r'^final_submission:')
            ],
            
            # ===== CRITICAL PROFILE COLLECTION STATES =====
            # These states handle users who need to complete missing information
            CRITICAL_COLLECTING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_critical_name)
            ],
            
            CRITICAL_COLLECTING_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_critical_phone)
            ],
            
            CRITICAL_COLLECTING_COMPLAINT_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_critical_complaint_type)
            ],
            
            # ===== CRITICAL COMPLAINT TEXT STATES =====
            CRITICAL_COLLECTING_COMPLAINT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_critical_complaint_text)
            ],
            
            CRITICAL_CONFIRM_COMPLAINT_SUBMISSION: [
                CallbackQueryHandler(handle_critical_submission_confirmation, pattern=r'^critical_submission:')
            ],
            
            # ===== SUGGESTION/FEEDBACK FLOW STATES =====
            COLLECTING_SUGGESTION_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_suggestion_text)
            ],
            
            CONFIRM_SUGGESTION_SUBMISSION: [
                CallbackQueryHandler(handle_suggestion_confirmation, pattern=r'^final_submission:')
            ]
        },
        
        # Fallback handlers - global actions that can terminate conversation from any state
        fallbacks=[
            # Handle conversation cancellation from any state
            CommandHandler('cancel', cancel_conversation)  # Note: This imports CommandHandler separately
        ],
        
        # Configuration parameters for robust operation
        name="main_user_conversation",
        persistent=True,          # Enables state persistence across bot restarts
        allow_reentry=True,       # Allows users to restart conversations
        per_message=False         # Prevents tracking every message, reduces state conflicts
    )


# Validation function to ensure handler completeness
def validate_handler_completeness():
    """
    Validates that all imported states have corresponding handlers in the conversation.
    This function can be used during development to ensure no states are missed.
    
    Returns:
        tuple: (is_complete: bool, missing_states: list, extra_states: list)
    """
    # Get all state constants from the states module
    from app.bot import states
    all_states = [getattr(states, attr) for attr in dir(states) 
                  if not attr.startswith('_') and isinstance(getattr(states, attr), int)]
    
    # Get the handler and extract defined states
    handler = get_main_conversation_handler()
    defined_states = set(handler.states.keys())
    
    # Compare
    all_states_set = set(all_states)
    missing_states = list(all_states_set - defined_states)
    extra_states = list(defined_states - all_states_set)
    
    is_complete = len(missing_states) == 0 and len(extra_states) == 0
    
    return is_complete, missing_states, extra_states


# Export the main function for use in the bot application
__all__ = ['get_main_conversation_handler', 'validate_handler_completeness']