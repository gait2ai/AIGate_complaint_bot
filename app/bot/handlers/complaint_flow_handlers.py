# app/bot/handlers/complaint_flow_handlers.py
"""
AI Gate for Artificial Intelligence Applications
Complaint Flow Handlers Module for Institution Complaint Management Bot

This module provides handler functions for the complaint submission flow as part
of a unified conversation management system. It handles various stages including
the initial choice between a new complaint or a reminder for a previous one,
user profile confirmation/data collection, gathering detailed complaint information,
managing critical case diversions, and final submission confirmation.

Enhanced with:
- Robust validation for all data collection steps
- Clear state transitions controlled by states.py
- Improved critical complaint flow
- Better error handling and user feedback
- Complete data collection flow for all profile fields
- AI-powered name validation
- Final AI analysis of complaint content
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from app.bot.handlers.conversation_utils import (
    cleanup_conversation_state,
    set_conversation_state,
    clear_conversation_state,
    ResponseTemplates
)

from app.bot.institution_bot_logic import InstitutionBot, ComplaintData
from app.bot import states
from app.bot.utils import (
    get_message,
    get_user_preferred_language_is_arabic,
    get_yes_no_keyboard,
    get_sex_keyboard,
    get_new_reminder_inline_keyboard,
    get_confirm_profile_inline_keyboard,
    get_complaint_text_choice_inline_keyboard,
    get_final_submission_inline_keyboard,
    validate_phone_number,
    get_residence_status_keyboard,
    get_disability_keyboard,
    get_governorates_keyboard
)

logger = logging.getLogger(__name__)

# Email validation pattern
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# --- Helper functions ---

def _get_complaint_data(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> ComplaintData:
    """Retrieves or initializes ComplaintData for the user from context.user_data."""
    if 'complaint_data' not in context.user_data:
        logger.info(f"Initializing fresh ComplaintData for user {user_id}")
        context.user_data['complaint_data'] = ComplaintData(user_id=user_id)
    
    if not isinstance(context.user_data['complaint_data'], ComplaintData):
        logger.error(f"Data for user {user_id} is not ComplaintData. Re-initializing.")
        context.user_data['complaint_data'] = ComplaintData(user_id=user_id)

    return context.user_data['complaint_data']

async def _send_or_edit(update: Update, text: str, reply_markup=None, parse_mode=ParseMode.MARKDOWN):
    """Helper to send new message or edit existing one based on update type."""
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=text, 
                reply_markup=reply_markup, 
                parse_mode=parse_mode
            )
        elif update.message:
            await update.message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        elif update.effective_chat:
            await update.effective_chat.send_message(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
    except Exception as e:
        logger.error(f"Error in _send_or_edit: {e}", exc_info=True)

async def _ask_for_field(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    is_arabic: bool,
    prompt_key: str,
    reply_markup=ReplyKeyboardRemove(),
    from_callback: bool = False
):
    """Standardized prompt for field collection."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    message_text = get_message(prompt_key, bot_instance, is_arabic)
    
    try:
        if from_callback and update.callback_query:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        elif update.message:
            await update.message.reply_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.error(f"Error in _ask_for_field: {e}", exc_info=True)

def _has_meaningful_profile_data(profile: dict) -> bool:
    """
    Determines if a user profile contains COMPLETE and meaningful data worth confirming.
    A profile is only considered meaningful if it was created through a non-critical,
    full data collection flow.
    """
    if not profile:
        return False

    # Define the core fields that MUST exist for a profile to be considered complete.
    # These are typically collected in the standard flow, but not the critical flow.
    # We check for fields that go beyond the name/phone collected in critical complaints.
    
    required_core_fields = [
        'name',
        'phone',
        'sex',
        'residence_status',
        'governorate'
    ]
    
    return all(profile.get(field) and str(profile.get(field)).strip() for field in required_core_fields)

