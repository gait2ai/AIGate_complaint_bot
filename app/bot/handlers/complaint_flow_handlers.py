# app/bot/handlers/complaint_flow_handlers.py
"""
AI Gate for Artificial Intelligence Applications
Complaint Flow Handlers Module for Institution Complaint Management Bot

This module defines and manages the entire conversation flow for users
submitting complaints. It handles various stages including the initial choice
between a new complaint or a reminder for a previous one, user profile
confirmation/data collection, gathering detailed complaint information,
managing critical case diversions, and final submission confirmation.
It integrates with InstitutionBot for core logic and data persistence,
and utilizes shared states and utilities.

Refactored to use Pydantic-style configuration access:
- All dictionary-style config access (config['key']) replaced with attribute-style (config.key)
- Type safety and IDE autocompletion support added
"""

import logging
from datetime import datetime
from typing import Optional

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters
)
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
        logger.error(f"Error in _send_or_edit: {e}")

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

# --- State Handler Functions ---

async def ask_new_or_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for complaint flow (state: states.ASK_NEW_OR_REMINDER)."""
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
            logger.info(f"No previous complaints for user {user.id}")
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
        return states.HANDLE_NEW_OR_REMINDER_CHOICE

    except Exception as e:
        logger.error(f"Error in ask_new_or_reminder for user {user.id}: {e}")
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
        action = query.data.split(":")[1]  # "complaint_flow:new" or "complaint_flow:reminder"

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
            return states.HANDLE_NEW_OR_REMINDER_CHOICE

    except Exception as e:
        logger.error(f"Error in handle_new_or_reminder_choice for user {user.id}: {e}")
        await query.edit_message_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return ConversationHandler.END

async def _proceed_to_profile_check(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool) -> int:
    """Helper: Branches to critical flow or standard profile collection."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    complaint_data = _get_complaint_data(user.id, context)

    if complaint_data.is_critical:
        await _send_or_edit(
            update,
            bot_instance.config.application_settings.ui_messages.critical_complaint_detected_prompt_name
        )
        return states.CRITICAL_COLLECTING_NAME

    existing_profile = await bot_instance._check_existing_beneficiary_profile(user.id)
    if existing_profile:
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
        await _ask_for_field(
            update,
            context,
            is_arabic,
            'prompt_enter_name'
        )
        return states.COLLECTING_NAME

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
    action = query.data.split(":")[1]  # "profile_confirm:yes" or "profile_confirm:no"

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
            await _ask_for_field(
                update,
                context,
                is_arabic,
                'prompt_enter_name'
            )
            return states.COLLECTING_NAME
            
        else:
            logger.warning(f"Unknown action in handle_profile_confirmation: {query.data}")
            await query.edit_message_text(bot_instance.config.application_settings.ui_messages.error_invalid_selection)
            return states.CONFIRM_EXISTING_PROFILE

    except Exception as e:
        logger.error(f"Error in handle_profile_confirmation for user {user.id}: {e}")
        await query.edit_message_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return ConversationHandler.END

# --- Standard Data Collection Handlers ---

async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_name',
        from_callback=from_callback
    )
    return states.COLLECTING_NAME

async def process_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    name_input = update.message.text.strip()
    if not name_input or len(name_input.split()) < bot_instance.config.application_settings.validation.min_name_words:
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_name)
        return await collect_name(update, context, is_arabic)
    
    complaint_data.name = name_input
    return await collect_sex(update, context, is_arabic)

async def collect_sex(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
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
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
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
    return await collect_phone(update, context, is_arabic)

async def collect_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_phone',
        from_callback=from_callback
    )
    return states.COLLECTING_PHONE

async def process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    phone_input = update.message.text.strip()
    if not validate_phone_number(phone_input, bot_instance.config.application_settings.validation.phone_patterns):
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_phone)
        return await collect_phone(update, context, is_arabic)
    
    complaint_data.phone = phone_input
    return await collect_residence_status(update, context, is_arabic)

async def collect_residence_status(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_residence',
        from_callback=from_callback
    )
    return states.COLLECTING_RESIDENCE

async def process_residence_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    complaint_data = _get_complaint_data(user.id, context)
    complaint_data.residence_status = update.message.text.strip()
    return await collect_governorate(update, context, get_user_preferred_language_is_arabic(update, context.bot_data['bot_instance']))

async def collect_governorate(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_governorate',
        from_callback=from_callback
    )
    return states.COLLECTING_GOVERNORATE

async def process_governorate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    complaint_data = _get_complaint_data(user.id, context)
    complaint_data.governorate = update.message.text.strip()
    return await collect_directorate(update, context, get_user_preferred_language_is_arabic(update, context.bot_data['bot_instance']))

async def collect_directorate(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_directorate',
        from_callback=from_callback
    )
    return states.COLLECTING_DIRECTORATE

async def process_directorate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    complaint_data = _get_complaint_data(user.id, context)
    complaint_data.directorate = update.message.text.strip()
    return await collect_village(update, context, get_user_preferred_language_is_arabic(update, context.bot_data['bot_instance']))

