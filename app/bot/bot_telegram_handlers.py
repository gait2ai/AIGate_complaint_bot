"""
AI Gate for Artificial Intelligence Applications
Telegram Handlers Module for Institution Complaint Management Bot

This module handles all Telegram-specific interactions and conversation flows,
ensuring a configurable and maintainable approach to user interactions.
"""

import logging
from typing import Dict, Any

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)

from app.bot.institution_bot_logic import InstitutionBot, ComplaintData

# State constants for ConversationHandler
(START_COMPLAINT_FLOW, CONFIRM_EXISTING, COLLECTING_NAME, COLLECTING_SEX,
 COLLECTING_PHONE, COLLECTING_RESIDENCE, COLLECTING_GOVERNORATE,
 COLLECTING_DIRECTORATE, COLLECTING_VILLAGE, COLLECTING_COMPLAINT,
 CONFIRMING_SUBMISSION, CRITICAL_NAME, CRITICAL_PHONE) = range(13)

# Logger for this module
logger = logging.getLogger(__name__)

# Default messages dictionary (primarily for keys not expected to change often per institution,
# or as a fallback if not defined in config.yaml)
# Placeholders like {institution_name} will be formatted by get_message.
DEFAULT_MESSAGES = {
    'ar': {
        'welcome': "مرحباً بك في بوت {institution_name}\nيمكنك تقديم شكوى أو اقتراح.",
        'welcome_existing': "مرحباً بك مرة أخرى! بياناتك محفوظة لدينا لـ {institution_name}.",
        'use_existing_data': "هل تريد استخدام بياناتك المحفوظة؟",
        'enter_name': "الرجاء إدخال اسمك الكامل:",
        'enter_sex': "الرجاء تحديد جنسك:",
        'enter_phone': "الرجاء إدخال رقم هاتفك:",
        'enter_residence': "الرجاء تحديد وضعك السكني:",
        'enter_governorate': "الرجاء إدخال المحافظة:",
        'enter_directorate': "الرجاء إدخال المديرية:",
        'enter_village': "الرجاء إدخال القرية/المنطقة:",
        'enter_complaint': "الرجاء إدخال تفاصيل شكواك أو اقتراحك:",
        'confirm_submission_prompt': "هل البيانات التالية صحيحة وجاهزة للإرسال؟", # Renamed for clarity
        'complaint_summary_header': "ملخص البيانات:",
        'critical_intro': "تم تصنيف حالتك كحالة حرجة لـ {institution_name}. سيتم التعامل معها بأولوية عالية.",
        'critical_name': "الرجاء إدخال اسمك للحالة الحرجة:",
        'critical_phone': "الرجاء إدخال رقم هاتفك للحالة الحرجة:",
        'critical_registered': "تم تسجيل الحالة الحرجة. سيتصل بك مسؤول من {institution_name} قريباً.",
        'complaint_success': "تم تسجيل شكواك بنجاح. شكراً لتعاملك مع {institution_name}.",
        'suggestion_success': "تم تسجيل اقتراحك بنجاح. شكراً لك.",
        'restart': "لنبدأ من جديد. الرجاء إدخال اسمك الكامل:",
        'cancelled': "تم إلغاء العملية.",
        'error': "حدث خطأ. الرجاء المحاولة مرة أخرى أو التواصل مع الدعم الفني لـ {institution_name}.",
        'help_header': "مساعدة بوت {institution_name}:",
        'help_text': "هذا البوت لتسجيل الشكاوى والاقتراحات.\n\nالأوامر المتاحة:\n/complaint - تقديم شكوى\n/suggestion - تقديم اقتراح\n/contact - معلومات التواصل\n/help - المساعدة\n/cancel - إلغاء العملية الحالية",
        'suggestion_ack': "شكراً لاقتراحك. سيتم دراسته بواسطة {institution_name}.",
        'contact_header': "معلومات التواصل مع {institution_name}:",
        'contact_details': "الهاتف: {phone}\nالبريد الإلكتروني: {email}\nالعنوان: {address}",
        'complaint_intent': "يبدو أنك تريد تقديم شكوى. استخدم الأمر /complaint للبدء.",
        'suggestion_intent': "يبدو أنك تريد تقديم اقتراح. استخدم الأمر /suggestion للبدء.",
        'off_topic': "هذا البوت مخصص لتسجيل الشكاوى والاقتراحات فقط لـ {institution_name}. استخدم /help للمساعدة.",
        'invalid_name': "الرجاء إدخال اسم صحيح (3 كلمات على الأقل).",
        'invalid_phone': "الرجاء إدخال رقم هاتف صحيح.",
        'yes': 'نعم',
        'no': 'لا',
        'male': 'ذكر',
        'female': 'أنثى',
        'resident': 'مقيم',
        'idp': 'نازح',
        'returnee': 'عائد',
        'residence_explanation': "مقيم: تعيش في منطقتك الأصلية.\nنازح: انتقلت من منطقة لأخرى.\nعائد: عدت إلى منطقتك بعد نزوح."
    },
    'en': {
        'welcome': "Welcome to the {institution_name} bot.\nYou can submit a complaint or suggestion.",
        'welcome_existing': "Welcome back! Your data is saved with us for {institution_name}.",
        'use_existing_data': "Would you like to use your saved data?",
        'enter_name': "Please enter your full name:",
        'enter_sex': "Please select your gender:",
        'enter_phone': "Please enter your phone number:",
        'enter_residence': "Please select your residence status:",
        'enter_governorate': "Please enter your governorate:",
        'enter_directorate': "Please enter your directorate:",
        'enter_village': "Please enter your village/area:",
        'enter_complaint': "Please enter the details of your complaint or suggestion:",
        'confirm_submission_prompt': "Is the following information correct and ready to be submitted?",
        'complaint_summary_header': "Data Summary:",
        'critical_intro': "Your case has been classified as critical for {institution_name}. It will be handled with high priority.",
        'critical_name': "Please enter your name for the critical case:",
        'critical_phone': "Please enter your phone number for the critical case:",
        'critical_registered': "Critical case has been registered. An officer from {institution_name} will contact you soon.",
        'complaint_success': "Your complaint has been registered successfully. Thank you for contacting {institution_name}.",
        'suggestion_success': "Your suggestion has been registered successfully. Thank you.",
        'restart': "Let's start over. Please enter your full name:",
        'cancelled': "Operation cancelled.",
        'error': "An error occurred. Please try again or contact {institution_name} support.",
        'help_header': "{institution_name} Bot Help:",
        'help_text': "This bot is for registering complaints and suggestions.\n\nAvailable commands:\n/complaint - Submit a complaint\n/suggestion - Submit a suggestion\n/contact - Contact information\n/help - Help\n/cancel - Cancel current operation",
        'suggestion_ack': "Thank you for your suggestion. It will be reviewed by {institution_name}.",
        'contact_header': "Contact Information for {institution_name}:",
        'contact_details': "Phone: {phone}\nEmail: {email}\nAddress: {address}",
        'complaint_intent': "It seems you want to submit a complaint. Use the /complaint command.",
        'suggestion_intent': "It seems you want to submit a suggestion. Use the /suggestion command.",
        'off_topic': "This bot is only for registering complaints and suggestions for {institution_name}. Use /help for assistance.",
        'invalid_name': "Please enter a valid name (at least 3 words).",
        'invalid_phone': "Please enter a valid phone number.",
        'yes': 'Yes',
        'no': 'No',
        'male': 'Male',
        'female': 'Female',
        'resident': 'Resident',
        'idp': 'IDP',
        'returnee': 'Returnee',
        'residence_explanation': "Resident: You live in your original area.\nIDP: You moved from one area to another.\nReturnee: You returned to your area after displacement."
    }
}

