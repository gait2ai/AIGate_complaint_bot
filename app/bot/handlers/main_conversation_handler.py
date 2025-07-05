"""
AI Gate for Artificial Intelligence Applications
Unified Conversation Handler Module for the Institution Complaint Bot

This module defines the primary ConversationHandler for the bot using the Gateway State Pattern.
It implements a robust ROUTING state that acts as a secure gateway for all new text-based
interactions, preventing conversation hijacking and ensuring clear state transitions.

Core Philosophy:
- Gateway State Pattern prevents premature re-triggering of conversations
- Single, simple entry point that immediately transitions to ROUTING state
- Clear separation between conversation initiation and stateful processing
- Stateful flag (in_conversation) as fail-safe against re-entry
- Explicit state transitions ensure predictable conversation flow
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# Import all state constants including the new ROUTING state
from app.bot.states import (
    ROUTING,
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

# Import flow handlers (excluding the removed entry_point_handlers)
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

# Import AI analysis utilities (previously in entry_point_handlers)
from app.bot.utils.ai_analysis import analyze_user_intent

logger = logging.getLogger(__name__)


async def text_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Simple entry point handler that immediately transitions to ROUTING state.
    
    This function serves as the gateway for all text-based conversation initiation.
    It performs minimal logic and immediately transitions to the ROUTING state
    where the actual intent analysis occurs safely within an established state.
    
    Args:
        update: The Telegram update object
        context: The callback context
        
    Returns:
        int: ROUTING state constant
    """
    # Check fail-safe flag to prevent re-entry during active conversations
    if context.user_data.get('in_conversation', False):
        logger.warning(f"User {update.effective_user.id} attempted to re-enter conversation")
        await update.message.reply_text(
            "⚠️ لديك محادثة نشطة بالفعل. يرجى إكمالها أو استخدام /cancel لإلغائها."
        )
        return ConversationHandler.END
    
    # Store the initial message for processing in ROUTING state
    context.user_data['initial_message'] = update.message.text
    
    logger.info(f"User {update.effective_user.id} initiated conversation with: {update.message.text[:50]}...")
    
    # Transition to ROUTING state for secure intent analysis
    return ROUTING