async def collect_village(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    await _ask_for_field(
        update,
        context,
        is_arabic,
        'prompt_enter_village',
        from_callback=from_callback
    )
    return states.COLLECTING_VILLAGE

async def process_village(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    complaint_data = _get_complaint_data(user.id, context)
    complaint_data.village = update.message.text.strip()
    return await collect_complaint_text(update, context, get_user_preferred_language_is_arabic(update, context.bot_data['bot_instance']))

# --- Complaint Text Collection ---

async def collect_complaint_text(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    complaint_data = _get_complaint_data(user.id, context)

    if complaint_data.original_complaint_text:
        reply_markup = get_complaint_text_choice_inline_keyboard(bot_instance, is_arabic)
        message = get_message(
            'offer_use_original_complaint',
            bot_instance,
            is_arabic,
            original_text_snippet=complaint_data.original_complaint_text[:100]
        )
        await _send_or_edit(update, message, reply_markup)
        return states.CHOOSING_COMPLAINT_TEXT
    else:
        await _ask_for_field(
            update,
            context,
            is_arabic,
            'prompt_enter_complaint_text',
            from_callback=from_callback
        )
        return states.COLLECTING_COMPLAINT_TEXT

async def handle_complaint_text_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    action = query.data.split(":")[1]

    if action == "use_original":
        await query.edit_message_text(
            bot_instance.config.application_settings.ui_messages.using_original_complaint
        )
        return await confirm_submission(update, context, is_arabic, from_callback=True)
    elif action == "write_new":
        await query.edit_message_text(
            bot_instance.config.application_settings.ui_messages.prompt_enter_new_complaint_text
        )
        await _ask_for_field(
            update,
            context,
            is_arabic,
            'prompt_enter_complaint_text'
        )
        return states.COLLECTING_COMPLAINT_TEXT
    else:
        await query.edit_message_text(
            bot_instance.config.application_settings.ui_messages.error_invalid_selection
        )
        return states.CHOOSING_COMPLAINT_TEXT

async def process_complaint_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    complaint_text = update.message.text.strip()
    if len(complaint_text) < bot_instance.config.application_settings.validation.min_suggestion_length:
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_description)
        return await collect_complaint_text(update, context, is_arabic)
    
    complaint_data.original_complaint_text = complaint_text
    return await confirm_submission(update, context, is_arabic)

# --- Submission Confirmation ---

async def confirm_submission(update: Update, context: ContextTypes.DEFAULT_TYPE, is_arabic: bool, from_callback: bool = False) -> int:
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    complaint_data = _get_complaint_data(user.id, context)
    
    summary_parts = [bot_instance.config.application_settings.ui_messages.complaint_review_summary_header]
    fields_to_summarize = {
        'label_name': complaint_data.name,
        'label_sex': complaint_data.sex,
        'label_phone': complaint_data.phone,
        'label_residence_status': complaint_data.residence_status,
        'label_governorate': complaint_data.governorate,
        'label_directorate': complaint_data.directorate,
        'label_village': complaint_data.village,
        'label_complaint_text': complaint_data.original_complaint_text[:300] + ("..." if len(complaint_data.original_complaint_text) > 300 else ""),
        'label_english_summary': complaint_data.complaint_details[:300] + ("..." if len(complaint_data.complaint_details) > 300 else "") if complaint_data.complaint_details else bot_instance.config.application_settings.placeholders.summary_not_yet_generated
    }

    for label_key, value in fields_to_summarize.items():
        if value:
            label = get_message(label_key, bot_instance, is_arabic)
            summary_parts.append(f"**{label}:** {value}")
    
    summary_text = "\n".join(summary_parts)
    summary_text += f"\n\n{bot_instance.config.application_settings.ui_messages.confirm_submission_prompt}"
    
    reply_markup = get_final_submission_inline_keyboard(bot_instance, is_arabic)
    await _send_or_edit(update, summary_text, reply_markup)
    return states.CONFIRM_SUBMISSION

async def handle_submission_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    action = query.data.split(":")[1]

    try:
        if action == "confirm":
            if complaint_data.telegram_message_date is None:
                msg_for_date = query.message or update.effective_message
                complaint_data.telegram_message_date = msg_for_date.date if msg_for_date else datetime.now()

            success = await bot_instance._log_complaint(complaint_data)
            
            if success:
                complaint_id = getattr(complaint_data, 'db_id', bot_instance.config.application_settings.placeholders.not_available_placeholder)
                await query.edit_message_text(
                    get_message('complaint_submitted_successfully', bot_instance, is_arabic, complaint_id=complaint_id)
                )
                if complaint_data.is_critical:
                    await bot_instance._send_critical_complaint_email(complaint_data)
            else:
                await query.edit_message_text(
                    bot_instance.config.application_settings.ui_messages.error_submission_failed
                )
        
        elif action == "cancel":
            await query.edit_message_text(
                bot_instance.config.application_settings.ui_messages.complaint_submission_cancelled
            )
        else:
            await query.edit_message_text(
                bot_instance.config.application_settings.ui_messages.error_invalid_selection
            )
            return states.CONFIRM_SUBMISSION

        context.user_data.pop('complaint_data', None)
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in handle_submission_confirmation for user {user.id}: {e}")
        await query.edit_message_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return ConversationHandler.END

# --- Critical Complaint Flow Handlers ---

async def collect_critical_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    name_input = update.message.text.strip()
    if not name_input or len(name_input.split()) < bot_instance.config.application_settings.validation.min_name_words:
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_name)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.critical_complaint_detected_prompt_name)
        return states.CRITICAL_COLLECTING_NAME

    complaint_data.name = name_input
    await update.message.reply_text(bot_instance.config.application_settings.ui_messages.prompt_enter_critical_phone)
    return states.CRITICAL_COLLECTING_PHONE

