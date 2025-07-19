"""
AI Gate for Artificial Intelligence Applications
Unified Conversation Handler Module for the Institution Complaint Bot

This module defines the primary ConversationHandler for the bot. It consolidates
the entry points (initial text messages), the complaint submission flow,
and the suggestion/feedback flow into a single, cohesive state machine.

Core Philosophy:
- A single entry point for all user-initiated conversation flows.
- Centralized state management for easier debugging and maintenance.
- Clear separation from administrative handlers.
- Leverages shared states and utilities for consistency.
- Eliminates competing handlers and resolves infinite loop problems.
- Text-only conversation initiation for maximum clarity and robustness.

Key Features:
- Integrated entry point handlers for initial text messages and action selection
- Complete complaint submission flow (regular and critical)
- Suggestion/feedback collection flow
- Profile management and confirmation
- Enhanced handlers that directly invoke next steps in the conversation flow
- Safety checks to prevent conversation hijacking
- Standardized conversation start for all complaint flows
- Proper conversation state management to prevent re-entry during active conversations
- State-aware text routing for active conversations with direct handler calling
"""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
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
    COLLECTING_DISABILITY,
    COLLECTING_COMPLAINT_TYPE,
    COLLECTING_COMPLAINT_TEXT,
    CONFIRM_COMPLAINT_SUBMISSION,
    CRITICAL_COLLECTING_NAME,
    CRITICAL_COLLECTING_PHONE,
    CRITICAL_COLLECTING_COMPLAINT_TEXT,
    CRITICAL_CONFIRM_COMPLAINT_SUBMISSION,
    COLLECTING_SUGGESTION_TEXT,
    CONFIRM_SUGGESTION_SUBMISSION
)

# Import core bot functionality
from app.bot.institution_bot_logic import InstitutionBot, ComplaintData
from app.bot.utils import (
    get_message,
    get_user_preferred_language_is_arabic,
    get_initial_action_buttons_keyboard
)