async def route_initial_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handler for the ROUTING state that performs AI analysis and intent determination.
    
    This function contains the LLM analysis logic that was previously in entry_point_handlers.
    It safely processes the user's initial message within an established conversation state,
    determines their intent, and transitions to the appropriate next state.
    
    Args:
        update: The Telegram update object
        context: The callback context
        
    Returns:
        int: SELECTING_INITIAL_ACTION state constant
    """
    try:
        # Get the initial message stored during entry
        initial_message = context.user_data.get('initial_message', '')
        
        if not initial_message:
            await update.message.reply_text(
                "⚠️ حدث خطأ في معالجة رسالتك. يرجى المحاولة مرة أخرى."
            )
            return ConversationHandler.END
        
        # Perform AI analysis to determine user intent
        intent_result = await analyze_user_intent(initial_message)
        
        # Store analysis result for later use
        context.user_data['intent_analysis'] = intent_result
        
        # Prepare welcome message based on intent
        if intent_result.get('intent') == 'complaint':
            welcome_text = (
                "🏛️ مرحباً بك في نظام الشكاوى المؤسسية\n\n"
                "يبدو أنك تريد تقديم شكوى. يمكنني مساعدتك في ذلك.\n"
                "اختر الإجراء المناسب:"
            )
        elif intent_result.get('intent') == 'suggestion':
            welcome_text = (
                "💡 مرحباً بك في نظام الاقتراحات\n\n"
                "يبدو أنك تريد تقديم اقتراح أو ملاحظة. يمكنني مساعدتك في ذلك.\n"
                "اختر الإجراء المناسب:"
            )
        else:
            welcome_text = (
                "🏛️ مرحباً بك في نظام الشكاوى والاقتراحات المؤسسية\n\n"
                "يمكنني مساعدتك في تقديم شكوى أو اقتراح.\n"
                "اختر الإجراء المناسب:"
            )
        
        # Create action selection keyboard
        keyboard = [
            [InlineKeyboardButton("📝 تقديم شكوى", callback_data="initial_action:complaint")],
            [InlineKeyboardButton("💡 تقديم اقتراح", callback_data="initial_action:suggestion")],
            [InlineKeyboardButton("❓ مساعدة", callback_data="initial_action:help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send welcome message with action buttons
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup
        )
        
        # Transition to action selection state
        return SELECTING_INITIAL_ACTION
        
    except Exception as e:
        logger.error(f"Error in route_initial_text: {e}")
        await update.message.reply_text(
            "⚠️ حدث خطأ في معالجة طلبك. يرجى المحاولة مرة أخرى."
        )
        return ConversationHandler.END


async def handle_initial_action_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handler for the SELECTING_INITIAL_ACTION state that processes user's callback query.
    
    This function processes the user's choice from the action selection buttons,
    sets the in_conversation flag as a fail-safe, and transitions to the appropriate
    flow based on the selected action.
    
    Args:
        update: The Telegram update object
        context: The callback context
        
    Returns:
        int: Next state constant based on selected action
    """
    query = update.callback_query
    await query.answer()
    
    try:
        # Extract action from callback data
        action = query.data.split(':')[1]
        
        # Set the fail-safe flag to prevent re-entry
        context.user_data['in_conversation'] = True
        
        # Store the selected action
        context.user_data['selected_action'] = action
        
        if action == "complaint":
            # Transition to complaint flow
            await query.edit_message_text(
                "📝 تم اختيار تقديم شكوى\n\n"
                "هل تريد تقديم شكوى جديدة أم لديك تذكير بشكوى سابقة؟"
            )
            
            # Create choice keyboard
            keyboard = [
                [InlineKeyboardButton("📝 شكوى جديدة", callback_data="complaint_flow:new")],
                [InlineKeyboardButton("🔔 تذكير بشكوى سابقة", callback_data="complaint_flow:reminder")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                "اختر نوع الطلب:",
                reply_markup=reply_markup
            )
            
            return ASK_NEW_OR_REMINDER
            
        elif action == "suggestion":
            # Transition to suggestion flow
            await query.edit_message_text(
                "💡 تم اختيار تقديم اقتراح\n\n"
                "يرجى كتابة اقتراحك أو ملاحظتك بالتفصيل:"
            )
            
            return COLLECTING_SUGGESTION_TEXT
            
        elif action == "help":
            # Provide help information
            help_text = (
                "🏛️ مرحباً بك في نظام الشكاوى والاقتراحات المؤسسية\n\n"
                "📝 **تقديم شكوى**: لتقديم شكوى رسمية حول خدمة أو مشكلة\n"
                "💡 **تقديم اقتراح**: لتقديم اقتراح أو ملاحظة لتحسين الخدمات\n\n"
                "🔧 **الأوامر المتاحة**:\n"
                "• /cancel - إلغاء المحادثة الحالية\n"
                "• /start - بدء محادثة جديدة\n\n"
                "للبدء، اكتب رسالة تصف ما تريد القيام به."
            )
            
            await query.edit_message_text(help_text)
            
            # Clear the conversation flag and end conversation
            context.user_data['in_conversation'] = False
            return ConversationHandler.END
            
        else:
            # Unknown action
            await query.edit_message_text(
                "⚠️ إجراء غير صحيح. يرجى المحاولة مرة أخرى."
            )
            context.user_data['in_conversation'] = False
            return ConversationHandler.END
            
    except Exception as e:
        logger.error(f"Error in handle_initial_action_selection: {e}")
        await query.edit_message_text(
            "⚠️ حدث خطأ في معالجة اختيارك. يرجى المحاولة مرة أخرى."
        )
        context.user_data['in_conversation'] = False
        return ConversationHandler.END


async def enhanced_cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Enhanced cancel handler that clears the in_conversation flag.
    
    This function extends the basic cancel functionality to ensure
    the fail-safe flag is properly cleared when conversation is cancelled.
    
    Args:
        update: The Telegram update object
        context: The callback context
        
    Returns:
        int: ConversationHandler.END
    """
    # Clear the fail-safe flag
    context.user_data['in_conversation'] = False
    
    # Call the original cancel handler
    return await cancel_conversation(update, context)


def get_main_conversation_handler():
    """
    Creates and returns the main ConversationHandler implementing the Gateway State Pattern.
    
    This handler creates a robust conversation flow that prevents premature re-triggering
    and conversation hijacking through:
    - Simple entry point that transitions to ROUTING state
    - Secure intent analysis within established state
    - Explicit state transitions with fail-safe flags
    - Clear separation between initiation and processing
    
    Returns:
        ConversationHandler: The configured main conversation handler with
                           Gateway State Pattern implementation
    """
    
    return ConversationHandler(
        # Entry points - single, simple entry point that transitions to ROUTING
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, text_entry_point)
        ],
        
        # States dictionary - maps each state to its corresponding handler(s)
        states={
            # ===== GATEWAY STATE =====
            ROUTING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, route_initial_text)
            ],
            
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
        
        # Fallback handlers - enhanced cancel that clears fail-safe flag
        fallbacks=[
            CommandHandler('cancel', enhanced_cancel_conversation)
        ],
        
        # Configuration parameters for robust operation
        name="main_user_conversation",
        persistent=True,          # Enables state persistence across bot restarts
        allow_reentry=True,       # Allows users to restart conversations
        per_message=False         # Prevents tracking every message, reduces state conflicts
    )


def validate_handler_completeness():
    """
    Validates that all imported states have corresponding handlers in the conversation.
    Updated to include the new ROUTING state in validation.
    
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