def get_message(text_key: str, bot_instance: InstitutionBot, is_arabic: bool = True, **kwargs) -> str:
    """
    Retrieves and formats a message string.
    Prioritizes messages from `config.yaml` (`custom_messages`),
    then falls back to `DEFAULT_MESSAGES`.
    Formats the message with institution details and any additional kwargs.

    Args:
        text_key: The key for the message template.
        bot_instance: The instance of InstitutionBot to access config.
        is_arabic: Boolean indicating if the Arabic version is needed.
        **kwargs: Additional key-value pairs for formatting.

    Returns:
        The formatted message string.
    """
    lang = 'ar' if is_arabic else 'en'
    message_template = ""

    # 1. Try to get from custom messages in config
    try:
        custom_messages_config = bot_instance.config.get('custom_messages', {})
        message_template = custom_messages_config.get(lang, {}).get(text_key, "")
    except AttributeError: # bot_instance.config might not be fully populated yet
        logger.debug("Config not fully available for custom_messages lookup, or custom_messages not defined.")

    # 2. Fall back to default messages if not found in config
    if not message_template:
        message_template = DEFAULT_MESSAGES.get(lang, {}).get(text_key, f"[{text_key.upper()}_NOT_FOUND]")

    # 3. Prepare formatting arguments
    format_args = {}
    try:
        institution_config = bot_instance.config.get('institution', {})
        format_args['institution_name'] = institution_config.get('name', 'Our Institution')
        
        contact_config = institution_config.get('contact', {}) # Assuming contact info might be nested
        format_args['phone'] = contact_config.get('phone', institution_config.get('contact_phone', '[Phone]')) # Fallback for flat structure
        format_args['email'] = contact_config.get('email', institution_config.get('contact_email', '[Email]')) # Fallback for flat structure
        format_args['address'] = contact_config.get('address', institution_config.get('contact_address', '[Address]')) # Fallback for flat structure
    except AttributeError:
        logger.warning("Institution config not fully available for message formatting. Using defaults.")
        format_args.setdefault('institution_name', 'Our Institution')
        format_args.setdefault('phone', '[Phone]')
        format_args.setdefault('email', '[Email]')
        format_args.setdefault('address', '[Address]')

    format_args.update(kwargs) # Add any explicitly passed format arguments

    # 4. Format the message
    try:
        return message_template.format_map(format_args)
    except KeyError as e:
        logger.warning(f"Missing key '{e}' for formatting message_key '{text_key}'. Template: '{message_template}'")
        return message_template # Return unformatted template on error
    except Exception as e:
        logger.error(f"Error formatting message_key '{text_key}': {e}. Template: '{message_template}'")
        return message_template