# Import shared utilities from conversation_utils
from app.bot.handlers.conversation_utils import (
    cleanup_conversation_state,
    is_conversation_active,
    start_conversation,
    set_conversation_state,
    get_conversation_state,
    clear_conversation_state,
    ResponseTemplates
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
    process_disability,
    process_complaint_type,
    process_complaint_text,
    handle_submission_confirmation,
    process_critical_name,
    process_critical_phone,
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

logger = logging.getLogger(__name__)


# ===== ENHANCED CANCEL CONVERSATION HANDLER =====

async def enhanced_cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Enhanced cancel conversation handler with proper state cleanup.
    
    This function handles conversation cancellation from any state and ensures
    proper cleanup of conversation state to prevent future conflicts.
    """
    try:
        bot_instance = context.bot_data['bot_instance']
        is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
        
        # Clean up conversation state using shared utility
        await cleanup_conversation_state(update, context, "user_cancelled")
        
        # Clear conversation state tracking
        clear_conversation_state(context)
        
        cancel_message = get_message('conversation_cancelled', bot_instance, is_arabic)
        await update.message.reply_text(cancel_message)
        
        logger.info(f"Conversation cancelled for user {update.effective_user.id}")
        
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in enhanced_cancel_conversation: {e}", exc_info=True)
        # Ensure cleanup even on error
        await cleanup_conversation_state(update, context, "error_during_cancel")
        clear_conversation_state(context)
        return ConversationHandler.END


# ===== ENTRY POINT HANDLERS =====

async def handle_initial_text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> Optional[int]:
    """
    Handle initial text messages from users and route them appropriately.
    
    This function serves dual purposes:
    1. For new conversations: Process text messages from users who interact directly
       without using the /start command, analyze intent, and transition to appropriate flow.
    2. For active conversations: Route text messages to the appropriate state handler
       by calling the handler function directly.
    
    The function now includes direct handler calling to ensure that text messages
    during active conversations are properly handled by their respective state handlers.
    """
    try:
        # STATE-AWARE ROUTING: Check if we're in an active conversation with a tracked state
        current_state = get_conversation_state(context)
        if current_state is not None:
            logger.info(f"User {update.effective_user.id} in active conversation state {current_state} - routing directly to handler")
            
            # Create a mapping of states to their handler functions
            state_handlers = {
                COLLECTING_NAME: process_name,
                COLLECTING_PHONE: process_phone,
                COLLECTING_EMAIL: process_email,
                COLLECTING_GOVERNORATE_OTHER: process_governorate_other,
                COLLECTING_DIRECTORATE: process_directorate,
                COLLECTING_VILLAGE: process_village,
                COLLECTING_DEPARTMENT: process_department,
                COLLECTING_COMPLAINT_TYPE: process_complaint_type,
                COLLECTING_COMPLAINT_TEXT: process_complaint_text,
                CRITICAL_COLLECTING_NAME: process_critical_name,
                CRITICAL_COLLECTING_PHONE: process_critical_phone,
                CRITICAL_COLLECTING_COMPLAINT_TEXT: process_critical_complaint_text,
                COLLECTING_SUGGESTION_TEXT: process_suggestion_text,
            }
            
            # Get the handler function for the current state
            handler_func = state_handlers.get(current_state)
            if handler_func:
                logger.info(f"Calling handler function for state {current_state}")
                # Call the handler function directly and return its result
                return await handler_func(update, context)
            else:
                logger.warning(f"No handler function found for state {current_state}")
                # Clear invalid state and fall through to new conversation logic
                clear_conversation_state(context)
        
        # NEW CONVERSATION LOGIC: Handle initial conversation setup
        # Additional safety check: Check if complaint_data already exists and has been processed
        existing_complaint = context.user_data.get('complaint_data')
        if existing_complaint and hasattr(existing_complaint, 'name') and existing_complaint.name:
            logger.info(f"User {update.effective_user.id} has active complaint data - ignoring text message")
            return None
        
        bot_instance: InstitutionBot = context.bot_data['bot_instance']
        user = update.effective_user
        message_text = update.message.text

        if not user or not message_text:
            logger.error("Missing user or message text in initial text handler", exc_info=True)
            return ConversationHandler.END

        await bot_instance.ensure_beneficiary_record(user.id, user.first_name)
        is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)

        # Mark conversation as active BEFORE processing to prevent re-entry
        start_conversation(context)

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

        elif signal == "IRRELEVANT":
            # Handle greetings and general questions
            await update.message.reply_text(response_text)
            # Display main action buttons to guide the user
            reply_markup = get_initial_action_buttons_keyboard(bot_instance, is_arabic)
            follow_up_message = get_message('how_can_i_help_today', bot_instance, is_arabic)
            await update.message.reply_text(follow_up_message, reply_markup=reply_markup)
            # Clear state tracking since we're transitioning to callback-based state
            clear_conversation_state(context)
            return SELECTING_INITIAL_ACTION

        elif signal == "GENERAL_INQUIRY":
            # Handle nonsensical or unrelated messages
            await update.message.reply_text(response_text)
            try:
                # Get the localized follow-up message from utils.py
                follow_up_message = get_message(
                    'general_inquiry_follow_up', 
                    bot_instance, 
                    is_arabic
                )
                # The get_message function already populates {institution_name}, {phone}, and {email}
                
                # Send the contact information message, using MarkdownV2 for formatting
                # Note: We need to escape characters for MarkdownV2 if they are not already.
                # The `get_message` function does not do this, so we handle it here.
                # However, since we control the string, we know it's safe. Let's adjust for robustness.
                
                # To be safe, let's use the standard Markdown for this.
                # Telegram supports Markdown and MarkdownV2. The former is more forgiving.
                await update.message.reply_text(
                    text=follow_up_message.replace('`', ''), # Remove backticks if using standard markdown
                    parse_mode='Markdown'
                )
            except Exception as contact_info_error:
                logger.error(f"Failed to send contact information follow-up: {contact_info_error}", exc_info=True)
            # Clean up conversation state since we're ending
            await cleanup_conversation_state(update, context, "irrelevant_message")
            clear_conversation_state(context)
            return ConversationHandler.END

        else:
            # Fallback for unexpected or unhandled signals
            logger.warning(f"Unknown signal received from LLM: {signal}")
            error_message = get_message('error_unknown_intent', bot_instance, is_arabic)
            await update.message.reply_text(error_message)
            # Clean up conversation state since we're ending
            await cleanup_conversation_state(update, context, "unknown_signal")
            clear_conversation_state(context)
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
        # Clean up conversation state since we're ending
        await cleanup_conversation_state(update, context, "error_in_handler")
        clear_conversation_state(context)
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
    
    Enhanced with proper error handling and state management.
    """
    try:
        bot_instance: InstitutionBot = context.bot_data['bot_instance']
        query = update.callback_query
        user = query.from_user

        if not query or not user:
            logger.error("Missing query or user in callback handler", exc_info=True)
            await cleanup_conversation_state(update, context, "missing_query_or_user")
            clear_conversation_state(context)
            return ConversationHandler.END

        await query.answer()
        await query.edit_message_reply_markup(reply_markup=None)

        callback_data = query.data
        if not callback_data or not callback_data.startswith("initial_action:"):
            logger.error(f"Invalid callback data: {callback_data}", exc_info=True)
            await cleanup_conversation_state(update, context, "invalid_callback_data")
            clear_conversation_state(context)
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
            await cleanup_conversation_state(update, context, "unknown_action")
            clear_conversation_state(context)
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
        await cleanup_conversation_state(update, context, "error_in_selection_handler")
        clear_conversation_state(context)
        return ConversationHandler.END


def get_main_conversation_handler():
    """
    Creates and returns the main ConversationHandler that unifies all primary
    user interaction flows into a single, cohesive state machine.
    
    This handler serves as the central nervous system for the bot, managing:
    - Initial user entry and action selection via text messages
    - Complete complaint submission flow (regular and critical)
    - Suggestion/feedback collection flow
    - Profile management and confirmation
    - State-aware text message routing for active conversations
    
    Entry Point Philosophy:
    - Single, unambiguous entry point via text messages only
    - Complete decoupling from /start command (handled elsewhere)
    - Eliminates state conflicts and conversation stalling
    - Maximum clarity and robustness in conversation initiation
    - Proper conversation state management to prevent re-entry
    - State-aware routing with direct handler calling for active conversations
    
    Returns:
        ConversationHandler: The configured main conversation handler with
                           persistent state management and proper fallback handling
    """
    
    return ConversationHandler(
        # Entry points - single, clear entry point for conversation initiation
        entry_points=[
            # Single entry point for direct text messages (non-commands)
            # This allows users to initiate conversations with any text message
            # AND routes active conversation text messages to appropriate state handlers
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_initial_text_message)
        ],
        
        # States dictionary - maps each state to its corresponding handler(s)
        states={
            # ===== INITIAL ACTION SELECTION =====
            SELECTING_INITIAL_ACTION: [
                CallbackQueryHandler(handle_initial_action_selection, pattern=r'^initial_action:')
                # Note: No text handler here - text messages are handled by entry point
            ],
            
            # ===== COMPLAINT FLOW STATES =====
            ASK_NEW_OR_REMINDER: [
                CallbackQueryHandler(handle_new_or_reminder_choice, pattern=r'^complaint_flow:')
                # Note: No text handler here - text messages are handled by entry point
            ],
            
            CONFIRM_EXISTING_PROFILE: [
                CallbackQueryHandler(handle_profile_confirmation, pattern=r'^profile_confirm:')
                # Note: No text handler here - text messages are handled by entry point
            ],
            
            # ===== REGULAR PROFILE COLLECTION STATES =====
            COLLECTING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_name)
            ],
            
            COLLECTING_SEX: [
                CallbackQueryHandler(process_sex, pattern=r'^sex:')
                # Note: No text handler here - text messages are handled by entry point
            ],
            
            COLLECTING_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_phone)
            ],
            
            COLLECTING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_email)
            ],
            
            COLLECTING_RESIDENCE: [
                CallbackQueryHandler(process_residence_status, pattern=r'^residence:')
                # Note: No text handler here - text messages are handled by entry point
            ],
            
            COLLECTING_GOVERNORATE: [
                CallbackQueryHandler(process_governorate, pattern=r'^governorate:')
                # Note: No text handler here - text messages are handled by entry point
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
            
            COLLECTING_DISABILITY: [
                CallbackQueryHandler(process_disability, pattern=r'^disability:')
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
                # Note: No text handler here - text messages are handled by entry point
            ],
            
            # ===== CRITICAL PROFILE COLLECTION STATES =====
            # These states handle users who need to complete missing information
            CRITICAL_COLLECTING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_critical_name)
            ],
            
            CRITICAL_COLLECTING_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_critical_phone)
            ],
            
            
            # ===== CRITICAL COMPLAINT TEXT STATES =====
            CRITICAL_COLLECTING_COMPLAINT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_critical_complaint_text)
            ],
            
            CRITICAL_CONFIRM_COMPLAINT_SUBMISSION: [
                CallbackQueryHandler(handle_critical_submission_confirmation, pattern=r'^critical_submission:')
                # Note: No text handler here - text messages are handled by entry point
            ],
            
            # ===== SUGGESTION/FEEDBACK FLOW STATES =====
            COLLECTING_SUGGESTION_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_suggestion_text)
            ],
            
            CONFIRM_SUGGESTION_SUBMISSION: [
                CallbackQueryHandler(handle_suggestion_confirmation, pattern=r'^final_submission:')
                # Note: No text handler here - text messages are handled by entry point
            ]
        },
        
        # Fallback handlers - global actions that can terminate conversation from any state
        fallbacks=[
            # Handle conversation cancellation from any state with enhanced cleanup
            CommandHandler('cancel', enhanced_cancel_conversation)
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


# Export the main functions for use in the bot application
__all__ = [
    'get_main_conversation_handler', 
    'validate_handler_completeness',
    'handle_initial_text_message',
    'handle_initial_action_selection',
    'enhanced_cancel_conversation'
]