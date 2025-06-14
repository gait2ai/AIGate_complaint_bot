"""
AI Gate for Artificial Intelligence Applications
Telegram Handlers Module for Institution Complaint Management Bot

This module handles all Telegram-specific interactions and conversation flows,
ensuring a configurable and maintainable approach to user interactions.
It manages user input, conversation states, and invokes core bot logic.
"""

import logging
import sys  # MODIFIED: Added to resolve NameError
from datetime import datetime # For handling message.date
from typing import Dict, Any, Optional

# Telegram libraries
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)

# Core modules
from app.bot.institution_bot_logic import InstitutionBot, ComplaintData # Ensure ComplaintData dataclass is updated

# --- Conversation State Constants ---
(
    SELECTING_ACTION,       # Initial state after /start for choosing action
    # Complaint Flow States
    CONFIRM_EXISTING,
    COLLECTING_NAME,
    COLLECTING_SEX,
    COLLECTING_PHONE,
    COLLECTING_RESIDENCE,
    COLLECTING_GOVERNORATE,
    COLLECTING_DIRECTORATE,
    COLLECTING_VILLAGE,
    COLLECTING_COMPLAINT,   # State for collecting the actual complaint text
    CONFIRMING_SUBMISSION,  # State for user to confirm all complaint data
    # Critical Complaint Flow States
    CRITICAL_NAME,
    CRITICAL_PHONE,
    # Suggestion and Feedback Flow States (simplified for now)
    COLLECTING_SUGGESTION_TEXT,
    COLLECTING_FEEDBACK_TEXT
) = range(16) # Adjusted range for new states

# Logger for this module
logger = logging.getLogger(__name__)