async def _generate_complaint_summary(bot_instance: InstitutionBot, complaint_data: ComplaintData, is_arabic: bool) -> str:
    """Generate a user-friendly summary of the complaint data for confirmation."""
    summary_parts = []
    
    if is_arabic:
        summary_parts.append("📋 ملخص الشكوى:\n")
        summary_parts.append(f"الاسم: {complaint_data.name or 'غير متوفر'}")
        summary_parts.append(f"الجنس: {complaint_data.sex or 'غير محدد'}")
        if hasattr(complaint_data, 'age') and complaint_data.age > 0:
            summary_parts.append(f"العمر: {complaint_data.age}")
        if hasattr(complaint_data, 'nationality') and complaint_data.nationality:
            summary_parts.append(f"الجنسية: {complaint_data.nationality}")
        summary_parts.append(f"الهاتف: {complaint_data.phone or 'غير متوفر'}")
        if complaint_data.email:
            summary_parts.append(f"البريد الإلكتروني: {complaint_data.email}")
        if hasattr(complaint_data, 'department') and complaint_data.department:
            summary_parts.append(f"القسم: {complaint_data.department}")
        if hasattr(complaint_data, 'disability') and complaint_data.disability:
            summary_parts.append(f"هل لديك إعاقة: {complaint_data.disability}")
        summary_parts.append(f"حالة الإقامة: {complaint_data.residence_status or 'غير محدد'}")
        summary_parts.append(f"المحافظة: {complaint_data.governorate or 'غير محدد'}")
        summary_parts.append(f"المديرية: {complaint_data.directorate or 'غير محدد'}")
        summary_parts.append(f"القرية/الحي: {complaint_data.village or 'غير محدد'}")
        if hasattr(complaint_data, 'complaint_type') and complaint_data.complaint_type:
            summary_parts.append(f"نوع الشكوى: {complaint_data.complaint_type}")
        summary_parts.append(f"\nنص الشكوى:\n{complaint_data.original_complaint_text}")
    else:
        summary_parts.append("📋 Complaint Summary:\n")
        summary_parts.append(f"Name: {complaint_data.name or 'Not provided'}")
        summary_parts.append(f"Gender: {complaint_data.sex or 'Not specified'}")
        if hasattr(complaint_data, 'age') and complaint_data.age > 0:
            summary_parts.append(f"Age: {complaint_data.age}")
        if hasattr(complaint_data, 'nationality') and complaint_data.nationality:
            summary_parts.append(f"Nationality: {complaint_data.nationality}")
        summary_parts.append(f"Phone: {complaint_data.phone or 'Not provided'}")
        if complaint_data.email:
            summary_parts.append(f"Email: {complaint_data.email}")
        if hasattr(complaint_data, 'department') and complaint_data.department:
            summary_parts.append(f"Department: {complaint_data.department}")
        if hasattr(complaint_data, 'disability') and complaint_data.disability:
            summary_parts.append(f"Has Disability: {complaint_data.disability}")
        summary_parts.append(f"Residence Status: {complaint_data.residence_status or 'Not specified'}")
        summary_parts.append(f"Governorate: {complaint_data.governorate or 'Not specified'}")
        summary_parts.append(f"Directorate: {complaint_data.directorate or 'Not specified'}")
        summary_parts.append(f"Village/Area: {complaint_data.village or 'Not specified'}")
        if hasattr(complaint_data, 'complaint_type') and complaint_data.complaint_type:
            summary_parts.append(f"Complaint Type: {complaint_data.complaint_type}")
        summary_parts.append(f"\nComplaint Text:\n{complaint_data.original_complaint_text}")
    
    return "\n".join(summary_parts)

def _get_next_step_after(bot_instance: InstitutionBot, current_step: str) -> str:
    """
    Centralized logic to determine the next step in the data collection flow.
    Follows a predefined sequence and checks which fields are enabled in config.
    
    Args:
        bot_instance: The bot instance containing configuration
        current_step: The name of the current step
        
    Returns:
        str: The name of the next step to proceed to
    """
    # Define the complete ordered sequence of possible steps
    step_sequence = [
        'name',
        'sex',
        'age',
        'nationality',
        'phone',
        'email',
        'residence_status',
        'governorate',
        'directorate',
        'village',
        'disability',
        'complaint_text'
    ]
    
    # Get the configuration for which fields are enabled
    config = bot_instance.config.application_settings.data_collection_fields
    
    try:
        # Find the current step in the sequence
        current_index = step_sequence.index(current_step)
        
        # Iterate through remaining steps to find the next enabled one
        for next_step in step_sequence[current_index + 1:]:
            # Check if this step is enabled in config
            if getattr(config, next_step, False):
                return next_step
        
        # If no enabled steps found after current one, default to complaint_text
        return 'complaint_text'
    
    except ValueError:
        logger.error(f"Unknown current_step in _get_next_step_after: {current_step}")
        return 'complaint_text'

async def _transition_to_next_step(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    current_step: str,
    is_arabic: bool,
    from_callback: bool = False
) -> int:
    """
    Centralized helper to transition to the next appropriate step in the data collection flow.
    
    Args:
        update: The Telegram Update object
        context: The callback context
        current_step: The name of the current step that was just completed
        is_arabic: Whether the user's preferred language is Arabic
        from_callback: Whether this transition originates from a callback query
        
    Returns:
        int: The next state to transition to
    """
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    
    try:
        # Get the next step based on configuration
        next_step = _get_next_step_after(bot_instance, current_step)
        
        # Map step names to their corresponding collect functions
        step_to_function = {
            'name': collect_name,
            'sex': collect_sex,
            'age': collect_age,
            'nationality': collect_nationality,
            'phone': collect_phone,
            'email': collect_email,
            'residence_status': collect_residence_status,
            'governorate': collect_governorate,
            'directorate': collect_directorate,
            'village': collect_village,
            'disability': collect_disability,
            'complaint_text': collect_complaint_text
        }
        
        # Get the appropriate function and execute it
        if next_step in step_to_function:
            return await step_to_function[next_step](update, context, is_arabic, from_callback)
        
        # Default to complaint text if no valid next step found
        return await collect_complaint_text(update, context, is_arabic, from_callback)
    
    except Exception as e:
        logger.error(f"Error in _transition_to_next_step: {e}", exc_info=True)
        await _send_or_edit(update, get_message('error_generic', bot_instance, is_arabic))
        await cleanup_conversation_state(update, context)
        return ConversationHandler.END

# Wrapper functions for backward compatibility
def _get_next_step_after_phone(bot_instance: InstitutionBot) -> str:
    """Wrapper that calls _get_next_step_after with 'phone' as current_step."""
    return _get_next_step_after(bot_instance, 'phone')

def _get_next_step_after_email(bot_instance: InstitutionBot) -> str:
    """Wrapper that calls _get_next_step_after with 'email' as current_step."""
    return _get_next_step_after(bot_instance, 'email')