async def collect_critical_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    complaint_data = _get_complaint_data(user.id, context)
    
    phone_input = update.message.text.strip()
    if not validate_phone_number(phone_input, bot_instance.config.application_settings.validation.phone_patterns):
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.validation_error_phone)
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.prompt_enter_critical_phone)
        return states.CRITICAL_COLLECTING_PHONE

    complaint_data.phone = phone_input
    
    if not complaint_data.original_complaint_text:
        complaint_data.original_complaint_text = bot_instance.config.application_settings.ui_messages.critical_complaint_default_text
    
    if complaint_data.telegram_message_date is None:
        complaint_data.telegram_message_date = update.effective_message.date if update.effective_message else datetime.now()

    try:
        success = await bot_instance._log_complaint(complaint_data)
        if success:
            await bot_instance._send_critical_complaint_email(complaint_data)
            complaint_id = getattr(complaint_data, 'db_id', bot_instance.config.application_settings.placeholders.not_available_placeholder)
            await update.message.reply_text(
                get_message('critical_complaint_submitted_successfully', bot_instance, is_arabic, complaint_id=complaint_id)
            )
        else:
            await update.message.reply_text(
                bot_instance.config.application_settings.ui_messages.error_submission_failed_critical
            )
        
        context.user_data.pop('complaint_data', None)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error submitting critical complaint for user {user.id}: {e}")
        await update.message.reply_text(bot_instance.config.application_settings.ui_messages.error_generic)
        return ConversationHandler.END

# --- Fallback / Cancel ---

async def local_cancel_complaint_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the current complaint flow."""
    bot_instance: InstitutionBot = context.bot_data['bot_instance']
    user = update.effective_user
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    
    if user:
        context.user_data.pop('complaint_data', None)

    await update.message.reply_text(
        bot_instance.config.application_settings.ui_messages.complaint_flow_cancelled,
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# --- ConversationHandler Definition ---

def get_complaint_conversation_handler() -> ConversationHandler:
    """Constructs and returns the ConversationHandler for the complaint submission flow."""
    
    state_handlers = {
        states.ASK_NEW_OR_REMINDER: [
            CallbackQueryHandler(
                handle_new_or_reminder_choice,
                pattern=r"^complaint_flow:(new|reminder)$"
            )
        ],
        states.CONFIRM_EXISTING_PROFILE: [
            CallbackQueryHandler(
                handle_profile_confirmation,
                pattern=r"^profile_confirm:(yes|no)$"
            )
        ],
        states.COLLECTING_NAME: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_name
            )
        ],
        states.COLLECTING_SEX: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_sex
            )
        ],
        states.COLLECTING_PHONE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_phone
            )
        ],
        states.COLLECTING_RESIDENCE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_residence_status
            )
        ],
        states.COLLECTING_GOVERNORATE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_governorate
            )
        ],
        states.COLLECTING_DIRECTORATE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_directorate
            )
        ],
        states.COLLECTING_VILLAGE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_village
            )
        ],
        states.CHOOSING_COMPLAINT_TEXT: [
            CallbackQueryHandler(
                handle_complaint_text_choice,
                pattern=r"^complaint_text_choice:(use_original|write_new)$"
            )
        ],
        states.COLLECTING_COMPLAINT_TEXT: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_complaint_text
            )
        ],
        states.CONFIRM_SUBMISSION: [
            CallbackQueryHandler(
                handle_submission_confirmation,
                pattern=r"^final_submission:(confirm|cancel)$"
            )
        ],
        states.CRITICAL_COLLECTING_NAME: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                collect_critical_name
            )
        ],
        states.CRITICAL_COLLECTING_PHONE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                collect_critical_phone
            )
        ]
    }
    
    return ConversationHandler(
        entry_points=[],
        states=state_handlers,
        fallbacks=[
            CommandHandler("cancel", local_cancel_complaint_flow),
            CommandHandler("start", local_cancel_complaint_flow)
        ],
        name="complaint_submission_flow",
        allow_reentry=True
    )