# --- Default Messages Dictionary ---
# Serves as a fallback if messages are not defined in config.yaml's custom_messages.
# Placeholders like {institution_name} and {user_name} will be formatted by get_message.
DEFAULT_MESSAGES = {
    'ar': {
        'guest': "ضيفنا الكريم", # Fallback if user.first_name is not available
        'welcome_options': "مرحباً بك {user_name} في بوت {institution_name}.\nهذا البوت مخصص لاستقبال الشكاوى والاقتراحات والملاحظات المتعلقة بخدماتنا.\n\nالرجاء تحديد أحد الخيارات التالية:",
        'option_complaint': "📝 تقديم شكوى",
        'option_suggestion': "💡 تقديم اقتراح",
        'option_feedback': "📋 تقديم ملاحظة",
        'complaint_initiated': "جاري بدء عملية تقديم الشكوى...", # Message after clicking complaint button
        'use_existing_data': "بيانات ملفك الشخصي موجودة لدينا. هل ترغب باستخدامها (الاسم، الهاتف، إلخ)؟",
        'enter_name': "الرجاء إدخال اسمك الكامل (ثلاثة مقاطع على الأقل):",
        'enter_sex': "الرجاء تحديد جنسك:",
        'enter_phone': "الرجاء إدخال رقم هاتفك (مع رمز الدولة إذا كنت خارج البلاد):",
        'enter_residence': "الرجاء تحديد وضع إقامتك الحالي:",
        'enter_governorate': "الرجاء إدخال اسم المحافظة:",
        'enter_directorate': "الرجاء إدخال اسم المديرية:",
        'enter_village': "الرجاء إدخال اسم القرية أو المنطقة:",
        'enter_complaint_details': "الآن، يرجى كتابة تفاصيل شكواك بوضوح:", # Renamed for clarity
        'enter_suggestion_details': "يرجى كتابة تفاصيل اقتراحك:",
        'enter_feedback_details': "يرجى كتابة ملاحظاتك:",
        'confirm_submission_prompt': "البيانات التي أدخلتها جاهزة للإرسال. هل تؤكد الإرسال؟",
        'complaint_summary_header': "📋 ملخص البيانات:",
        'name_label': "الاسم", 'sex_label': "الجنس", 'phone_label': "الهاتف",
        'residence_label': "الإقامة", 'governorate_label': "المحافظة",
        'directorate_label': "المديرية", 'village_label': "القرية/المنطقة",
        'complaint_text_label': "نص الشكوى", # For summary
        'critical_intro': "تنبيه: تم تحديد شكواك كحالة قد تكون حرجة. سيتم التعامل معها بأولوية من قبل فريق {institution_name}.",
        'critical_name': "للحالات الحرجة، يرجى تأكيد أو إدخال اسمك:",
        'critical_phone': "للحالات الحرجة، يرجى تأكيد أو إدخال رقم هاتفك:",
        'critical_registered': "تم تسجيل الحالة الحرجة بنجاح. سيتواصل معك أحد موظفي {institution_name} في أقرب وقت ممكن.",
        'complaint_success': "شكراً لك! تم استلام شكواك بنجاح وسيتم مراجعتها من قبل فريق {institution_name}.",
        'suggestion_success': "شكراً لك! تم استلام اقتراحك وسيؤخذ بعين الاعتبار.",
        'feedback_success': "شكراً لك! تم استلام ملاحظاتك.",
        'restart_data_entry': "تم إلغاء الإدخال الحالي. لنبدأ من جديد بجمع بياناتك.",
        'cancelled': "تم إلغاء العملية الحالية. يمكنك البدء من جديد باستخدام /start.",
        'error': "عفواً، حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى لاحقاً. إذا استمرت المشكلة، يمكنك التواصل مع دعم {institution_name}.",
        'help_header': "مساعدة بوت {institution_name}",
        'help_text': "يمكنك استخدام هذا البوت لتقديم:\n- شكوى (/complaint)\n- اقتراح (/suggestion)\n- ملاحظة (/feedback)\n\nأوامر أخرى:\n/start - عرض الخيارات الرئيسية\n/contact - معلومات الاتصال بالمؤسسة\n/cancel - إلغاء أي عملية جارية",
        'contact_header': "معلومات التواصل مع {institution_name}",
        'contact_details': "الهاتف: {phone}\nالبريد الإلكتروني: {email}\nالعنوان: {address}",
        'complaint_intent_detected': "أهلاً بك. إذا كنت ترغب في تقديم شكوى، يمكنك اختيار 'تقديم شكوى' من القائمة أو استخدام الأمر /complaint.",
        'suggestion_intent_detected': "أهلاً بك. إذا كنت ترغب في تقديم اقتراح، يمكنك اختيار 'تقديم اقتراح' من القائمة أو استخدام الأمر /suggestion.",
        'contact_intent_detected': "أهلاً بك! إذا كنت تبحث عن معلومات الاتصال الخاصة بـ {institution_name}، يمكنك استخدام الأمر /contact مباشرة.",
        'off_topic': "مرحباً! هذا البوت مخصص لاستقبال الشكاوى، الاقتراحات، والملاحظات المتعلقة بخدمات {institution_name}. للمساعدة، استخدم الأمر /help.",
        'invalid_name': "الاسم المدخل غير صحيح. يرجى إدخال اسم ثلاثي على الأقل.",
        'invalid_phone': "رقم الهاتف المدخل غير صحيح. يرجى التأكد من إدخال رقم هاتف صالح.",
        'yes': 'نعم', 'no': 'لا', 'male': 'ذكر', 'female': 'أنثى',
        'resident': 'مقيم', 'idp': 'نازح', 'returnee': 'عائد',
        'residence_explanation': "مقيم: تعيش في منطقتك الأصلية.\nنازح: انتقلت من منطقة سكنك الأصلية بسبب الظروف.\nعائد: عدت إلى منطقة سكنك الأصلية بعد فترة نزوح."
    },
    'en': {
        'guest': "Guest",
        'welcome_options': "Welcome {user_name} to the {institution_name} bot.\nThis bot is for submitting complaints, suggestions, and feedback regarding our services.\n\nPlease select one of the following options:",
        'option_complaint': "📝 Submit Complaint",
        'option_suggestion': "💡 Submit Suggestion",
        'option_feedback': "📋 Submit Feedback",
        'complaint_initiated': "Starting the complaint submission process...",
        'use_existing_data': "We have your profile data (Name, Phone, etc.). Would you like to use it?",
        'enter_name': "Please enter your full name (at least two words):",
        'enter_sex': "Please select your gender:",
        'enter_phone': "Please enter your phone number (include country code if international):",
        'enter_residence': "Please select your current residency status:",
        'enter_governorate': "Please enter your governorate:",
        'enter_directorate': "Please enter your directorate/district:",
        'enter_village': "Please enter your village or area:",
        'enter_complaint_details': "Now, please clearly describe the details of your complaint:",
        'enter_suggestion_details': "Please describe your suggestion:",
        'enter_feedback_details': "Please provide your feedback:",
        'confirm_submission_prompt': "The data you entered is ready for submission. Do you confirm?",
        'complaint_summary_header': "📋 Data Summary:",
        'name_label': "Name", 'sex_label': "Gender", 'phone_label': "Phone",
        'residence_label': "Residency", 'governorate_label': "Governorate",
        'directorate_label': "Directorate", 'village_label': "Village/Area",
        'complaint_text_label': "Complaint Text",
        'critical_intro': "Attention: Your submission has been identified as a potentially critical case. It will be prioritized by the {institution_name} team.",
        'critical_name': "For critical cases, please confirm or enter your name:",
        'critical_phone': "For critical cases, please confirm or enter your phone number:",
        'critical_registered': "The critical case has been successfully registered. A representative from {institution_name} will contact you shortly.",
        'complaint_success': "Thank you! Your complaint has been successfully received and will be reviewed by the {institution_name} team.",
        'suggestion_success': "Thank you! Your suggestion has been received and will be considered.",
        'feedback_success': "Thank you! Your feedback has been received.",
        'restart_data_entry': "Current data entry cancelled. Let's start over with your information.",
        'cancelled': "The current operation has been cancelled. You can start again using /start.",
        'error': "Sorry, an unexpected error occurred. Please try again later. If the problem persists, you can contact {institution_name} support.",
        'help_header': "{institution_name} Bot Help",
        'help_text': "You can use this bot to:\n- Submit a Complaint (/complaint)\n- Submit a Suggestion (/suggestion)\n- Submit Feedback (/feedback)\n\nOther commands:\n/start - Show main options\n/contact - Institution contact information\n/cancel - Cancel any ongoing operation",
        'contact_header': "Contact Information for {institution_name}",
        'contact_details': "Phone: {phone}\nEmail: {email}\nAddress: {address}",
        'complaint_intent_detected': "Welcome. If you wish to submit a complaint, you can select 'Submit Complaint' from the menu or use the /complaint command.",
        'suggestion_intent_detected': "Welcome. If you wish to submit a suggestion, you can select 'Submit Suggestion' from the menu or use the /suggestion command.",
        'contact_intent_detected': "Welcome! If you're looking for contact information for {institution_name}, you can use the /contact command directly.",
        'off_topic': "Hello! This bot is for receiving complaints, suggestions, and feedback related to {institution_name} services. For help, use the /help command.",
        'invalid_name': "The name entered is not valid. Please enter at least two words for your name.",
        'invalid_phone': "The phone number entered is not valid. Please ensure you enter a valid phone number.",
        'yes': 'Yes', 'no': 'No', 'male': 'Male', 'female': 'Female',
        'resident': 'Resident', 'idp': 'IDP', 'returnee': 'Returnee',
        'residence_explanation': "Resident: You live in your original area.\nIDP: You moved from your original area due to circumstances.\nReturnee: You returned to your original area after a period of displacement."
    }
}

# --- Utility Functions ---