def _get_next_step_after_residence_status(bot_instance: InstitutionBot) -> str:
    """Wrapper that calls _get_next_step_after with 'residence_status' as current_step."""
    return _get_next_step_after(bot_instance, 'residence_status')

def _get_next_step_after_governorate(bot_instance: InstitutionBot) -> str:
    """Wrapper that calls _get_next_step_after with 'governorate' as current_step."""
    return _get_next_step_after(bot_instance, 'governorate')

def _get_next_step_after_directorate(bot_instance: InstitutionBot) -> str:
    """Wrapper that calls _get_next_step_after with 'directorate' as current_step."""
    return _get_next_step_after(bot_instance, 'directorate')

def _get_next_step_after_village(bot_instance: InstitutionBot) -> str:
    """Wrapper that calls _get_next_step_after with 'village' as current_step."""
    return _get_next_step_after(bot_instance, 'village')

def _get_next_step_after_department(bot_instance: InstitutionBot) -> str:
    """Wrapper that calls _get_next_step_after with 'department' as current_step."""
    return _get_next_step_after(bot_instance, 'department')

# --- State Handler Functions ---

async def ask_new_or_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point for complaint flow. Decides whether to ask about new vs reminder
    or proceed directly to data collection based on user's complaint history.
    """
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    if not user:
        logger.error("ask_new_or_reminder: No effective user.")
        return ConversationHandler.END

    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)

    try:
        previous_complaints = await bot_instance.get_user_previous_complaints_summary(user.id)
        
        if not previous_complaints:
            logger.info(f"No previous complaints for user {user.id}, proceeding to profile check")
            return await _proceed_to_profile_check(update, context, is_arabic)

        reply_markup = get_new_reminder_inline_keyboard(bot_instance, is_arabic)
        message_text = get_message(
            'ask_new_or_reminder', 
            bot_instance, 
            is_arabic, 
            num_complaints=len(previous_complaints)
        )
        
        await _send_or_edit(update, message_text, reply_markup)
        return states.ASK_NEW_OR_REMINDER

    except Exception as e:
        logger.error(f"Error in ask_new_or_reminder for user {user.id}: {e}", exc_info=True)
        await _send_or_edit(update, get_message('error_generic', bot_instance, is_arabic))
        await cleanup_conversation_state(update, context)
        return ConversationHandler.END

async def handle_new_or_reminder_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles user's choice between new complaint or reminder."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    query = update.callback_query
    if not query:
        return ConversationHandler.END
        
    await query.answer()
    user = update.effective_user
    if not user:
        return ConversationHandler.END
    
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)

    try:
        action = query.data.split(":")[1]

        if action == "reminder":
            previous_complaints = await bot_instance.get_user_previous_complaints_summary(user.id)
            if not previous_complaints:
                await query.edit_message_text(get_message('reminder_no_complaints_found', bot_instance, is_arabic))
                return ConversationHandler.END

            most_recent = previous_complaints[0]
            retrieved_details = {
                "name": most_recent.get("submitter_name", get_message('data_not_available', bot_instance, is_arabic)),
                "text_snippet": most_recent.get("summary", get_message('data_not_available', bot_instance, is_arabic))[:50],
                "date": most_recent.get("date", get_message('data_not_available', bot_instance, is_arabic))
            }
            
            reminder_logged = await bot_instance.log_complaint_reminder_note(
                user_id=user.id,
                original_complaint_id=most_recent.get('id'),
                retrieved_complaint_details=retrieved_details
            )

            ack_text_key = 'reminder_acknowledged' if reminder_logged else 'reminder_log_error'
            ack_text = get_message(ack_text_key, bot_instance, is_arabic, complaint_id=most_recent.get('id'))
            await query.edit_message_text(text=ack_text)
            return ConversationHandler.END

        elif action == "new":
            await query.edit_message_text(text=get_message('new_complaint_selected', bot_instance, is_arabic))
            return await _proceed_to_profile_check(update, context, is_arabic)
            
        else:
            logger.warning(f"Unknown action in handle_new_or_reminder_choice: {query.data}")
            await query.edit_message_text(get_message('error_invalid_selection', bot_instance, is_arabic))
            return states.ASK_NEW_OR_REMINDER

    except Exception as e:
        logger.error(f"Error in handle_new_or_reminder_choice for user {user.id}: {e}", exc_info=True)
        await query.edit_message_text(get_message('error_generic', bot_instance, is_arabic))
        await cleanup_conversation_state(update, context)
        return ConversationHandler.END

async def _proceed_to_profile_check(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool) -> int:
    """
    Helper: Branches to critical flow or standard profile collection.
    Only prompts for profile confirmation if meaningful data exists.
    """
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    complaint_data = _get_complaint_data(user.id, context)

    try:
        if complaint_data.is_critical:
            return await collect_critical_name(update, context, is_arabic)

        existing_profile = await bot_instance._check_existing_beneficiary_profile(user.id)
        
        if existing_profile and _has_meaningful_profile_data(existing_profile):
            profile_summary = get_message(
                'existing_profile_summary',
                bot_instance,
                is_arabic,
                **existing_profile
            )
            reply_markup = get_confirm_profile_inline_keyboard(bot_instance, is_arabic)
            await _send_or_edit(update, profile_summary, reply_markup)
            return states.CONFIRM_EXISTING_PROFILE
        else:
            return await collect_name(update, context, is_arabic)

    except Exception as e:
        logger.error(f"Error in _proceed_to_profile_check for user {user.id}: {e}", exc_info=True)
        await _send_or_edit(update, get_message('error_generic', bot_instance, is_arabic))
        await cleanup_conversation_state(update, context)
        return ConversationHandler.END

async def handle_profile_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles Yes/No choice for using existing profile."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    query = update.callback_query
    if not query:
        return ConversationHandler.END
        
    await query.answer()
    user = update.effective_user
    if not user:
        return ConversationHandler.END

    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    action = query.data.split(":")[1]

    try:
        if action == "yes":
            existing_profile = await bot_instance._check_existing_beneficiary_profile(user.id)
            if existing_profile:
                complaint_data.name = existing_profile.get('name', complaint_data.name)
                complaint_data.sex = existing_profile.get('sex', complaint_data.sex)
                complaint_data.phone = existing_profile.get('phone', complaint_data.phone)
                complaint_data.residence_status = existing_profile.get('residence_status', complaint_data.residence_status)
                complaint_data.governorate = existing_profile.get('governorate', complaint_data.governorate)
                complaint_data.directorate = existing_profile.get('directorate', complaint_data.directorate)
                complaint_data.village = existing_profile.get('village_area', complaint_data.village)
                if hasattr(complaint_data, 'department'):
                    complaint_data.department = existing_profile.get('department', getattr(complaint_data, 'department', None))
                if hasattr(complaint_data, 'position'):
                    complaint_data.position = existing_profile.get('position', getattr(complaint_data, 'position', None))
            
            await query.edit_message_text(
                get_message('profile_data_confirmed', bot_instance, is_arabic)
            )
            return await _transition_to_next_step(update, context, 'village', is_arabic, from_callback=True)

        elif action == "no":
            await query.edit_message_text(
                get_message('collecting_new_profile_data', bot_instance, is_arabic)
            )
            return await collect_name(update, context, is_arabic, from_callback=True)
            
        else:
            logger.warning(f"Unknown action in handle_profile_confirmation: {query.data}")
            await query.edit_message_text(get_message('error_invalid_selection', bot_instance, is_arabic))
            return states.CONFIRM_EXISTING_PROFILE

    except Exception as e:
        logger.error(f"Error in handle_profile_confirmation for user {user.id}: {e}", exc_info=True)
        await query.edit_message_text(get_message('error_generic', bot_instance, is_arabic))
        await cleanup_conversation_state(update, context)
        return ConversationHandler.END

# --- Standard Data Collection Handlers (collect_/process_ pattern) ---

async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their name."""
    set_conversation_state(context, states.COLLECTING_NAME)
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_name',
        from_callback=from_callback
    )
    return states.COLLECTING_NAME

