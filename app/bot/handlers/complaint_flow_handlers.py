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
- Simple direct skip logic controlled by config.yaml
- Improved critical complaint flow
- Better error handling and user feedback
"""

import logging
import re
from datetime import datetime
from typing import Optional

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

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
    validate_phone_number
)

logger = logging.getLogger(__name__)

# Email validation pattern
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# --- Helper functions ---

def _get_complaint_data(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> ComplaintData:
    """
    Retrieves or initializes ComplaintData for the user from context.user_data.
    """
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
    Determines if a user profile contains meaningful data worth confirming.
    Only considers it meaningful if it has contact information like phone number.
    """
    if not profile:
        return False
    
    meaningful_fields = ['phone', 'email', 'residence_status', 'governorate', 'directorate', 'village_area']
    return any(profile.get(field) and str(profile.get(field)).strip() for field in meaningful_fields)

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
        
        await context.bot.send_message(
            chat_id=user.id, 
            text=message_text, 
            reply_markup=reply_markup, 
            parse_mode=ParseMode.MARKDOWN
        )
        return states.ASK_NEW_OR_REMINDER

    except Exception as e:
        logger.error(f"Error in ask_new_or_reminder for user {user.id}: {e}", exc_info=True)
        await _send_or_edit(update, bot_instance.config.application_settings.ui_messages.error_generic)
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
                await query.edit_message_text(bot_instance.config.application_settings.ui_messages.reminder_no_complaints_found)
                return ConversationHandler.END

            most_recent = previous_complaints[0]
            retrieved_details = {
                "name": most_recent.get("submitter_name", bot_instance.config.application_settings.placeholders.data_not_available),
                "text_snippet": most_recent.get("summary", bot_instance.config.application_settings.placeholders.data_not_available)[:50],
                "date": most_recent.get("date", bot_instance.config.application_settings.placeholders.data_not_available)
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
            await query.edit_message_text(text=bot_instance.config.application_settings.ui_messages.new_complaint_selected)
            return await _proceed_to_profile_check(update, context, is_arabic)
            
        else:
            logger.warning(f"Unknown action in handle_new_or_reminder_choice: {query.data}")
            await query.edit_message_text(bot_instance.config.application_settings.ui_messages.error_invalid_selection)
            return states.ASK_NEW_OR_REMINDER

    except Exception as e:
        logger.error(f"Error in handle_new_or_reminder_choice for user {user.id}: {e}", exc_info=True)
        await query.edit_message_text(bot_instance.config.application_settings.ui_messages.error_generic)
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
        await _send_or_edit(update, bot_instance.config.application_settings.ui_messages.error_generic)
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
            
            await query.edit_message_text(
                bot_instance.config.application_settings.ui_messages.profile_data_confirmed
            )
            return await collect_complaint_text(update, context, is_arabic, from_callback=True)

        elif action == "no":
            await query.edit_message_text(
                bot_instance.config.application_settings.ui_messages.collecting_new_profile_data
            )
            return await collect_name(update, context, is_arabic, from_callback=True)
            
        else:
            logger.warning(f"Unknown action in handle_profile_confirmation: {query.data}")
            await query.edit_message_text(bot_instance.config.application_settings.ui_messages.error_invalid_selection)
            return states.CONFIRM_EXISTING_PROFILE

    except Exception as e:
        logger.error(f"Error in handle_profile_confirmation for user {user.id}: {e}", exc_info=True)
        await query.edit_message_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return ConversationHandler.END

# --- Standard Data Collection Handlers (collect_/process_ pattern) ---

async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their name."""
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
        if not name_input or len(name_input.split()) < bot_instance.config.application_settings.validation.min_name_words:
            await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_name)
            return await collect_name(update, context, is_arabic)
        
        complaint_data.name = name_input
        
        # Direct skip logic chain - start from sex (next mandatory field after name)
        config = bot_instance.config.application_settings.data_collection_fields
        return await collect_sex(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_name for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.COLLECTING_NAME

async def collect_sex(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to select their sex."""
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
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        sex_input = update.message.text.strip()
        valid_options = [
            bot_instance.config.application_settings.ui_messages.btn_male,
            bot_instance.config.application_settings.ui_messages.btn_female,
            bot_instance.config.application_settings.ui_messages.btn_prefer_not_say,
            bot_instance.config.application_settings.ui_messages.btn_skip
        ]
        
        if sex_input not in valid_options:
            await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_invalid_selection)
            return await collect_sex(update, context, is_arabic)
        
        complaint_data.sex = "" if sex_input == bot_instance.config.application_settings.ui_messages.btn_skip else sex_input
        
        # Direct skip logic chain - start from phone (next mandatory field after sex)
        config = bot_instance.config.application_settings.data_collection_fields
        return await collect_phone(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_sex for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.COLLECTING_SEX

async def collect_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their phone number."""
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
        if not validate_phone_number(phone_input, bot_instance.config.application_settings.validation.phone_patterns):
            await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_phone)
            return await collect_phone(update, context, is_arabic)
        
        complaint_data.phone = phone_input
        
        # Direct skip logic chain - check optional fields first, then mandatory location fields
        config = bot_instance.config.application_settings.data_collection_fields
        if getattr(config, 'email', False):
            return await collect_email(update, context, is_arabic)
        elif getattr(config, 'department', False):
            return await collect_department(update, context, is_arabic)
        elif getattr(config, 'position', False):
            return await collect_position(update, context, is_arabic)
        elif getattr(config, 'complaint_type', False):
            return await collect_complaint_type(update, context, is_arabic)
        else:
            # Proceed to mandatory location fields
            return await collect_residence_status(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_phone for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.COLLECTING_PHONE

async def collect_email(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their email address."""
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
                await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_email)
                return await collect_email(update, context, is_arabic)
        
        complaint_data.email = email_input
        
        # Direct skip logic chain - check remaining optional fields, then mandatory location fields
        config = bot_instance.config.application_settings.data_collection_fields
        if getattr(config, 'department', False):
            return await collect_department(update, context, is_arabic)
        elif getattr(config, 'position', False):
            return await collect_position(update, context, is_arabic)
        elif getattr(config, 'complaint_type', False):
            return await collect_complaint_type(update, context, is_arabic)
        else:
            # Proceed to mandatory location fields
            return await collect_residence_status(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_email for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.COLLECTING_EMAIL

async def collect_department(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their department."""
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_department',
        from_callback=from_callback
    )
    return states.COLLECTING_DEPARTMENT

async def process_department(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the user's department input with validation and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        department_input = update.message.text.strip()
        if not department_input or len(department_input) > 100:
            await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_department)
            return await collect_department(update, context, is_arabic)
        
        complaint_data.department = department_input
        
        # Direct skip logic chain - check remaining optional fields, then mandatory location fields
        config = bot_instance.config.application_settings.data_collection_fields
        if getattr(config, 'position', False):
            return await collect_position(update, context, is_arabic)
        elif getattr(config, 'complaint_type', False):
            return await collect_complaint_type(update, context, is_arabic)
        else:
            # Proceed to mandatory location fields
            return await collect_residence_status(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_department for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.COLLECTING_DEPARTMENT

async def collect_position(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their position."""
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_position',
        from_callback=from_callback
    )
    return states.COLLECTING_POSITION

async def process_position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the user's position input with validation and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        position_input = update.message.text.strip()
        if not position_input or len(position_input) > 100:
            await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_position)
            return await collect_position(update, context, is_arabic)
        
        complaint_data.position = position_input
        
        # Direct skip logic chain - check remaining optional fields, then mandatory location fields
        config = bot_instance.config.application_settings.data_collection_fields
        if getattr(config, 'complaint_type', False):
            return await collect_complaint_type(update, context, is_arabic)
        else:
            # Proceed to mandatory location fields
            return await collect_residence_status(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_position for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.COLLECTING_POSITION

async def collect_complaint_type(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their complaint type."""
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_complaint_type',
        from_callback=from_callback
    )
    return states.COLLECTING_COMPLAINT_TYPE

async def process_complaint_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the user's complaint type and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        complaint_type_input = update.message.text.strip()
        if not complaint_type_input:
            await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_complaint_type)
            return await collect_complaint_type(update, context, is_arabic)
        
        complaint_data.complaint_type = complaint_type_input
        
        # Direct skip logic chain - proceed to mandatory location fields
        return await collect_residence_status(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_complaint_type for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.COLLECTING_COMPLAINT_TYPE

async def collect_residence_status(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their residence status."""
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_residence',
        from_callback=from_callback
    )
    return states.COLLECTING_RESIDENCE

async def process_residence_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the user's residence status and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        residence_input = update.message.text.strip()
        if not residence_input:
            await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_residence)
            return await collect_residence_status(update, context, is_arabic)
        
        complaint_data.residence_status = residence_input
        
        # Direct skip logic chain - proceed to governorate (next mandatory location field)
        return await collect_governorate(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_residence_status for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.COLLECTING_RESIDENCE

async def collect_governorate(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their governorate."""
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_governorate',
        from_callback=from_callback
    )
    return states.COLLECTING_GOVERNORATE

async def process_governorate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the user's governorate and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        governorate_input = update.message.text.strip()
        if not governorate_input:
            await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_governorate)
            return await collect_governorate(update, context, is_arabic)
        
        complaint_data.governorate = governorate_input
        
        # Direct skip logic chain - proceed to directorate (next mandatory location field)
        return await collect_directorate(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_governorate for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.COLLECTING_GOVERNORATE

async def collect_directorate(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their directorate."""
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_directorate',
        from_callback=from_callback
    )
    return states.COLLECTING_DIRECTORATE

async def process_directorate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the user's directorate and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        directorate_input = update.message.text.strip()
        if not directorate_input:
            await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_directorate)
            return await collect_directorate(update, context, is_arabic)
        
        complaint_data.directorate = directorate_input
        
        # Direct skip logic chain - proceed to village (next mandatory location field)
        return await collect_village(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_directorate for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.COLLECTING_DIRECTORATE

async def collect_village(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their village."""
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_village',
        from_callback=from_callback
    )
    return states.COLLECTING_VILLAGE

async def process_village(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the user's village and transitions to next appropriate step."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        village_input = update.message.text.strip()
        if not village_input:
            await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_village)
            return await collect_village(update, context, is_arabic)
        
        complaint_data.village = village_input
        
        # After all location fields, proceed directly to complaint text collection
        return await collect_complaint_text(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_village for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.COLLECTING_VILLAGE

async def collect_complaint_text(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their complaint text."""
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
            await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_complaint_text_too_short)
            return await collect_complaint_text(update, context, is_arabic)
        
        complaint_data.original_complaint_text = complaint_text
        
        # Prepare summary for confirmation
        summary = await bot_instance._generate_complaint_summary(complaint_data)
        reply_markup = get_final_submission_inline_keyboard(bot_instance, is_arabic)
        
        await update.message.reply_text(
            text=summary,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return states.CONFIRM_COMPLAINT_SUBMISSION
    
    except Exception as e:
        logger.error(f"Error in process_complaint_text for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.COLLECTING_COMPLAINT_TEXT

# --- Critical Complaint Flow Handlers ---

async def collect_critical_name(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their name for a critical complaint with urgency indication."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
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
        if not name_input or len(name_input.split()) < bot_instance.config.application_settings.validation.min_name_words:
            await update.message.reply_text(get_message('validation_error_name', bot_instance, is_arabic))
            return states.CRITICAL_COLLECTING_NAME
            
        complaint_data.name = name_input
        return await collect_critical_phone(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_critical_name for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.CRITICAL_COLLECTING_NAME

async def collect_critical_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their phone for a critical complaint with urgency indication."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
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
        if not validate_phone_number(phone_input, bot_instance.config.application_settings.validation.phone_patterns):
            await update.message.reply_text(get_message('validation_error_phone', bot_instance, is_arabic))
            return states.CRITICAL_COLLECTING_PHONE
            
        complaint_data.phone = phone_input
        return await collect_critical_complaint_type(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_critical_phone for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.CRITICAL_COLLECTING_PHONE

async def collect_critical_complaint_type(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their complaint type for a critical complaint with urgency indication."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'critical_prompt_enter_complaint_type',
        from_callback=from_callback
    )
    return states.CRITICAL_COLLECTING_COMPLAINT_TYPE

async def process_critical_complaint_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes complaint type for critical complaint with validation and transitions to text collection."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    try:
        complaint_type_input = update.message.text.strip()
        if not complaint_type_input:
            await update.message.reply_text(get_message('validation_error_complaint_type', bot_instance, is_arabic))
            return states.CRITICAL_COLLECTING_COMPLAINT_TYPE
            
        complaint_data.complaint_type = complaint_type_input
        return await collect_critical_complaint_text(update, context, is_arabic)
    
    except Exception as e:
        logger.error(f"Error in process_critical_complaint_type for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.CRITICAL_COLLECTING_COMPLAINT_TYPE

async def collect_critical_complaint_text(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    """Prompts user to enter their complaint text for a critical complaint with urgency indication."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'critical_prompt_enter_complaint_text',
        from_callback=from_callback
    )
    return states.CRITICAL_COLLECTING_COMPLAINT_TEXT

async def process_critical_complaint_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes complaint text for critical complaint with validation and transitions to submission."""
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
        return await handle_critical_submission_confirmation(update, context)
    
    except Exception as e:
        logger.error(f"Error in process_critical_complaint_text for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return states.CRITICAL_COLLECTING_COMPLAINT_TEXT

async def handle_critical_submission_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles final submission for critical complaints with urgency indicators."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)

    try:
        # Set critical complaint timestamp
        complaint_data.telegram_message_date = datetime.now()
        complaint_data.is_critical = True

        # Submit critical complaint
        complaint_id = await bot_instance._log_complaint(complaint_data)
        if not complaint_id:
            await _send_or_edit(update, get_message('error_submission_failed_critical', bot_instance, is_arabic))
            return ConversationHandler.END

        # Send critical notifications
        if hasattr(bot_instance, 'email_service'):
            await bot_instance.email_service.send_critical_complaint_email(complaint_data)
        else:
            await bot_instance._send_critical_complaint_email(complaint_data)

        # Notify user
        confirmation_msg = get_message(
            'critical_complaint_submitted_successfully',
            bot_instance,
            is_arabic,
            complaint_id=complaint_id
        )
        await _send_or_edit(update, confirmation_msg)

        # Clean up
        context.user_data.pop('complaint_data', None)
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in handle_critical_submission_confirmation for user {user.id}: {e}", exc_info=True)
        await _send_or_edit(update, get_message('error_submission_failed_critical', bot_instance, is_arabic))
        return ConversationHandler.END