def get_user_preferred_language_is_arabic(update: Update, bot_instance: InstitutionBot) -> bool:
    """
    Determines if the user's preferred reply language is Arabic.
    Priority: User's Telegram language_code -> Institution's primary_language from config -> Default (Arabic).
    """
    user = update.effective_user
    user_lang_code: Optional[str] = None

    if user and hasattr(user, 'language_code') and user.language_code:
        user_lang_code = user.language_code.lower()

    if user_lang_code:
        if user_lang_code.startswith('ar'):
            return True
        elif user_lang_code.startswith('en'): # Assuming English is the primary non-Arabic supported
            return False
        # For other user language codes (e.g., 'fr', 'es'), if not explicitly handled as
        # a supported non-Arabic language, behavior will fall through to institution's primary language.

    # Fallback to institution's primary language from config.yaml
    # Defaults to 'ar' if 'primary_language' is not set in config.
    primary_lang = bot_instance.config.get('institution', {}).get('primary_language', 'ar')
    return primary_lang.lower() == 'ar'


def get_message(text_key: str, bot_instance: InstitutionBot, is_arabic_reply: bool, default_fallback: Optional[str] = None, **kwargs) -> str:
    """
    Retrieves and formats a message string.
    Prioritizes messages from `config.yaml` (`custom_messages`), then `DEFAULT_MESSAGES`.
    Formats with institution details (language-specific name) and other kwargs.
    """
    lang = 'ar' if is_arabic_reply else 'en'
    message_template = ""

    try:
        custom_messages_config = bot_instance.config.get('custom_messages', {})
        message_template = custom_messages_config.get(lang, {}).get(text_key, "")
    except AttributeError:
        logger.debug("Config not fully available for custom_messages lookup.")

    if not message_template:
        message_template = DEFAULT_MESSAGES.get(lang, {}).get(text_key, default_fallback or f"[{text_key.upper()}_MSG_NOT_FOUND]")

    format_args = {}
    try:
        institution_config = bot_instance.config.get('institution', {})
        if is_arabic_reply and institution_config.get('name_ar'):
            format_args['institution_name'] = institution_config.get('name_ar')
        else:
            format_args['institution_name'] = institution_config.get('name', 'Our Institution') # Fallback

        contact_config = institution_config.get('contact', {})
        format_args['phone'] = contact_config.get('phone', '[Phone]')
        format_args['email'] = contact_config.get('email', '[Email]')
        format_args['address'] = contact_config.get('address', '[Address]')
    except AttributeError:
        logger.warning("Institution config not fully available for message formatting. Using defaults.")
        format_args.setdefault('institution_name', 'Our Institution')
        format_args.setdefault('phone', '[Phone]')
        format_args.setdefault('email', '[Email]')
        format_args.setdefault('address', '[Address]')

    format_args.update(kwargs)

    try:
        return message_template.format_map(format_args)
    except KeyError as e:
        logger.warning(f"Missing key '{e}' for formatting message_key '{text_key}'. Template: '{message_template}'")
        return message_template # Return unformatted on error
    except Exception as e:
        logger.error(f"Error formatting message_key '{text_key}': {e}. Template: '{message_template}'")
        return message_template

# --- Keyboard Helper Functions ---

def _create_reply_keyboard(buttons: list, one_time: bool = True, resize: bool = True) -> ReplyKeyboardMarkup:
    """Helper to create ReplyKeyboardMarkup instances for text-based choices."""
    return ReplyKeyboardMarkup(buttons, one_time_keyboard=one_time, resize_keyboard=resize)

def get_yes_no_keyboard(bot_instance: InstitutionBot, is_arabic_reply: bool) -> ReplyKeyboardMarkup:
    """Gets a Yes/No ReplyKeyboardMarkup."""
    yes_text = get_message('yes', bot_instance, is_arabic_reply)
    no_text = get_message('no', bot_instance, is_arabic_reply)
    return _create_reply_keyboard([[KeyboardButton(yes_text), KeyboardButton(no_text)]])

def get_sex_keyboard(bot_instance: InstitutionBot, is_arabic_reply: bool) -> ReplyKeyboardMarkup:
    """Gets a Male/Female ReplyKeyboardMarkup."""
    male_text = get_message('male', bot_instance, is_arabic_reply)
    female_text = get_message('female', bot_instance, is_arabic_reply)
    return _create_reply_keyboard([[KeyboardButton(male_text), KeyboardButton(female_text)]])

def get_residence_keyboard(bot_instance: InstitutionBot, is_arabic_reply: bool) -> ReplyKeyboardMarkup:
    """Gets a residence status ReplyKeyboardMarkup."""
    resident_text = get_message('resident', bot_instance, is_arabic_reply)
    idp_text = get_message('idp', bot_instance, is_arabic_reply)
    returnee_text = get_message('returnee', bot_instance, is_arabic_reply)
    return _create_reply_keyboard([
        [KeyboardButton(resident_text)],
        [KeyboardButton(idp_text)],
        [KeyboardButton(returnee_text)]
    ])