async def process_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the user's name input and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        name_input = update.message.text.strip()
        
        # First check basic validation (minimum words)
        if not name_input or len(name_input.split()) < bot_instance.config.application_settings.validation.min_name_words:
            await update.message.reply_text(get_message('validation_error_name', bot_instance, is_arabic))
            return states.COLLECTING_NAME
        
        # Perform AI-powered name validation
        is_valid = await bot_instance.is_name_valid(
            question_asked=get_message('prompt_enter_name', bot_instance, is_arabic),
            user_answer=name_input
        )
        if not is_valid:
            await update.message.reply_text(get_message('validation_error_name_ai', bot_instance, is_arabic))
            return states.COLLECTING_NAME
        
        complaint_data.name = name_input
        clear_conversation_state(context)
        # Proceed to next step using centralized transition logic
        return await _transition_to_next_step(update, context, 'name', is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_name for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error_generic', bot_instance, is_arabic))
        return states.COLLECTING_NAME

async def collect_sex(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to select their sex."""
    clear_conversation_state(context)
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_select_sex',
        get_sex_keyboard(bot_instance, is_arabic),
        from_callback=from_callback
    )
    return states.COLLECTING_SEX

async def process_sex(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the user's sex selection and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    query = update.callback_query
    if not query:
        return ConversationHandler.END
        
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)  # Remove inline keyboard
    
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        # Extract selected sex from callback data (format: "sex:male")
        selected_sex = query.data.split(":")[1]
        
        # Map callback values to display values
        sex_mapping = {
            'male': get_message('btn_male', bot_instance, is_arabic),
            'female': get_message('btn_female', bot_instance, is_arabic),
            'prefer_not_say': get_message('btn_prefer_not_say', bot_instance, is_arabic)
        }
        
        complaint_data.sex = sex_mapping.get(selected_sex, "")
        
        # Proceed to next step using centralized transition logic
        return await _transition_to_next_step(update, context, 'sex', is_arabic, from_callback=True)
    
    except Exception as e:
        logger.error(f"Error in process_sex for user {user.id}: {e}", exc_info=True)
        await query.edit_message_text(get_message('error_generic', bot_instance, is_arabic))
        return states.COLLECTING_SEX

async def collect_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their phone number."""
    set_conversation_state(context, states.COLLECTING_PHONE)
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_phone',
        from_callback=from_callback
    )
    return states.COLLECTING_PHONE

async def process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	
    """Processes the user's phone input and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        phone_input = update.message.text.strip()
        phone_patterns = bot_instance.config.application_settings.validation.phone_patterns
        
        if not validate_phone_number(phone_input, phone_patterns):
            await update.message.reply_text(get_message('validation_error_phone', bot_instance, is_arabic))
            return await collect_phone(update, context, is_arabic)
        
        complaint_data.phone = phone_input
        clear_conversation_state(context)
        # Proceed to next step using centralized transition logic
        return await _transition_to_next_step(update, context, 'phone', is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_phone for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error_generic', bot_instance, is_arabic))
        return states.COLLECTING_PHONE

async def collect_email(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their email address."""
    set_conversation_state(context, states.COLLECTING_EMAIL)
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_email',
        from_callback=from_callback
    )
    return states.COLLECTING_EMAIL