# --- Keyboard Helper Functions ---
def _create_reply_keyboard(buttons: list, one_time: bool = True, resize: bool = True) -> ReplyKeyboardMarkup:
    """Helper to create ReplyKeyboardMarkup instances."""
    return ReplyKeyboardMarkup(buttons, one_time_keyboard=one_time, resize_keyboard=resize)

def get_yes_no_keyboard(bot_instance: InstitutionBot, is_arabic: bool = True) -> ReplyKeyboardMarkup:
    """Gets a Yes/No keyboard."""
    yes_text = get_message('yes', bot_instance, is_arabic)
    no_text = get_message('no', bot_instance, is_arabic)
    return _create_reply_keyboard([[KeyboardButton(yes_text), KeyboardButton(no_text)]])

def get_sex_keyboard(bot_instance: InstitutionBot, is_arabic: bool = True) -> ReplyKeyboardMarkup:
    """Gets a Male/Female keyboard."""
    male_text = get_message('male', bot_instance, is_arabic)
    female_text = get_message('female', bot_instance, is_arabic)
    return _create_reply_keyboard([[KeyboardButton(male_text), KeyboardButton(female_text)]])

def get_residence_keyboard(bot_instance: InstitutionBot, is_arabic: bool = True) -> ReplyKeyboardMarkup:
    """Gets a residence status keyboard."""
    resident_text = get_message('resident', bot_instance, is_arabic)
    idp_text = get_message('idp', bot_instance, is_arabic)
    returnee_text = get_message('returnee', bot_instance, is_arabic)
    # Presenting as single buttons per row for better tap targets on mobile
    return _create_reply_keyboard([
        [KeyboardButton(resident_text)],
        [KeyboardButton(idp_text)],
        [KeyboardButton(returnee_text)]
    ])