# --- Initial Interaction & Action Selection ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    """
    Handles the /start command. Presents initial action options (Complaint, Suggestion, Feedback)
    to the user using an InlineKeyboardMarkup. This is the main entry point.
    """
    user = update.effective_user
    if not user:
        logger.warning("start_command: No effective user.")
        # Attempt to send an error message if possible, though update.message might be None
        if update.effective_message:
             await update.effective_message.reply_text("Error: Could not identify user.")
        return ConversationHandler.END

    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
    user_name = user.first_name if user.first_name else get_message('guest', bot_instance, is_arabic_reply)

    keyboard = [
        [InlineKeyboardButton(get_message('option_complaint', bot_instance, is_arabic_reply), callback_data='action:complaint')],
        [InlineKeyboardButton(get_message('option_suggestion', bot_instance, is_arabic_reply), callback_data='action:suggestion')],
        [InlineKeyboardButton(get_message('option_feedback', bot_instance, is_arabic_reply), callback_data='action:feedback')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = get_message('welcome_options', bot_instance, is_arabic_reply, user_name=user_name)

    # Clear previous user-specific data for a clean start if they re-issue /start
    if user.id in bot_instance.user_data:
        del bot_instance.user_data[user.id]
    if context.user_data: # PTB's conversation context
        context.user_data.clear()

    # Send the welcome message with options
    if update.message: # Typical /start command
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    elif update.callback_query: # If /start is triggered from a callback (e.g., after /cancel)
        # Edit the message that had the previous buttons, or send a new one if not possible.
        try:
            await update.callback_query.edit_message_text(text=welcome_text, reply_markup=reply_markup)
        except Exception: # If edit fails (e.g. message too old), send new.
            await update.callback_query.message.reply_text(welcome_text, reply_markup=reply_markup)
        await update.callback_query.answer() # Always answer callback queries

    return SELECTING_ACTION # Transition to state waiting for button press

async def handle_action_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> Optional[int]:
    """
    Handles user's selection from the initial InlineKeyboard (Complaint, Suggestion, Feedback).
    Triggered by a CallbackQueryHandler.
    """
    query = update.callback_query
    if not query: return ConversationHandler.END
    await query.answer() # Acknowledge button press

    user = query.from_user
    if not user:
        logger.warning("handle_action_selection: No user in callback_query.")
        return ConversationHandler.END

    user_id = user.id
    action = query.data # e.g., "action:complaint"
    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)

    # Initialize ComplaintData for the user for any action.
    # It will store original_complaint_text which can be complaint, suggestion, or feedback.
    bot_instance.user_data[user_id] = ComplaintData(user_id=user_id)
    context.user_data['_current_conversation_type'] = action # Store action type for context

    # Edit the message to remove buttons and show a transition message.
    transition_message_key = ""
    next_state = ConversationHandler.END # Default

    if action == "action:complaint":
        # For complaints, we'll start the full data collection flow.
        # The start_complaint_flow will send the first data collection prompt.
        # No need to edit message here, start_complaint_flow will send a new one.
        return await start_complaint_flow(update, context, bot_instance)
    elif action == "action:suggestion":
        transition_message_key = 'enter_suggestion_details'
        next_state = COLLECTING_SUGGESTION_TEXT
    elif action == "action:feedback":
        transition_message_key = 'enter_feedback_details'
        next_state = COLLECTING_FEEDBACK_TEXT
    else:
        logger.warning(f"Unknown action selected: {action} by user {user_id}")
        await query.edit_message_text(text=get_message('error', bot_instance, is_arabic_reply))
        return ConversationHandler.END

    # For suggestion/feedback, prompt for details
    if transition_message_key:
        await query.edit_message_text(text=get_message(transition_message_key, bot_instance, is_arabic_reply))
    return next_state


# --- Complaint Conversation Handler Functions ---

async def start_complaint_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    """
    Initiates the full complaint data collection process.
    Called after user selects "Submit Complaint" or via direct /complaint command.
    """
    user = update.effective_user
    if not user:
        logger.warning("start_complaint_flow: No effective user.")
        if update.callback_query: await update.callback_query.answer()
        return ConversationHandler.END

    user_id = user.id
    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)

    # Ensure ComplaintData is initialized
    if user_id not in bot_instance.user_data:
        bot_instance.user_data[user_id] = ComplaintData(user_id=user_id)
    context.user_data['_current_conversation_type'] = "action:complaint" # Mark as complaint flow

    # Determine how to reply (new message or edit if from callback)
    reply_func = update.message.reply_text if update.message else update.callback_query.message.reply_text
    if update.callback_query: # Edit the "options" message to "complaint initiated"
        try:
            await update.callback_query.edit_message_text(text=get_message('complaint_initiated', bot_instance, is_arabic_reply))
        except Exception as e:
            logger.debug(f"Could not edit message in start_complaint_flow: {e}. Will send new.")


    # Check for existing profile
    existing_profile = await bot_instance._check_existing_beneficiary_profile(user_id)
    if existing_profile:
        # Populate ComplaintData with existing profile data
        for key, value in existing_profile.items():
            if hasattr(bot_instance.user_data[user_id], key):
                setattr(bot_instance.user_data[user_id], key, value)
            elif key == 'village_area' and hasattr(bot_instance.user_data[user_id], 'village'):
                setattr(bot_instance.user_data[user_id], 'village', value)
        # Send message using reply_func to handle both command and callback scenarios
        await reply_func(
            get_message('use_existing_data', bot_instance, is_arabic_reply),
            reply_markup=get_yes_no_keyboard(bot_instance, is_arabic_reply)
        )
        context.user_data['_current_state_for_reentry_'] = CONFIRM_EXISTING
        return CONFIRM_EXISTING

    # If no existing profile, start collecting name
    await reply_func(
        get_message('enter_name', bot_instance, is_arabic_reply),
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data['_current_state_for_reentry_'] = COLLECTING_NAME
    return COLLECTING_NAME

async def confirm_existing_data(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    """Handles user's response (Yes/No) to using existing profile data."""
    user = update.effective_user
    if not user: return ConversationHandler.END

    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
    response_text = update.message.text.strip().lower()

    if response_text == get_message('yes', bot_instance, is_arabic_reply).lower():
        # User wants to use existing data, ask for complaint details
        await update.message.reply_text(
            get_message('enter_complaint_details', bot_instance, is_arabic_reply),
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['_current_state_for_reentry_'] = COLLECTING_COMPLAINT
        return COLLECTING_COMPLAINT

    # User said No or gave an unrecognized response, start collecting data from scratch
    await update.message.reply_text(
        get_message('enter_name', bot_instance, is_arabic_reply),
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data['_current_state_for_reentry_'] = COLLECTING_NAME
    return COLLECTING_NAME

# Generic input collection and individual data collection functions
# (collect_name, collect_sex, etc. use _collect_text_input)

async def _collect_text_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot,
    data_field: str, next_state_constant: int, prompt_key: str,
    keyboard_func: Optional[callable] = None, validation_func: Optional[callable] = None,
    invalid_message_key: Optional[str] = None
) -> int:
    """Generic helper to collect simple text input and transition to next state."""
    user = update.effective_user
    if not user: return ConversationHandler.END
    user_id = user.id

    if not update.message or not update.message.text:
        logger.warning(f"_collect_text_input called without message.text for user {user_id}, field {data_field}")
        # Attempt to re-prompt gracefully or end if state is unrecoverable
        is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
        await update.effective_message.reply_text(get_message('error', bot_instance, is_arabic_reply))
        return ConversationHandler.END # Or return current state if re-prompt is complex

    input_text = update.message.text.strip()
    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance) # For reply messages

    # Perform validation if a validation function is provided
    if validation_func and not validation_func(input_text):
        if invalid_message_key:
            await update.message.reply_text(get_message(invalid_message_key, bot_instance, is_arabic_reply))
        else: # Send the original prompt again if no specific invalid message
            original_prompt_markup = keyboard_func(bot_instance, is_arabic_reply) if keyboard_func else ReplyKeyboardRemove()
            await update.message.reply_text(get_message(prompt_key, bot_instance, is_arabic_reply), reply_markup=original_prompt_markup)
        return context.user_data['_current_state_for_reentry_'] # Stay in current state (re-prompted)

    # Store data
    if user_id not in bot_instance.user_data:
        logger.warning(f"User data for {user_id} missing in _collect_text_input. Initializing.")
        bot_instance.user_data[user_id] = ComplaintData(user_id=user_id)
    setattr(bot_instance.user_data[user_id], data_field, input_text)

    # Prepare for next state
    context.user_data['_current_state_for_reentry_'] = next_state_constant
    reply_markup_next = keyboard_func(bot_instance, is_arabic_reply) if keyboard_func else ReplyKeyboardRemove()
    await update.message.reply_text(get_message(prompt_key, bot_instance, is_arabic_reply), reply_markup=reply_markup_next)
    return next_state_constant