async def process_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the user's email input with validation and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        email_input = update.message.text.strip()
        
        if email_input:  # Email is optional but must be valid if provided
            if not EMAIL_REGEX.match(email_input):
                await update.message.reply_text(get_message('validation_error_email', bot_instance, is_arabic))
                return await collect_email(update, context, is_arabic)
        
        complaint_data.email = email_input if email_input else None
        clear_conversation_state(context)
        # Proceed to next step using centralized transition logic
        return await _transition_to_next_step(update, context, 'email', is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_email for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error_generic', bot_instance, is_arabic))
        return states.COLLECTING_EMAIL

async def collect_residence_status(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to select their residence status."""
    clear_conversation_state(context)
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_residence',
        get_residence_status_keyboard(bot_instance, is_arabic),
        from_callback=from_callback
    )
    return states.COLLECTING_RESIDENCE

async def process_residence_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the user's residence status selection and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    query = update.callback_query
    if not query:
        return ConversationHandler.END
        
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)  # Remove inline keyboard
    
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        # Extract selected residence status from callback data (format: "residence:Resident")
        residence_status = query.data.split(":")[1]
        
        if not residence_status:
            await query.edit_message_text(get_message('validation_error_residence', bot_instance, is_arabic))
            return states.COLLECTING_RESIDENCE
        
        complaint_data.residence_status = residence_status
        
        # Proceed to next step using centralized transition logic
        return await _transition_to_next_step(update, context, 'residence_status', is_arabic, from_callback=True)
    
    except Exception as e:
        logger.error(f"Error in process_residence_status for user {user.id}: {e}", exc_info=True)
        await query.edit_message_text(get_message('error_generic', bot_instance, is_arabic))
        return states.COLLECTING_RESIDENCE

async def collect_governorate(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to select their governorate."""
    clear_conversation_state(context)
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_governorate',
        get_governorates_keyboard(bot_instance, is_arabic),
        from_callback=from_callback
    )
    return states.COLLECTING_GOVERNORATE

async def process_governorate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the user's governorate selection and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    query = update.callback_query
    if not query:
        return ConversationHandler.END
        
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)  # Remove inline keyboard
    
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        # Extract selected governorate from callback data (format: "governorate:Taiz")
        governorate = query.data.split(":")[1]
        
        if not governorate:
            await query.edit_message_text(get_message('validation_error_governorate', bot_instance, is_arabic))
            return states.COLLECTING_GOVERNORATE
        
        # Check if "Other" was selected
        if governorate == get_message('governorates_other', bot_instance, is_arabic):
        	# set_conversation_state(context, states.COLLECTING_GOVERNORATE_OTHER)
            await query.edit_message_text(get_message('prompt_enter_governorate_other', bot_instance, is_arabic))
            return states.COLLECTING_GOVERNORATE_OTHER
        
        complaint_data.governorate = governorate
        
        # Proceed to next step using centralized transition logic
        return await _transition_to_next_step(update, context, 'governorate', is_arabic, from_callback=True)
    
    except Exception as e:
        logger.error(f"Error in process_governorate for user {user.id}: {e}", exc_info=True)
        await query.edit_message_text(get_message('error_generic', bot_instance, is_arabic))
        return states.COLLECTING_GOVERNORATE

async def process_governorate_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	
    """Processes manually entered governorate when 'Other' is selected."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        governorate_input = update.message.text.strip()
        if not governorate_input:
            await update.message.reply_text(get_message('validation_error_governorate', bot_instance, is_arabic))
            return states.COLLECTING_GOVERNORATE_OTHER
        
        complaint_data.governorate = governorate_input
        clear_conversation_state(context)
        # Proceed to next step using centralized transition logic
        return await _transition_to_next_step(update, context, 'governorate', is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_governorate_other for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error_generic', bot_instance, is_arabic))
        return states.COLLECTING_GOVERNORATE_OTHER

async def collect_directorate(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their directorate."""
    set_conversation_state(context, states.COLLECTING_DIRECTORATE)
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_directorate',
        from_callback=from_callback
    )
    return states.COLLECTING_DIRECTORATE

async def process_directorate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	
    """Processes the user's directorate input and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        directorate_input = update.message.text.strip()
        if not directorate_input:
            await update.message.reply_text(get_message('validation_error_directorate', bot_instance, is_arabic))
            return states.COLLECTING_DIRECTORATE
        
        complaint_data.directorate = directorate_input
        clear_conversation_state(context)
        # Proceed to next step using centralized transition logic
        return await _transition_to_next_step(update, context, 'directorate', is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_directorate for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error_generic', bot_instance, is_arabic))
        return states.COLLECTING_DIRECTORATE

async def collect_village(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their village/area."""
    set_conversation_state(context, states.COLLECTING_VILLAGE)
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_village',
        from_callback=from_callback
    )
    return states.COLLECTING_VILLAGE