# --- Conversation Handler Functions ---

async def start_complaint_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    """Initiates the complaint collection process."""
    user = update.effective_user
    if not user:
        logger.warning("start_complaint_flow: No effective user found.")
        return ConversationHandler.END # Or some error state

    user_id = user.id
    message_text = update.message.text if update.message else ""
    is_arabic_input = bot_instance._is_arabic_text(message_text)

    bot_instance.user_data[user_id] = ComplaintData(user_id=user_id) # Reset/Initialize

    try:
        is_critical = await bot_instance._is_critical_complaint_llm(message_text)
        bot_instance.user_data[user_id].is_critical = is_critical
        bot_instance.user_data[user_id].original_complaint_text = message_text

        if is_critical:
            await update.message.reply_text(
                get_message('critical_intro', bot_instance, is_arabic_input),
                reply_markup=ReplyKeyboardRemove()
            )
            await update.message.reply_text(get_message('critical_name', bot_instance, is_arabic_input))
            return CRITICAL_NAME

        existing_profile = await bot_instance._check_existing_beneficiary_profile(user_id)
        if existing_profile:
            # Populate complaint_data with existing profile data
            for key, value in existing_profile.items():
                if hasattr(bot_instance.user_data[user_id], key):
                    setattr(bot_instance.user_data[user_id], key, value)
                elif key == 'village_area' and hasattr(bot_instance.user_data[user_id], 'village'): # Handle mapping
                    setattr(bot_instance.user_data[user_id], 'village', value)

            await update.message.reply_text(
                get_message('use_existing_data', bot_instance, is_arabic_input),
                reply_markup=get_yes_no_keyboard(bot_instance, is_arabic_input)
            )
            return CONFIRM_EXISTING

        await update.message.reply_text(
            get_message('enter_name', bot_instance, is_arabic_input),
            reply_markup=ReplyKeyboardRemove()
        )
        return COLLECTING_NAME

    except Exception as e:
        logger.error(f"Error in start_complaint_flow for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error', bot_instance, True)) # Default to Arabic for error
        return ConversationHandler.END


async def confirm_existing_data(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    """Handles user's response to using existing data."""
    user = update.effective_user
    if not user: return ConversationHandler.END
    
    response_text = update.message.text.strip().lower()
    is_arabic_response = bot_instance._is_arabic_text(response_text)

    if response_text == get_message('yes', bot_instance, is_arabic_response).lower():
        await update.message.reply_text(
            get_message('enter_complaint', bot_instance, is_arabic_response),
            reply_markup=ReplyKeyboardRemove()
        )
        return COLLECTING_COMPLAINT

    await update.message.reply_text(
        get_message('enter_name', bot_instance, is_arabic_response),
        reply_markup=ReplyKeyboardRemove()
    )
    return COLLECTING_NAME


async def _collect_text_input(update: Update, bot_instance: InstitutionBot, data_field: str, next_state: int,
                               prompt_key: str, keyboard_func: callable = None, validation_func: callable = None,
                               invalid_message_key: str = None) -> int:
    """Generic helper to collect simple text input."""
    user = update.effective_user
    if not user: return ConversationHandler.END
    
    user_id = user.id
    input_text = update.message.text.strip()
    is_arabic = bot_instance._is_arabic_text(input_text)

    if validation_func and not validation_func(input_text):
        if invalid_message_key:
            await update.message.reply_text(get_message(invalid_message_key, bot_instance, is_arabic))
        return getattr(sys.modules[__name__], data_field.upper()) # Return current state constant

    setattr(bot_instance.user_data[user_id], data_field, input_text)

    reply_markup = keyboard_func(bot_instance, is_arabic) if keyboard_func else ReplyKeyboardRemove()
    await update.message.reply_text(get_message(prompt_key, bot_instance, is_arabic), reply_markup=reply_markup)
    return next_state

def _validate_name(name: str) -> bool:
    return len(name.split()) >= 3

def _validate_phone(phone: str) -> bool:
    return any(char.isdigit() for char in phone) and len(phone.replace('+', '').replace('-', '').replace(' ', '')) >= 7


async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    return await _collect_text_input(update, bot_instance, 'name', COLLECTING_SEX,
                                     'enter_sex', get_sex_keyboard, _validate_name, 'invalid_name')

async def collect_sex(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    user = update.effective_user
    if not user: return ConversationHandler.END
    user_id = user.id
    sex_input = update.message.text.strip()
    is_arabic = bot_instance._is_arabic_text(sex_input)

    normalized_sex = ""
    if sex_input.lower() in [get_message('male', bot_instance, True).lower(), get_message('male', bot_instance, False).lower(), 'm']:
        normalized_sex = "Male"
    elif sex_input.lower() in [get_message('female', bot_instance, True).lower(), get_message('female', bot_instance, False).lower(), 'f']:
        normalized_sex = "Female"
    else:
        await update.message.reply_text(get_message('enter_sex', bot_instance, is_arabic),
                                        reply_markup=get_sex_keyboard(bot_instance, is_arabic))
        return COLLECTING_SEX

    bot_instance.user_data[user_id].sex = normalized_sex
    await update.message.reply_text(get_message('enter_phone', bot_instance, is_arabic),
                                    reply_markup=ReplyKeyboardRemove())
    return COLLECTING_PHONE


async def collect_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    user_id = update.effective_user.id # Keep this to ensure user_data access
    is_arabic = bot_instance._is_arabic_text(update.message.text) # Determine language for prompts
    
    # Using the generic helper for phone collection as well
    next_state_val = await _collect_text_input(
        update, bot_instance, 'phone', COLLECTING_RESIDENCE,
        'enter_residence', get_residence_keyboard, _validate_phone, 'invalid_phone'
    )
    # If validation passed and we are moving to COLLECTING_RESIDENCE, send the explanation message.
    if next_state_val == COLLECTING_RESIDENCE:
         # Send residence explanation separately if needed or integrate into prompt_key
        await update.message.reply_text(get_message('residence_explanation', bot_instance, is_arabic))
   
    return next_state_val


async def collect_residence(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    user = update.effective_user
    if not user: return ConversationHandler.END
    user_id = user.id
    residence_input = update.message.text.strip()
    is_arabic = bot_instance._is_arabic_text(residence_input)

    normalized_residence = ""
    if residence_input.lower() in [get_message('resident', bot_instance, True).lower(), get_message('resident', bot_instance, False).lower()]:
        normalized_residence = "Resident"
    elif residence_input.lower() in [get_message('idp', bot_instance, True).lower(), get_message('idp', bot_instance, False).lower()]:
        normalized_residence = "IDP"
    elif residence_input.lower() in [get_message('returnee', bot_instance, True).lower(), get_message('returnee', bot_instance, False).lower()]:
        normalized_residence = "Returnee"
    else:
        await update.message.reply_text(get_message('enter_residence', bot_instance, is_arabic),
                                        reply_markup=get_residence_keyboard(bot_instance, is_arabic))
        return COLLECTING_RESIDENCE

    bot_instance.user_data[user_id].residence_status = normalized_residence
    await update.message.reply_text(get_message('enter_governorate', bot_instance, is_arabic),
                                    reply_markup=ReplyKeyboardRemove())
    return COLLECTING_GOVERNORATE


async def collect_governorate(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    return await _collect_text_input(update, bot_instance, 'governorate', COLLECTING_DIRECTORATE, 'enter_directorate')

async def collect_directorate(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    return await _collect_text_input(update, bot_instance, 'directorate', COLLECTING_VILLAGE, 'enter_village')

async def collect_village(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    # The field in ComplaintData is 'village', but DB might be 'village_area'.
    # _collect_text_input will set 'village' on ComplaintData.
    # Mapping to 'village_area' for DB happens in _check_existing_beneficiary_profile or _save_beneficiary_profile.
    return await _collect_text_input(update, bot_instance, 'village', COLLECTING_COMPLAINT, 'enter_complaint')


async def collect_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    user = update.effective_user
    if not user: return ConversationHandler.END
    user_id = user.id
    
    complaint_data_obj = bot_instance.user_data[user_id]
    complaint_data_obj.original_complaint_text = update.message.text.strip()
    is_arabic_complaint = bot_instance._is_arabic_text(complaint_data_obj.original_complaint_text)

    try:
        complaint_data_obj.complaint_details = await bot_instance._summarize_and_translate_complaint_llm(
            complaint_data_obj.original_complaint_text
        )

        summary_parts = [
            get_message('complaint_summary_header', bot_instance, is_arabic_complaint),
            f"الاسم: {complaint_data_obj.name}" if is_arabic_complaint else f"Name: {complaint_data_obj.name}",
            f"الجنس: {complaint_data_obj.sex}" if is_arabic_complaint else f"Gender: {complaint_data_obj.sex}",
            f"الهاتف: {complaint_data_obj.phone}" if is_arabic_complaint else f"Phone: {complaint_data_obj.phone}",
            f"الوضع السكني: {complaint_data_obj.residence_status}" if is_arabic_complaint else f"Residence Status: {complaint_data_obj.residence_status}",
            f"المحافظة: {complaint_data_obj.governorate}" if is_arabic_complaint else f"Governorate: {complaint_data_obj.governorate}",
            f"المديرية: {complaint_data_obj.directorate}" if is_arabic_complaint else f"Directorate: {complaint_data_obj.directorate}",
            f"القرية/المنطقة: {complaint_data_obj.village}" if is_arabic_complaint else f"Village/Area: {complaint_data_obj.village}",
            f"الشكوى: {complaint_data_obj.original_complaint_text[:200]}{'...' if len(complaint_data_obj.original_complaint_text) > 200 else ''}"
            if is_arabic_complaint else
            f"Complaint: {complaint_data_obj.original_complaint_text[:200]}{'...' if len(complaint_data_obj.original_complaint_text) > 200 else ''}"
        ]
        confirmation_msg = "\n\n".join(filter(None, summary_parts))

        await update.message.reply_text(confirmation_msg)
        await update.message.reply_text(
            get_message('confirm_submission_prompt', bot_instance, is_arabic_complaint),
            reply_markup=get_yes_no_keyboard(bot_instance, is_arabic_complaint)
        )
        return CONFIRMING_SUBMISSION

    except Exception as e:
        logger.error(f"Error in collect_complaint for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error', bot_instance, is_arabic_complaint))
        return ConversationHandler.END


async def confirm_submission(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    user = update.effective_user
    if not user: return ConversationHandler.END
    user_id = user.id

    response_text = update.message.text.strip().lower()
    # Determine language for "yes" based on the language of the complaint or a stored preference
    # For now, use the language of the original complaint text as a proxy
    is_arabic_context = bot_instance._is_arabic_text(bot_instance.user_data[user_id].original_complaint_text)

    if response_text != get_message('yes', bot_instance, is_arabic_context).lower():
        await update.message.reply_text(
            get_message('restart', bot_instance, is_arabic_context),
            reply_markup=ReplyKeyboardRemove()
        )
        # Reset user_data for a fresh start, except user_id
        current_complaint_data = bot_instance.user_data[user_id]
        bot_instance.user_data[user_id] = ComplaintData(user_id=user_id, 
                                                        name=current_complaint_data.name, # Keep existing data if they restart from confirmation
                                                        sex=current_complaint_data.sex,
                                                        phone=current_complaint_data.phone,
                                                        residence_status=current_complaint_data.residence_status,
                                                        governorate=current_complaint_data.governorate,
                                                        directorate=current_complaint_data.directorate,
                                                        village=current_complaint_data.village)
        return COLLECTING_NAME # Or perhaps a more appropriate restart point

    try:
        complaint_data_to_log = bot_instance.user_data[user_id]
        log_successful = await bot_instance._log_complaint(complaint_data_to_log)

        if log_successful:
            # Re-classify here to determine if it was a suggestion for the success message
            # This ensures we use the latest understanding of the complaint text.
            classification = await bot_instance._classify_complaint_llm(complaint_data_to_log.original_complaint_text)
            complaint_type = classification[0].lower() if classification else "" # type is first element

            success_key = 'suggestion_success' if 'suggestion' in complaint_type else 'complaint_success'
            await update.message.reply_text(
                get_message(success_key, bot_instance, is_arabic_context),
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await update.message.reply_text(get_message('error', bot_instance, is_arabic_context), reply_markup=ReplyKeyboardRemove())

    except Exception as e:
        logger.error(f"Error during final submission for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error', bot_instance, is_arabic_context), reply_markup=ReplyKeyboardRemove())
    finally:
        if user_id in bot_instance.user_data:
            del bot_instance.user_data[user_id]
        return ConversationHandler.END


async def collect_critical_name(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    return await _collect_text_input(update, bot_instance, 'name', CRITICAL_PHONE,
                                     'critical_phone', validation_func=_validate_name,
                                     invalid_message_key='invalid_name') # Re-prompt for name if invalid


async def collect_critical_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    user = update.effective_user
    if not user: return ConversationHandler.END
    user_id = user.id
    
    phone_text = update.message.text.strip()
    is_arabic_context = bot_instance._is_arabic_text(phone_text) # Or original complaint lang

    if not _validate_phone(phone_text):
        await update.message.reply_text(get_message('invalid_phone', bot_instance, is_arabic_context))
        return CRITICAL_PHONE # Re-prompt for phone

    complaint_data_obj = bot_instance.user_data[user_id]
    complaint_data_obj.phone = phone_text

    try:
        await bot_instance._log_complaint(complaint_data_obj)
        await bot_instance._send_critical_complaint_email(complaint_data_obj)
        await update.message.reply_text(
            get_message('critical_registered', bot_instance, is_arabic_context),
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        logger.error(f"Error processing critical complaint for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error', bot_instance, is_arabic_context), reply_markup=ReplyKeyboardRemove())
    finally:
        if user_id in bot_instance.user_data:
            del bot_instance.user_data[user_id]
        return ConversationHandler.END

# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot):
    user = update.effective_user
    if not user: return
    is_arabic_default = True # Default language for initial interaction

    try:
        existing_profile = await bot_instance._check_existing_beneficiary_profile(user.id)
        welcome_key = 'welcome_existing' if existing_profile else 'welcome'
        
        # If existing_profile, we might try to guess language from their name or last interaction
        # For now, defaulting to Arabic for welcome.
        await update.message.reply_text(get_message(welcome_key, bot_instance, is_arabic_default))
    except Exception as e:
        logger.error(f"Error in start_command for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error', bot_instance, is_arabic_default))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot):
    user = update.effective_user
    if not user: return
    # Determine language preference if possible, else default
    is_arabic_default = True
    await update.message.reply_text(
        f"{get_message('help_header', bot_instance, is_arabic_default)}\n\n"
        f"{get_message('help_text', bot_instance, is_arabic_default)}"
    )


async def suggestion_command(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot):
    user = update.effective_user
    if not user: return ConversationHandler.END # Should be END if it's a one-off command
    is_arabic_default = True
    await update.message.reply_text(get_message('suggestion_ack', bot_instance, is_arabic_default))
    return ConversationHandler.END


async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot):
    user = update.effective_user
    if not user: return ConversationHandler.END
    is_arabic_default = True
    await update.message.reply_text(
        f"{get_message('contact_header', bot_instance, is_arabic_default)}\n\n"
        f"{get_message('contact_details', bot_instance, is_arabic_default)}"
    )
    return ConversationHandler.END


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    user = update.effective_user
    if not user: return ConversationHandler.END
    
    # Determine language for cancel message, perhaps from user_data if available
    is_arabic_default = True
    if user.id in bot_instance.user_data and bot_instance.user_data[user.id].original_complaint_text:
        is_arabic_default = bot_instance._is_arabic_text(bot_instance.user_data[user.id].original_complaint_text)

    if user.id in bot_instance.user_data:
        del bot_instance.user_data[user.id]
        
    await update.message.reply_text(
        get_message('cancelled', bot_instance, is_arabic_default),
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# --- General Message and Error Handlers ---

async def handle_general_message(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot):
    user = update.effective_user
    if not user or not update.message or not update.message.text: return

    user_id = user.id
    message_text = update.message.text
    is_arabic = bot_instance._is_arabic_text(message_text)

    if user_id in bot_instance.user_data: # User is in an active conversation
        # Optionally, remind them they are in a process or to use /cancel
        # For now, we let the conversation handler manage this.
        return

    try:
        intent = await bot_instance._determine_user_intent_llm(message_text)
        if intent == "COMPLAINT_INTENT":
            reply_key = 'complaint_intent'
        elif intent == "SUGGESTION_INTENT":
            reply_key = 'suggestion_intent'
        else: # Includes "CONTACT_INTENT" and "OFF_TOPIC"
            reply_key = 'off_topic'
        await update.message.reply_text(get_message(reply_key, bot_instance, is_arabic))
    except Exception as e:
        logger.error(f"Error determining user intent for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error', bot_instance, is_arabic))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Attempt to inform user if possible
    if isinstance(update, Update) and update.effective_message:
        # Try to get bot_instance from context if passed by application.add_error_handler
        # This is a common pattern but depends on how error_handler is registered.
        # For this exercise, we assume bot_instance might not be directly available here
        # without further application-level setup for context.bot_data or similar.
        # So, we send a very generic error message without language detection or config access.
        try:
            await update.effective_message.reply_text(
                "An unexpected error occurred. Please try again later.", # Generic, non-localized
                reply_markup=ReplyKeyboardRemove()
            )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")


def setup_telegram_handlers(application: Application, bot_instance: InstitutionBot) -> None:
    """Sets up all Telegram handlers for the bot application."""

    # ConversationHandler for complaint submission
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('complaint', lambda u, c: start_complaint_flow(u, c, bot_instance)),
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.Regex(r'.*(شكوى|complaint|مشكلة|problem|issue).*'), # Added "issue"
                lambda u, c: start_complaint_flow(u, c, bot_instance)
            )
        ],
        states={
            # Each state maps to a handler function
            START_COMPLAINT_FLOW: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: start_complaint_flow(u, c, bot_instance))],
            CONFIRM_EXISTING: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: confirm_existing_data(u, c, bot_instance))],
            COLLECTING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_name(u, c, bot_instance))],
            COLLECTING_SEX: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_sex(u, c, bot_instance))],
            COLLECTING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_phone(u, c, bot_instance))],
            COLLECTING_RESIDENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_residence(u, c, bot_instance))],
            COLLECTING_GOVERNORATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_governorate(u, c, bot_instance))],
            COLLECTING_DIRECTORATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_directorate(u, c, bot_instance))],
            COLLECTING_VILLAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_village(u, c, bot_instance))],
            COLLECTING_COMPLAINT: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_complaint(u, c, bot_instance))],
            CONFIRMING_SUBMISSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: confirm_submission(u, c, bot_instance))],
            CRITICAL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_critical_name(u, c, bot_instance))],
            CRITICAL_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_critical_phone(u, c, bot_instance))],
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: cancel_conversation(u, c, bot_instance))],
        allow_reentry=True
    )
    application.add_handler(conv_handler)

    # Standard command handlers
    command_handlers = {
        "start": start_command,
        "help": help_command,
        "suggestion": suggestion_command,
        "contact": contact_command
    }
    for command, handler_func in command_handlers.items():
        application.add_handler(CommandHandler(command, lambda u, c, hf=handler_func: hf(u, c, bot_instance)))

    # General message handler (must be lower priority than ConversationHandler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, 
                                           lambda u, c: handle_general_message(u, c, bot_instance)), group=1)

    # Error handler
    # Note: The error_handler ideally should get bot_instance if it needs to send localized messages.
    # This can be done by `application.bot_data['bot_instance'] = bot_instance` in main.py
    # and then `bot_instance = context.application.bot_data['bot_instance']` in error_handler.
    # For now, error_handler sends a generic non-localized message.
    application.add_error_handler(error_handler) # Pass only update and context