def _validate_name(name: str) -> bool:
    """Validates name: at least two words."""
    return len(name.split()) >= 2

def _validate_phone(phone: str) -> bool:
    """Validates phone: contains digits and has a minimum length after stripping non-digits."""
    return any(char.isdigit() for char in phone) and len(re.sub(r'\D', '', phone)) >= 7

# Specific data collection handlers
async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    context.user_data['_current_state_for_reentry_'] = COLLECTING_NAME
    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
    return await _collect_text_input(update, context, bot_instance, 'name', COLLECTING_SEX,
                                     'enter_sex', lambda bi, ar: get_sex_keyboard(bi, ar),
                                     _validate_name, 'invalid_name')

async def collect_sex(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    user = update.effective_user
    if not user: return ConversationHandler.END
    user_id = user.id
    context.user_data['_current_state_for_reentry_'] = COLLECTING_SEX
    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
    sex_input = update.message.text.strip()

    # Robust check against localized options
    male_ar = get_message('male', bot_instance, True).lower()
    male_en = get_message('male', bot_instance, False).lower()
    female_ar = get_message('female', bot_instance, True).lower()
    female_en = get_message('female', bot_instance, False).lower()

    normalized_sex = ""
    if sex_input.lower() in [male_ar, male_en, 'm', 'male']: # Added 'male' for direct EN input
        normalized_sex = "Male"
    elif sex_input.lower() in [female_ar, female_en, 'f', 'female']: # Added 'female'
        normalized_sex = "Female"
    else:
        await update.message.reply_text(get_message('enter_sex', bot_instance, is_arabic_reply),
                                        reply_markup=get_sex_keyboard(bot_instance, is_arabic_reply))
        return COLLECTING_SEX # Stay in current state

    if user_id not in bot_instance.user_data: bot_instance.user_data[user_id] = ComplaintData(user_id=user_id)
    bot_instance.user_data[user_id].sex = normalized_sex
    await update.message.reply_text(get_message('enter_phone', bot_instance, is_arabic_reply),
                                    reply_markup=ReplyKeyboardRemove())
    context.user_data['_current_state_for_reentry_'] = COLLECTING_PHONE
    return COLLECTING_PHONE

async def collect_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    context.user_data['_current_state_for_reentry_'] = COLLECTING_PHONE
    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
    next_state_val = await _collect_text_input(
        update, context, bot_instance, 'phone', COLLECTING_RESIDENCE,
        'enter_residence', lambda bi, ar: get_residence_keyboard(bi, ar),
        _validate_phone, 'invalid_phone'
    )
    if next_state_val == COLLECTING_RESIDENCE:
        await update.message.reply_text(get_message('residence_explanation', bot_instance, is_arabic_reply))
    return next_state_val

async def collect_residence(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    user = update.effective_user
    if not user: return ConversationHandler.END
    user_id = user.id
    context.user_data['_current_state_for_reentry_'] = COLLECTING_RESIDENCE
    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
    residence_input = update.message.text.strip()

    resident_ar = get_message('resident', bot_instance, True).lower()
    resident_en = get_message('resident', bot_instance, False).lower()
    idp_ar = get_message('idp', bot_instance, True).lower()
    idp_en = get_message('idp', bot_instance, False).lower()
    returnee_ar = get_message('returnee', bot_instance, True).lower()
    returnee_en = get_message('returnee', bot_instance, False).lower()

    normalized_residence = ""
    if residence_input.lower() in [resident_ar, resident_en]:
        normalized_residence = "Resident"
    elif residence_input.lower() in [idp_ar, idp_en]:
        normalized_residence = "IDP"
    elif residence_input.lower() in [returnee_ar, returnee_en]:
        normalized_residence = "Returnee"
    else:
        await update.message.reply_text(get_message('enter_residence', bot_instance, is_arabic_reply),
                                        reply_markup=get_residence_keyboard(bot_instance, is_arabic_reply))
        return COLLECTING_RESIDENCE

    if user_id not in bot_instance.user_data: bot_instance.user_data[user_id] = ComplaintData(user_id=user_id)
    bot_instance.user_data[user_id].residence_status = normalized_residence
    await update.message.reply_text(get_message('enter_governorate', bot_instance, is_arabic_reply),
                                    reply_markup=ReplyKeyboardRemove())
    context.user_data['_current_state_for_reentry_'] = COLLECTING_GOVERNORATE
    return COLLECTING_GOVERNORATE

async def collect_governorate(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    context.user_data['_current_state_for_reentry_'] = COLLECTING_GOVERNORATE
    return await _collect_text_input(update, context, bot_instance, 'governorate', COLLECTING_DIRECTORATE, 'enter_directorate')

async def collect_directorate(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    context.user_data['_current_state_for_reentry_'] = COLLECTING_DIRECTORATE
    return await _collect_text_input(update, context, bot_instance, 'directorate', COLLECTING_VILLAGE, 'enter_village')

async def collect_village(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    context.user_data['_current_state_for_reentry_'] = COLLECTING_VILLAGE
    return await _collect_text_input(update, context, bot_instance, 'village', COLLECTING_COMPLAINT, 'enter_complaint_details')


# Combined handler for complaint, suggestion, feedback text
async def collect_main_text(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    """
    Collects the main descriptive text for a complaint, suggestion, or feedback.
    Also handles storing the Telegram message date.
    """
    user = update.effective_user
    if not user: return ConversationHandler.END
    user_id = user.id

    if user_id not in bot_instance.user_data:
        logger.error(f"User_data for {user_id} missing in collect_main_text.")
        is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
        await update.message.reply_text(get_message('error', bot_instance, is_arabic_reply))
        return ConversationHandler.END

    complaint_data_obj = bot_instance.user_data[user_id]
    complaint_data_obj.original_complaint_text = update.message.text.strip()

    # Store Telegram message date
    if update.message and hasattr(update.message, 'date'):
        msg_date = update.message.date
        if isinstance(msg_date, int): # Unix timestamp
            complaint_data_obj.telegram_message_date = datetime.fromtimestamp(msg_date)
        elif isinstance(msg_date, datetime):
            complaint_data_obj.telegram_message_date = msg_date
        else: # Fallback
            complaint_data_obj.telegram_message_date = datetime.now()
    else: # Fallback if no message.date (e.g., if called from a non-message update)
        complaint_data_obj.telegram_message_date = datetime.now()

    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
    conversation_type = context.user_data.get('_current_conversation_type', 'action:complaint') # Default to complaint

    # If it's a full complaint, proceed to confirmation.
    if conversation_type == "action:complaint":
        try:
            # Perform pre-critical check now that we have the complaint text
            complaint_data_obj.is_critical = await bot_instance._is_critical_complaint_llm(complaint_data_obj.original_complaint_text)

            if complaint_data_obj.is_critical:
                # Transition to critical flow, ask for name/phone again for confirmation for critical cases
                # We need to pass the complaint_text to this flow if it's designed to take it.
                # For now, it implies a slightly different data collection for critical.
                # Let's directly use the existing critical flow states.
                # We have name/phone already, but critical flow might re-confirm.
                # This needs careful state management if critical flow is very different.
                # A simpler approach for now: if critical, skip full summary, log with what we have.
                # OR, if critical flow just needs name/phone + complaint text:
                await update.message.reply_text(get_message('critical_intro', bot_instance, is_arabic_reply))
                await update.message.reply_text(get_message('critical_name', bot_instance, is_arabic_reply))
                context.user_data['_current_state_for_reentry_'] = CRITICAL_NAME
                return CRITICAL_NAME


            # Summarize/translate if it's a complaint and likely to be in Arabic for the summary display
            if bot_instance._is_arabic_text(complaint_data_obj.original_complaint_text):
                complaint_data_obj.complaint_details = await bot_instance._summarize_and_translate_complaint_llm(
                    complaint_data_obj.original_complaint_text
                )
            else:
                complaint_data_obj.complaint_details = complaint_data_obj.original_complaint_text

            summary_parts = [
                get_message('complaint_summary_header', bot_instance, is_arabic_reply),
                f"{get_message('name_label', bot_instance, is_arabic_reply)}: {complaint_data_obj.name}",
                f"{get_message('sex_label', bot_instance, is_arabic_reply)}: {complaint_data_obj.sex}",
                f"{get_message('phone_label', bot_instance, is_arabic_reply)}: {complaint_data_obj.phone}",
                # Add other fields to summary as needed
                f"{get_message('complaint_text_label', bot_instance, is_arabic_reply)}: {complaint_data_obj.original_complaint_text[:200]}"
            ]
            await update.message.reply_text("\n".join(summary_parts))
            await update.message.reply_text(
                get_message('confirm_submission_prompt', bot_instance, is_arabic_reply),
                reply_markup=get_yes_no_keyboard(bot_instance, is_arabic_reply)
            )
            context.user_data['_current_state_for_reentry_'] = CONFIRMING_SUBMISSION
            return CONFIRMING_SUBMISSION
        except Exception as e:
            logger.error(f"Error in collect_main_text (complaint summary) for user {user_id}: {e}", exc_info=True)
            await update.message.reply_text(get_message('error', bot_instance, is_arabic_reply))
            return ConversationHandler.END
    else:
        # For suggestions or feedback, log directly after collecting text
        success_key = 'suggestion_success' if conversation_type == "action:suggestion" else 'feedback_success'
        try:
            # Ensure basic data is there for _log_complaint
            complaint_data_obj.is_critical = False # Suggestions/feedback are not critical by default

            log_successful = await bot_instance._log_complaint(complaint_data_obj)
            if log_successful:
                await update.message.reply_text(
                    get_message(success_key, bot_instance, is_arabic_reply),
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(get_message('error', bot_instance, is_arabic_reply), reply_markup=ReplyKeyboardRemove())
        except Exception as e:
            logger.error(f"Error logging {conversation_type} for user {user_id}: {e}", exc_info=True)
            await update.message.reply_text(get_message('error', bot_instance, is_arabic_reply), reply_markup=ReplyKeyboardRemove())
        finally:
            if user_id in bot_instance.user_data: del bot_instance.user_data[user_id]
            if context.user_data: context.user_data.clear()
            return ConversationHandler.END

async def confirm_submission(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    """Handles user's confirmation (Yes/No) to submit the full complaint data."""
    user = update.effective_user
    if not user: return ConversationHandler.END
    user_id = user.id

    if user_id not in bot_instance.user_data: # Should not happen if flow is correct
        logger.error(f"User_data for {user_id} missing in confirm_submission.")
        is_arabic_reply_error = get_user_preferred_language_is_arabic(update, bot_instance)
        await update.message.reply_text(get_message('error', bot_instance, is_arabic_reply_error))
        return ConversationHandler.END

    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
    response_text = update.message.text.strip().lower()

    if response_text != get_message('yes', bot_instance, is_arabic_reply).lower():
        await update.message.reply_text(
            get_message('restart_data_entry', bot_instance, is_arabic_reply),
            reply_markup=ReplyKeyboardRemove()
        )
        # Preserve essential parts of ComplaintData if restarting
        current_data = bot_instance.user_data[user_id]
        bot_instance.user_data[user_id] = ComplaintData(
            user_id=user_id,
            original_complaint_text=current_data.original_complaint_text,
            is_critical=current_data.is_critical,
            telegram_message_date=current_data.telegram_message_date
        )
        await update.message.reply_text(get_message('enter_name', bot_instance, is_arabic_reply))
        context.user_data['_current_state_for_reentry_'] = COLLECTING_NAME
        return COLLECTING_NAME

    # User confirmed "Yes"
    try:
        complaint_data_to_log = bot_instance.user_data[user_id]
        log_successful = await bot_instance._log_complaint(complaint_data_to_log)

        if log_successful:
            await update.message.reply_text(
                get_message('complaint_success', bot_instance, is_arabic_reply),
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await update.message.reply_text(get_message('error', bot_instance, is_arabic_reply), reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        logger.error(f"Error during final submission for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error', bot_instance, is_arabic_reply), reply_markup=ReplyKeyboardRemove())
    finally:
        if user_id in bot_instance.user_data: del bot_instance.user_data[user_id]
        if context.user_data: context.user_data.clear()
        return ConversationHandler.END

# Critical case handlers
async def collect_critical_name(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    context.user_data['_current_state_for_reentry_'] = CRITICAL_NAME
    return await _collect_text_input(update, context, bot_instance, 'name', CRITICAL_PHONE,
                                     'critical_phone', validation_func=_validate_name,
                                     invalid_message_key='invalid_name')

async def collect_critical_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    user = update.effective_user
    if not user: return ConversationHandler.END
    user_id = user.id
    context.user_data['_current_state_for_reentry_'] = CRITICAL_PHONE
    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
    phone_text = update.message.text.strip()

    if not _validate_phone(phone_text):
        await update.message.reply_text(get_message('invalid_phone', bot_instance, is_arabic_reply))
        return CRITICAL_PHONE

    if user_id not in bot_instance.user_data:
        logger.error(f"User data for {user_id} missing in collect_critical_phone.")
        await update.message.reply_text(get_message('error', bot_instance, is_arabic_reply))
        return ConversationHandler.END

    complaint_data_obj = bot_instance.user_data[user_id]
    complaint_data_obj.phone = phone_text
    # Name was collected in CRITICAL_NAME state
    # original_complaint_text and is_critical were set when critical flow started

    try:
        log_successful = await bot_instance._log_complaint(complaint_data_obj)
        if log_successful:
            # Optional: await bot_instance._send_critical_complaint_email(complaint_data_obj)
            await update.message.reply_text(
                get_message('critical_registered', bot_instance, is_arabic_reply),
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await update.message.reply_text(get_message('error', bot_instance, is_arabic_reply), reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        logger.error(f"Error processing critical complaint for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error', bot_instance, is_arabic_reply), reply_markup=ReplyKeyboardRemove())
    finally:
        if user_id in bot_instance.user_data: del bot_instance.user_data[user_id]
        if context.user_data: context.user_data.clear()
        return ConversationHandler.END

# --- Standard Command Handlers (Non-Conversational) ---

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot):
    user = update.effective_user
    if not user: return
    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
    await update.message.reply_text(
        f"{get_message('help_header', bot_instance, is_arabic_reply)}\n\n"
        f"{get_message('help_text', bot_instance, is_arabic_reply)}"
    )

async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot):
    user = update.effective_user
    if not user: return
    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
    await update.message.reply_text(
        f"{get_message('contact_header', bot_instance, is_arabic_reply)}\n\n"
        f"{get_message('contact_details', bot_instance, is_arabic_reply)}"
    )

async def cancel_conversation_command(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot) -> int:
    """Handles /cancel command to exit any active conversation and return to start options."""
    user = update.effective_user
    if not user: return ConversationHandler.END # Should not happen from a command

    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)

    if user.id in bot_instance.user_data:
        del bot_instance.user_data[user.id]
    if context.user_data: # Clear PTB's conversation context
        context.user_data.clear()

    await update.message.reply_text(
        get_message('cancelled', bot_instance, is_arabic_reply),
        reply_markup=ReplyKeyboardRemove() # Remove any lingering reply keyboards
    )
    # After cancelling, re-present the main options by calling start_command
    return await start_command(update, context, bot_instance)


# --- General Message Handler (Outside Conversations) ---

async def handle_general_message(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot):
    """Handles general text messages not part of a command or active conversation."""
    user = update.effective_user
    if not user or not update.message or not update.message.text: return

    # This handler is for messages outside of any defined ConversationHandler flow.
    # If user types something unexpected while in a conversation, that conversation's
    # state handlers (or fallbacks) should manage it.

    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
    message_text = update.message.text.strip()

    try:
        # Heuristic check for critical complaints in general messages
        if await bot_instance._is_critical_complaint_llm(message_text):
            # If a general message seems critical, we should guide them into the complaint flow.
            # The complaint flow itself will then do a more formal critical check.
            # For now, we interpret this as a complaint intent.
            await update.message.reply_text(get_message('complaint_intent_detected', bot_instance, is_arabic_reply))
            # Ideally, offer to start complaint flow or show main menu.
            # For now, just informs. User can then use /start or /complaint.
            return

        intent = await bot_instance._determine_user_intent_llm(message_text)
        reply_key = ""

        if intent == "COMPLAINT_INTENT":
            reply_key = 'complaint_intent_detected'
        elif intent == "SUGGESTION_INTENT":
            reply_key = 'suggestion_intent_detected'
        elif intent == "CONTACT_INTENT":
            reply_key = 'contact_intent_detected'
        else: # "OFF_TOPIC" or any other unexpected intent
            reply_key = 'off_topic'

        await update.message.reply_text(get_message(reply_key, bot_instance, is_arabic_reply))

    except Exception as e:
        logger.error(f"Error in handle_general_message for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(get_message('error', bot_instance, is_arabic_reply))

# --- Global Error Handler ---

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates and inform the user if possible."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        try:
            bot_instance = context.application.bot_data.get('bot_instance')
            is_arabic_reply = True # Default if bot_instance not found or no user context
            if bot_instance and update.effective_user : # Ensure user context exists for language preference
                is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
            
            error_message_text = get_message('error', bot_instance, is_arabic_reply) if bot_instance else \
                                 "An unexpected error occurred. Please try again later."

            await update.effective_message.reply_text(
                error_message_text,
                reply_markup=ReplyKeyboardRemove()
            )
        except Exception as e_reply:
            logger.error(f"Failed to send error message to user: {e_reply}")

# --- Setup Function ---

def setup_telegram_handlers(application: Application, bot_instance: InstitutionBot) -> None:
    """Sets up all Telegram handlers for the bot application."""

    # Store bot_instance in application.bot_data for access in error_handler etc.
    application.bot_data['bot_instance'] = bot_instance

    # Main ConversationHandler for the entire interaction flow after /start
    main_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', lambda u, c: start_command(u, c, bot_instance)),
            # Allow direct entry to complaint flow (e.g. if user types /complaint)
            # This will initiate the complaint data collection.
            CommandHandler('complaint', lambda u,c: start_complaint_flow(u,c,bot_instance))
        ],
        states={
            SELECTING_ACTION: [ # After /start, waiting for button press
                CallbackQueryHandler(lambda u, c: handle_action_selection(u, c, bot_instance), pattern=r'^action:'),
                # Optional: Handle text messages if user types instead of clicking a button
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: start_command(u,c,bot_instance)) # Re-show options
            ],
            # Complaint specific states (entered from handle_action_selection or direct /complaint)
            CONFIRM_EXISTING: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: confirm_existing_data(u, c, bot_instance))],
            COLLECTING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_name(u, c, bot_instance))],
            COLLECTING_SEX: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_sex(u, c, bot_instance))],
            COLLECTING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_phone(u, c, bot_instance))],
            COLLECTING_RESIDENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_residence(u, c, bot_instance))],
            COLLECTING_GOVERNORATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_governorate(u, c, bot_instance))],
            COLLECTING_DIRECTORATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_directorate(u, c, bot_instance))],
            COLLECTING_VILLAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_village(u, c, bot_instance))],
            COLLECTING_COMPLAINT: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_main_text(u, c, bot_instance))], # Uses collect_main_text
            CONFIRMING_SUBMISSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: confirm_submission(u, c, bot_instance))],

            # Critical complaint states
            CRITICAL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_critical_name(u, c, bot_instance))],
            CRITICAL_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_critical_phone(u, c, bot_instance))],

            # Suggestion and Feedback states (entered from handle_action_selection)
            COLLECTING_SUGGESTION_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_main_text(u, c, bot_instance))],
            COLLECTING_FEEDBACK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: collect_main_text(u, c, bot_instance))],
        },
        fallbacks=[
            CommandHandler('cancel', lambda u, c: cancel_conversation_command(u, c, bot_instance)),
            CommandHandler('start', lambda u, c: start_command(u, c, bot_instance)) # Allow /start to reset
            ],
        allow_reentry=True,
    )
    application.add_handler(main_conv_handler)

    # Standard command handlers (available globally, outside conversations)
    command_handlers_map = {
        "help": help_command,
        "contact": contact_command,
        # Direct commands for suggestion/feedback if user knows them (optional)
        # They would need their own entry points or simple handlers if not part of main_conv_handler
        "suggestion": lambda u,c: _direct_suggestion_entry(u,c,bot_instance), # Example
        "feedback": lambda u,c: _direct_feedback_entry(u,c,bot_instance),   # Example
    }
    for command, handler_func in command_handlers_map.items():
        application.add_handler(CommandHandler(command, handler_func)) # Pass bot_instance if direct call

    # General message handler for text not caught by conversations or specific commands
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        lambda u, c: handle_general_message(u, c, bot_instance)
    ), group=1) # Lower priority

    # Global error handler
    application.add_error_handler(error_handler)

# Helper functions for direct command entries (if desired)
async def _direct_suggestion_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot):
    """Handles direct /suggestion command to start suggestion flow."""
    user = update.effective_user
    if not user: return
    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
    bot_instance.user_data[user.id] = ComplaintData(user_id=user.id) # Initialize
    context.user_data['_current_conversation_type'] = "action:suggestion"
    await update.message.reply_text(get_message('enter_suggestion_details', bot_instance, is_arabic_reply))
    return COLLECTING_SUGGESTION_TEXT # This needs to be an entry point to a ConversationHandler or handled differently

async def _direct_feedback_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_instance: InstitutionBot):
    """Handles direct /feedback command to start feedback flow."""
    user = update.effective_user
    if not user: return
    is_arabic_reply = get_user_preferred_language_is_arabic(update, bot_instance)
    bot_instance.user_data[user.id] = ComplaintData(user_id=user.id) # Initialize
    context.user_data['_current_conversation_type'] = "action:feedback"
    await update.message.reply_text(get_message('enter_feedback_details', bot_instance, is_arabic_reply))
    return COLLECTING_FEEDBACK_TEXT # Similar to above, needs proper handling if used as direct entry