async def process_village(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	
    """Processes the user's village/area input and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        village_input = update.message.text.strip()
        if not village_input:
            await update.message.reply_text(get_message('validation_error_village', bot_instance, is_arabic))
            return states.COLLECTING_VILLAGE
        
        complaint_data.village = village_input
        clear_conversation_state(context)
        # Proceed to next step using centralized transition logic
        return await _transition_to_next_step(update, context, 'village', is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_village for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error_generic', bot_instance, is_arabic))
        return states.COLLECTING_VILLAGE

async def collect_age(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their age."""
    set_conversation_state(context, states.COLLECTING_AGE)
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_age', # النص الجديد من utils.py
        from_callback=from_callback
    )
    return states.COLLECTING_AGE

async def process_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	
    """Processes the user's age, validates it, and transitions to the next step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    age_input = update.message.text.strip()
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    #complaint_data = _get_complaint_data(user.id, context)
    
    try:
        age_int = int(age_input)
        if not (1 <= age_int <= 120):
            await update.message.reply_text(get_message('validation_error_age', bot_instance, is_arabic))
            return states.COLLECTING_AGE # نطلب منه المحاولة مرة أخرى

        complaint_data = _get_complaint_data(user.id, context)
        complaint_data.age = age_int
        
        # *** الحفاظ على المعمارية ***
        # تم استلام النص بنجاح، ننظف الحالة
        clear_conversation_state(context)
        
        return await _transition_to_next_step(update, context, 'age', is_arabic)

    except (ValueError, TypeError):
        # إذا كان الإدخال ليس رقمًا
        await update.message.reply_text(get_message('validation_error_age', bot_instance, is_arabic))
        return states.COLLECTING_AGE

async def collect_disability(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """يسأل المستخدم عن حالة الإعاقة."""
    # ملاحظة معمارية مهمة: نحن الآن سنعرض أزرارًا، لا نتوقع نصًا.
    # لذا يجب أن "نُنظّف" حالة انتظار النص لكي لا يتعامل معالج النص الرئيسي مع أي شيء.
    clear_conversation_state(context)
    
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_select_disability',  # النص الذي أضفناه في utils.py
        get_disability_keyboard(bot_instance, is_arabic), # الدالة التي أضفناها في utils.py
        from_callback=from_callback
    )
    return states.COLLECTING_DISABILITY

async def process_disability(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعالج اختيار المستخدم (نعم/لا) وينتقل للخطوة التالية."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None) # نزيل الأزرار بعد الاختيار
    
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        # callback_data ستكون "disability:yes" أو "disability:no"
        selection = query.data.split(":")[1]  # نحصل على "yes" أو "no"
        
        # نترجم الاختصار إلى نص كامل ("نعم" أو "لا") من ملف utils.py
        disability_status = get_message(f'btn_{selection}_disability', bot_instance, is_arabic)
        complaint_data.disability = disability_status
        
        # نطلب من نظام الملاحة أن يأخذنا للخطوة التالية بعد خطوة 'disability'
        return await _transition_to_next_step(update, context, 'disability', is_arabic, from_callback=True)
    
    except Exception as e:
        logger.error(f"خطأ في process_disability للمستخدم {user.id}: {e}", exc_info=True)
        await query.edit_message_text(get_message('error_generic', bot_instance, is_arabic))
        return states.COLLECTING_DISABILITY

async def collect_nationality(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their nationality."""
    set_conversation_state(context, states.COLLECTING_NATIONALITY)
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_nationality',
        from_callback=from_callback
    )
    return states.COLLECTING_NATIONALITY

async def process_nationality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the user's nationality and transitions to the next step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    nationality_input = update.message.text.strip()
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    
    # التحقق من أن النص ليس فارغًا (يمكن إضافة شروط أخرى)
    if not nationality_input:
        await update.message.reply_text(get_message('validation_error_nationality', bot_instance, is_arabic))
        return states.COLLECTING_NATIONALITY

    complaint_data = _get_complaint_data(user.id, context)
    complaint_data.nationality = nationality_input
    
    # *** الحفاظ على المعمارية ***
    # تم استلام النص بنجاح، ننظف الحالة
    clear_conversation_state(context)
    
    return await _transition_to_next_step(update, context, 'nationality', is_arabic)

async def collect_complaint_text(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their complaint text."""
    set_conversation_state(context, states.COLLECTING_COMPLAINT_TEXT)
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_complaint_text',
        from_callback=from_callback
    )
    return states.COLLECTING_COMPLAINT_TEXT

async def process_complaint_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	
    """Processes the user's complaint text and transitions to submission confirmation."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        complaint_text = update.message.text.strip()
        if not complaint_text or len(complaint_text) < 20:
            await update.message.reply_text(get_message('validation_error_complaint_text_too_short', bot_instance, is_arabic))
            return await collect_complaint_text(update, context, is_arabic)
        
        complaint_data.original_complaint_text = complaint_text
        clear_conversation_state(context)
        # Prepare summary for confirmation
        summary = await _generate_complaint_summary(bot_instance, complaint_data, is_arabic)
        reply_markup = get_final_submission_inline_keyboard(bot_instance, is_arabic)
        
        await update.message.reply_text(
            text=summary,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return states.CONFIRM_COMPLAINT_SUBMISSION
    
    except Exception as e:
        logger.error(f"Error in process_complaint_text for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error_generic', bot_instance, is_arabic))
        return states.COLLECTING_COMPLAINT_TEXT

async def handle_submission_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles final submission confirmation for standard complaints."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    query = update.callback_query
    if not query:
        return ConversationHandler.END
        
    await query.answer()
    user = update.effective_user
    if not user:
        return ConversationHandler.END

    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    action = query.data.split(":")[1]

    try:
        if action == "confirm":
            # Show processing message immediately
            await query.edit_message_text(
                text=get_message('processing_submission', bot_instance, is_arabic),
                reply_markup=None
            )
            
            # Perform final AI analysis before submission
            analysis_result = await bot_instance.perform_final_complaint_analysis(complaint_data.original_complaint_text)
            
            # Check if content was flagged as abusive or spam
            if analysis_result.get('content_assessment') in ['ABUSIVE', 'SPAM']:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=get_message('complaint_rejected_content', bot_instance, is_arabic)
                )
                logger.warning(f"Rejected complaint from user {user.id} due to content assessment: {analysis_result['content_assessment']}")
                await cleanup_conversation_state(update, context, "error_in_submission")
                return ConversationHandler.END
            
            # Merge analysis results into complaint data
            complaint_data.complaint_category = analysis_result.get('complaint_category')
            complaint_data.sensitivity_score = analysis_result.get('sensitivity')
            complaint_data.complaint_details = analysis_result.get('summary')
            
            # Set submission timestamp
            complaint_data.telegram_message_date = datetime.now()
            
            # Submit complaint
            complaint_id = await bot_instance._log_complaint(complaint_data)
            if not complaint_id:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=get_message('error_submission_failed', bot_instance, is_arabic)
                )
                await cleanup_conversation_state(update, context)
                return ConversationHandler.END
            
            # Send confirmation as new message
            confirmation_msg = get_message(
                'complaint_submitted_successfully',
                bot_instance,
                is_arabic,
                complaint_id=complaint_id
            )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=confirmation_msg
            )
            
            if analysis_result.get('is_critical', False):
                logger.info(f"Complaint {complaint_id} was flagged as critical during final analysis. Sending follow-up contact info.")
                follow_up_message = get_message('general_inquiry_follow_up',
        bot_instance,
        is_arabic
                )
                await context.bot.send_message(chat_id=query.message.chat_id, text=follow_up_message, parse_mode='Markdown'
                )
            
            # Clean up
            context.user_data.pop('complaint_data', None)
            # Clean up conversation state after successful submission
            await cleanup_conversation_state(update, context)
            return ConversationHandler.END

        elif action == "cancel":
            await query.edit_message_text(get_message('complaint_flow_cancelled', bot_instance, is_arabic))
            context.user_data.pop('complaint_data', None)
            # Clean up conversation state after successful submission
            await cleanup_conversation_state(update, context)
            return ConversationHandler.END
            
        else:
            logger.warning(f"Unknown action in handle_submission_confirmation: {query.data}")
            await query.edit_message_text(get_message('error_invalid_selection', bot_instance, is_arabic))
            return states.CONFIRM_COMPLAINT_SUBMISSION

    except Exception as e:
        logger.error(f"Error in handle_submission_confirmation for user {user.id}: {e}", exc_info=True)
        await query.edit_message_text(get_message('error_generic', bot_instance, is_arabic))
        await cleanup_conversation_state(update, context)
        return ConversationHandler.END

# --- Critical Complaint Flow Handlers ---

async def collect_critical_name(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their name for a critical complaint with urgency indication."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    set_conversation_state(context, states.CRITICAL_COLLECTING_NAME)
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'critical_complaint_detected_prompt_name',
        from_callback=from_callback
    )
    return states.CRITICAL_COLLECTING_NAME

async def process_critical_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	
    """Processes name for critical complaint with validation and transitions to phone collection."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        name_input = update.message.text.strip()
        
        # First check basic validation (minimum words)
        if not name_input or len(name_input.split()) < bot_instance.config.application_settings.validation.min_name_words:
            await update.message.reply_text(get_message('validation_error_name', bot_instance, is_arabic))
            return states.CRITICAL_COLLECTING_NAME
        
        # Perform AI-powered name validation
        is_valid = await bot_instance.is_name_valid(
            question_asked=get_message('critical_complaint_detected_prompt_name', bot_instance, is_arabic),
            user_answer=name_input
        )
        
        if not is_valid:
            await update.message.reply_text(get_message('validation_error_name_ai', bot_instance, is_arabic))
            return states.CRITICAL_COLLECTING_NAME
            
        complaint_data.name = name_input
        clear_conversation_state(context)
        return await collect_critical_phone(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_critical_name for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error_generic', bot_instance, is_arabic))
        return states.CRITICAL_COLLECTING_NAME

async def collect_critical_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their phone for a critical complaint with urgency indication."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    set_conversation_state(context, states.CRITICAL_COLLECTING_PHONE)
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_critical_phone',
        from_callback=from_callback
    )
    return states.CRITICAL_COLLECTING_PHONE

async def process_critical_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	
    """Processes phone for critical complaint with validation and transitions to complaint type."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        phone_input = update.message.text.strip()
        phone_patterns = bot_instance.config.application_settings.validation.phone_patterns
        
        if not validate_phone_number(phone_input, phone_patterns):
            await update.message.reply_text(get_message('validation_error_phone', bot_instance, is_arabic))
            return states.CRITICAL_COLLECTING_PHONE
            
        complaint_data.phone = phone_input
        clear_conversation_state(context)
        # Get the confirmation message text
        confirmation_text = get_message('critical_confirm_submission_prompt', # We will need to add this key to our message file
    bot_instance,
    is_arabic
)
        # Get the confirmation keyboard (Confirm/Cancel buttons)
        reply_markup = get_final_submission_inline_keyboard(
    bot_instance, 
    is_arabic, 
    prefix="critical_submission"
)
        # Send the message to the user
        await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
        # Transition directly to the final confirmation state
        return states.CRITICAL_CONFIRM_COMPLAINT_SUBMISSION
    
    except Exception as e:
        logger.error(f"Error in process_critical_phone for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error_generic', bot_instance, is_arabic))
        return states.CRITICAL_COLLECTING_PHONE
        

async def collect_critical_complaint_text(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their complaint text for a critical complaint with urgency indication."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    set_conversation_state(context, states.CRITICAL_COLLECTING_COMPLAINT_TEXT)
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'critical_prompt_enter_complaint_text',
        from_callback=from_callback
    )
    return states.CRITICAL_COLLECTING_COMPLAINT_TEXT

async def process_critical_complaint_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	
    """Processes complaint text for critical complaint with validation and prepares for submission."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        complaint_text = update.message.text.strip()
        if not complaint_text or len(complaint_text) < 20:
            await update.message.reply_text(get_message('validation_error_complaint_text_too_short', bot_instance, is_arabic))
            return states.CRITICAL_COLLECTING_COMPLAINT_TEXT
            
        complaint_data.original_complaint_text = complaint_text
        clear_conversation_state(context)
        # Prepare summary for confirmation
        summary = await _generate_complaint_summary(bot_instance, complaint_data, is_arabic)
        reply_markup = get_final_submission_inline_keyboard(bot_instance, is_arabic, prefix="critical_submission")
        
        await update.message.reply_text(
            text=summary,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return states.CRITICAL_CONFIRM_COMPLAINT_SUBMISSION
    
    except Exception as e:
        logger.error(f"Error in process_critical_complaint_text for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error_generic', bot_instance, is_arabic))
        return states.CRITICAL_COLLECTING_COMPLAINT_TEXT

async def handle_critical_submission_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles final submission for critical complaints with urgency indicators."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    query = update.callback_query
    if not query:
        return ConversationHandler.END
        
    await query.answer()
    user = update.effective_user
    if not user:
        return ConversationHandler.END

    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    action = query.data.split(":")[1]

    try:
        if action == "confirm":
            # Show processing message immediately
            await query.edit_message_text(
                text=get_message('processing_submission_critical', bot_instance, is_arabic),
                reply_markup=None
            )

            # Perform final AI analysis before submission
            analysis_result = await bot_instance.perform_final_complaint_analysis(complaint_data.original_complaint_text)
            
            # Check if content was flagged as abusive or spam
            if analysis_result.get('content_assessment') in ['ABUSIVE', 'SPAM']:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=get_message('complaint_rejected_content', bot_instance, is_arabic)
                )
                logger.warning(f"Rejected critical complaint from user {user.id} due to content assessment: {analysis_result['content_assessment']}")
                await cleanup_conversation_state(update, context)
                return ConversationHandler.END
            
            # Merge analysis results into complaint data
            complaint_data.complaint_category = analysis_result.get('complaint_category')
            complaint_data.sensitivity_score = analysis_result.get('sensitivity')
            complaint_data.complaint_details = analysis_result.get('summary')

            # Set critical complaint timestamp
            complaint_data.telegram_message_date = datetime.now()
            complaint_data.is_critical = True

            # Submit critical complaint
            complaint_id = await bot_instance._log_complaint(complaint_data)
            if not complaint_id:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=get_message('error_submission_failed_critical', bot_instance, is_arabic)
                )
                await cleanup_conversation_state(update, context)
                return ConversationHandler.END

            # Send critical notifications
            if hasattr(bot_instance, 'email_service'):
                notification_email = bot_instance.config.critical_complaint_config.notification_email
                await bot_instance.email_service.send_critical_complaint_email(
        data=complaint_data,
        notification_email=notification_email,
        analysis_results=analysis_result
    )
            else:
                await bot_instance._send_critical_complaint_email(complaint_data)

            # Notify user with new message
            confirmation_msg = get_message(
                'critical_complaint_submitted_successfully',
                bot_instance,
                is_arabic,
                complaint_id=complaint_id
            )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=confirmation_msg
            )
            follow_up_message = get_message('general_inquiry_follow_up', bot_instance, is_arabic)
            await context.bot.send_message(chat_id=query.message.chat_id, text=follow_up_message, parse_mode='Markdown'
            )

            # Clean up
            context.user_data.pop('complaint_data', None)
            # Clean up conversation state after successful submission
            await cleanup_conversation_state(update, context)
            return ConversationHandler.END

        elif action == "cancel":
            await query.edit_message_text(get_message('complaint_flow_cancelled', bot_instance, is_arabic))
            context.user_data.pop('complaint_data', None)
            # Clean up conversation state after successful submission
            await cleanup_conversation_state(update, context)
            return ConversationHandler.END
            
        else:
            logger.warning(f"Unknown action in handle_critical_submission_confirmation: {query.data}")
            await query.edit_message_text(get_message('error_invalid_selection', bot_instance, is_arabic))
            return states.CRITICAL_CONFIRM_COMPLAINT_SUBMISSION

    except Exception as e:
        logger.error(f"Error in handle_critical_submission_confirmation for user {user.id}: {e}", exc_info=True)
        await query.edit_message_text(get_message('error_generic', bot_instance, is_arabic))
        await cleanup_conversation_state(update, context)
        return ConversationHandler.END
