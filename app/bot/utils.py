"""
AI Gate for Artificial Intelligence Applications
Shared Bot Utilities Module for Institution Complaint Management Bot

This module provides centralized utilities for:
- Message localization and text management
- User language preference detection
- Common Telegram UI helper functions
- Shared formatting and validation utilities

Core Philosophy:
- Single source of truth for default bot messages
- Robust localization support with Arabic/English
- Extensible helper functions for common UI patterns
- No circular dependencies with handler modules
- Comprehensive message coverage for all handler modules
"""

import logging
import re
from functools import wraps
from typing import Dict, Any, Optional, TYPE_CHECKING
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, constants
from telegram.ext import ContextTypes

# Type hinting for bot_instance without circular imports
if TYPE_CHECKING:
    from app.bot.institution_bot_logic import InstitutionBot

logger = logging.getLogger(__name__)

def send_typing_action(func):
    """Decorator that sends a 'typing' action to the user."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=constants.ChatAction.TYPING
        )
        return await func(update, context, *args, **kwargs)
    return wrapper

def escape_markdown_v2(text: str) -> str:
    """
    Escapes text for Telegram's MarkdownV2 parse mode.
    This is crucial to prevent errors when sending text that might
    contain special Markdown characters like *, _, `, etc.
    """
    # List of characters to escape: _ * [ ] ( ) ~ ` > # + - = | { } . !
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    # Use re.sub to add a backslash before each special character
    return re.sub(f'([\\\\{escape_chars}])', r'\\\\\\1', str(text))

# Comprehensive default messages dictionary supporting Arabic and English
DEFAULT_MESSAGES: Dict[str, Dict[str, str]] = {
    'ar': {
        # Welcome and main menu messages
        'welcome_options': "مرحباً بك {user_first_name} في بوت {institution_name}. يرجى اختيار أحد الخيارات:",
        'welcome_back': "مرحباً بك مرة أخرى {user_first_name}! كيف يمكنني مساعدتك اليوم؟",
        'how_can_i_help_today': "كيف يمكنني خدمتك اليوم؟",
        
        # Main menu options
        'option_complaint': "📝 تقديم شكوى",
        'option_inquiry': "❓ استفسار",
        'option_status': "📊 حالة الشكوى",
        'option_help': "ℹ️ المساعدة",
        'option_settings': "⚙️ الإعدادات",
        'option_contact': "📞 التواصل",
        'option_suggestion': "💡 تقديم اقتراح",
        'option_feedback': "📋 تقديم ملاحظة",
        
        # Complaint flow messages
        'complaint_start': "سأساعدك في تقديم شكوى جديدة. يرجى تعبئة المعلومات التالية:",
        'complaint_name_prompt': "الرجاء إدخال اسمك الكامل:",
        'complaint_phone_prompt': "الرجاء إدخال رقم هاتفك:",
        'complaint_email_prompt': "الرجاء إدخال بريدك الإلكتروني (اختياري):",
        'complaint_sex_prompt': "الرجاء تحديد الجنس:",
        'complaint_age_prompt': "الرجاء إدخال العمر:",
        'complaint_description_prompt': "الرجاء وصف شكواك بالتفصيل:",
        'complaint_location_prompt': "الرجاء تحديد موقع الحادثة أو إرسال الموقع:",
        'complaint_new_or_reminder': "هل تريد تقديم شكوى جديدة أم متابعة شكوى سابقة؟",
        'complaint_use_original_text': "استخدام النص الأصلي",
        'complaint_write_new_text': "كتابة نص جديد",
        
        # Confirmation and completion messages
        'complaint_review': "مراجعة بيانات الشكوى:\n\n{complaint_details}\n\nهل تريد تأكيد إرسال الشكوى؟",
        'complaint_submitted': "✅ تم تقديم شكواك بنجاح!\n\nرقم الشكوى: {complaint_id}\n\nسيتم التواصل معك خلال {response_time}",
        'complaint_cancelled': "❌ تم إلغاء تقديم الشكوى. يمكنك البدء من جديد في أي وقت.",
        'complaint_data_collected': "تم جمع البيانات بنجاح. يرجى مراجعة المعلومات.",
        
        # Status and inquiry messages
        'status_prompt': "الرجاء إدخال رقم الشكوى للاستعلام عن حالتها:",
        'status_not_found': "❌ لم يتم العثور على شكوى برقم: {complaint_id}",
        'status_found': "📊 حالة الشكوى رقم {complaint_id}:\n\n{status_details}",
        
        # Input validation messages
        'invalid_phone': "❌ رقم الهاتف غير صحيح. يرجى إدخال رقم صحيح (مثال: 05xxxxxxxx)",
        'invalid_phone_format': "❌ تنسيق رقم الهاتف غير صحيح. يرجى إدخال رقم بالتنسيق الصحيح",
        'invalid_email': "❌ البريد الإلكتروني غير صحيح. يرجى إدخال بريد صحيح أو اختر 'تخطي'",
        'invalid_age': "❌ العمر غير صحيح. يرجى إدخال رقم بين 1 و 120",
        'input_too_long': "❌ النص طويل جداً. الحد الأقصى {max_length} حرف",
        'input_required': "❌ هذا الحقل مطلوب. يرجى إدخال القيمة المطلوبة",
        'name_too_short': "❌ الاسم قصير جداً. يرجى إدخال الاسم الكامل",
        'invalid_selection': "❌ اختيارك غير صالح. يرجى اختيار أحد الخيارات المتاحة",
        'invalid_name_format': "❌ يرجى إدخال اسم صحيح (اسمين على الأقل)",
        'input_too_short': "❌ النص قصير جداً. يرجى تقديم المزيد من التفاصيل",
        
        # New messages from complaint_flow_handlers.py
        'prompt_enter_residence': "الرجاء تحديد حالة الإقامة:",
        'prompt_enter_governorate': "الرجاء تحديد المحافظة:",
        'prompt_enter_directorate': "الرجاء تحديد المديرية:",
        'prompt_enter_village': "الرجاء تحديد القرية/الحي:",
        'prompt_enter_department': "الرجاء إدخال القسم:",
        'prompt_enter_position': "الرجاء إدخال المنصب/المسمى الوظيفي:",
        'prompt_enter_complaint_type': "الرجاء إدخال نوع الشكوى:",
        'critical_complaint_detected_prompt_name': "❗ تم تحديد أن شكواك عاجلة. يرجى إدخال اسمك الكامل:",
        'prompt_enter_critical_phone': "❗ يرجى إدخال رقم هاتف للتواصل العاجل:",
        'validation_error_name': "❌ يرجى إدخال اسم صحيح (اسمين على الأقل)",
        'validation_error_phone': "❌ رقم الهاتف غير صحيح. يرجى إدخال رقم صحيح",
        'validation_error_email': "❌ البريد الإلكتروني غير صحيح. يرجى إدخال بريد صحيح",
        'validation_error_complaint_text_too_short': "❌ وصف الشكوى قصير جداً. يرجى تقديم المزيد من التفاصيل (20 حرف على الأقل)",
        'validation_error_department': "❌ يرجى إدخال اسم القسم",
        'validation_error_position': "❌ يرجى إدخال المسمى الوظيفي",
        'validation_error_complaint_type': "❌ يرجى إدخال نوع الشكوى",
        
        # Button labels
        'btn_yes': "نعم ✅",
        'btn_no': "لا ❌",
        'btn_confirm': "تأكيد",
        'btn_cancel': "إلغاء",
        'btn_skip': "تخطي",
        'btn_back': "رجوع",
        'btn_next': "التالي",
        'btn_main_menu': "القائمة الرئيسية 🏠",
        'btn_male': "ذكر",
        'btn_female': "أنثى",
        'btn_prefer_not_say': "أفضل عدم الإفصاح",
        'btn_submit_confirm': "تأكيد الإرسال",
        'btn_new_complaint': "شكوى جديدة",
        'btn_follow_complaint': "متابعة شكوى",
        'btn_reminder_previous': "تذكير بشكوى سابقة",
        'btn_yes_use_data': "نعم، استخدم بياناتي",
        'btn_no_new_data': "لا، سأدخل بيانات جديدة",
        'btn_submit_final': "إرسال نهائي",
        'btn_cancel_submission': "إلغاء الإرسال",
        
        # Error messages
        'error_generic': "عذراً، حدث خطأ ما. يرجى المحاولة مرة أخرى لاحقاً.",
        'error_network': "❌ خطأ في الاتصال. يرجى التحقق من الإنترنت والمحاولة مرة أخرى",
        'error_server': "❌ خطأ في الخادم. يرجى المحاولة لاحقاً",
        'error_permission': "❌ لا تملك صلاحية للوصول إلى هذه الخدمة",
        'error_session_expired': "❌ انتهت جلسة العمل. يرجى البدء من جديد",
        'error_start_command': "عذراً، حدث خطأ أثناء بدء التشغيل. يرجى المحاولة مرة أخرى.",
        'error_unknown_intent': "عذراً، لم أتمكن من فهم طلبك بوضوح.",
        'error_processing_message': "عذراً، حدث خطأ أثناء معالجة رسالتك.",
        'error_invalid_selection': "عذراً، اختيارك غير صالح.",
        'error_processing_selection': "عذراً، حدث خطأ أثناء معالجة اختيارك.",
        'error_no_user_context': "❌ لا يمكن تحديد هويتك. يرجى البدء من جديد بإرسال /start",
        'error_submission_failed': "❌ فشل إرسال الشكوى. يرجى المحاولة مرة أخرى.",
        'error_submission_failed_critical': "❌ فشل إرسال الشكوى العاجلة. يرجى الاتصال بنا مباشرة.",
        'error_generic_unexpected': "حدث خطأ غير متوقع",
        
        # Help and information messages
        'help_main': "📖 مساعدة بوت {institution_name}\n\nيمكنك استخدام هذا البوت لـ:\n• تقديم الشكاوى\n• متابعة حالة الشكاوى\n• الاستفسارات العامة\n\nللمساعدة اتصل: {contact_info}",
        'contact_info': "📞 معلومات التواصل:\n\nالهاتف: {phone}\nالبريد: {email}\nالموقع: {website}\nالعنوان: {address}",
        'contact_details_full': "📞 معلومات التواصل الكاملة:\n\nالاسم الرسمي: {institution_name}\nالهاتف: {phone}\nالبريد الإلكتروني: {email}\nالموقع الإلكتروني: {website}\nالعنوان: {address}",
        
        # Settings messages
        'settings_language': "اختر اللغة المفضلة:",
        'settings_notifications': "إعدادات الإشعارات:",
        'language_changed': "✅ تم تغيير اللغة بنجاح",
        
        # Suggestion/Feedback Flow Messages
        'prompt_enter_suggestion_text': "يرجى كتابة اقتراحك أو ملاحظاتك بالتفصيل:",
        'confirm_suggestion_text': "📋 مراجعة الاقتراح:\n\n`{suggestion_text}`\n\nهل تريد تأكيد إرسال هذا الاقتراح؟",
        'suggestion_submitted_successfully': "✅ شكراً لك! تم استلام اقتراحك بنجاح.",
        'suggestion_submission_cancelled': "❌ تم إلغاء تقديم الاقتراح.",
        'suggestion_flow_cancelled': "❌ تم إلغاء عملية تقديم الاقتراح.",
        
        # Admin messages (if applicable)
        'admin_dashboard': "لوحة التحكم - الإحصائيات:\n\n{statistics}",
        'admin_unauthorized': "❌ غير مصرح لك بالوصول إلى لوحة التحكم",
        
        # Admin messages and dashboard
        'admin_welcome': "أهلاً بك أيها المدير *{user_first_name}* في لوحة التحكم الرئيسية\.",
        'admin_menu_prompt': "يرجى تحديد الإجراء المطلوب من القائمة أدناه:",
        'admin_option_stats': "📊 عرض الإحصائيات",
        'admin_option_export': "📤 تصدير البيانات",
        'admin_stats_loading': "⏳ جاري تحميل الإحصائيات، يرجى الانتظار...",
        'admin_stats_header': "📊 *ملخص إحصائيات الشكاوى*",
        'admin_stats_total': "إجمالي الشكاوى: *{count}*",
        'admin_stats_critical': "الشكاوى الحرجة: *{count}* \({percentage}%\)",
        'admin_stats_breakdown': "\nتفصيل حسب الحالة:",
        'admin_stats_item': "• {status}: *{count}* \({percentage}%\)",
        'admin_stats_no_data': "لا توجد بيانات إحصائية متاحة حالياً.",
        'admin_stats_timestamp': "\n_تم إنشاء التقرير في: {timestamp}_",
        'admin_export_placeholder': "ميزة تصدير البيانات قيد التطوير حالياً\. سيتم إعلامك عند توفرها\.",
        'admin_exit_message': "تم الخروج من لوحة التحكم\. شكراً لك\.",
        'admin_cancel_message': "تم إلغاء الجلسة الإدارية.",
        'btn_back_to_admin': "⬅️ العودة إلى القائمة",
        'btn_exit': "🚪 خروج",
        
        # Time and status labels
        'status_pending': "قيد المراجعة",
        'status_in_progress': "قيد المعالجة",
        'status_resolved': "تم الحل",
        'status_closed': "مغلقة",
        'created_at': "تاريخ الإنشاء",
        'updated_at': "آخر تحديث",
        
        # Reminders and notifications
        'reminder_followup': "تذكير: شكواك رقم {complaint_id} قيد المراجعة. سنتواصل معك قريباً.",
        'notification_status_update': "🔔 تحديث حالة الشكوى {complaint_id}: {new_status}",
        'reminder_no_complaints_found': "❌ لم يتم العثور على شكاوى سابقة.",
        'reminder_acknowledged': "✅ تم تسجيل طلب التذكير بالشكوى رقم {complaint_id}. سنتواصل معك قريباً.",
        'reminder_log_error': "❌ حدث خطأ أثناء تسجيل طلب التذكير. يرجى المحاولة مرة أخرى.",
        
        # Data collection prompts
        'prompt_enter_name': "يرجى إدخال اسمك الكامل:",
        'prompt_enter_phone': "يرجى إدخال رقم هاتفك:",
        'prompt_enter_email': "يرجى إدخال بريدك الإلكتروني (اختياري):",
        'prompt_select_sex': "يرجى تحديد الجنس:",
        'prompt_enter_age': "يرجى إدخال عمرك:",
        'prompt_enter_complaint_text': "يرجى وصف شكواك بالتفصيل:",
        'prompt_enter_location': "يرجى تحديد موقع الحادثة:",
        'prompt_enter_residence': "يرجى تحديد حالة الإقامة:",
        'prompt_enter_governorate': "يرجى تحديد المحافظة:",
        'prompt_enter_directorate': "يرجى تحديد المديرية:",
        'prompt_enter_village': "يرجى تحديد القرية/الحي:",
        'prompt_enter_critical_phone': "❗ يرجى إدخال رقم هاتف للتواصل العاجل:",
        
        # Profile and complaint flow messages
        'ask_new_or_reminder': "لديك {num_complaints} شكوى/شكاوى سابقة. هل تريد تقديم شكوى جديدة أو تذكير بشكوى سابقة؟",
        'new_complaint_selected': "✅ سيتم البدء في تقديم شكوى جديدة.",
        'existing_profile_summary': "📋 يوجد لديك ملف شخصي مسجل:\n\nالاسم: {name}\nالجنس: {sex}\nالهاتف: {phone}\n\nهل تريد استخدام هذه البيانات؟",
        'profile_data_confirmed': "✅ تم تأكيد استخدام بياناتك المسجلة.",
        'collecting_new_profile_data': "سيتم جمع بياناتك الشخصية الجديدة الآن.",
        'offer_use_original_complaint': "لديك نص شكوى مسبق:\n\n{original_text_snippet}...\n\nهل تريد استخدام هذا النص؟",
        'using_original_complaint': "✅ سيتم استخدام نص الشكوى الأصلي.",
        'prompt_enter_new_complaint_text': "يرجى إدخال نص الشكوى الجديد:",
        'complaint_review_summary_header': "📋 ملخص الشكوى:\n",
        'confirm_submission_prompt': "هل تريد تأكيد إرسال هذه الشكوى؟",
        'complaint_submitted_successfully': "✅ تم تقديم شكواك بنجاح برقم {complaint_id}. شكراً لك.",
        'complaint_flow_cancelled': "❌ تم إلغاء عملية تقديم الشكوى.",
        'critical_complaint_detected_prompt_name': "❗ تم تحديد أن شكواك عاجلة. يرجى إدخال اسمك الكامل:",
        'critical_complaint_default_text': "شكوى عاجلة - تم تقديمها عبر البوت",
        'critical_complaint_submitted_successfully': "❗ تم تقديم شكواك العاجلة برقم {complaint_id}. سيتم التواصل معك فوراً.",
        
        # Summary labels
        'label_name': "الاسم",
        'label_sex': "الجنس",
        'label_phone': "الهاتف",
        'label_residence_status': "حالة الإقامة",
        'label_governorate': "المحافظة",
        'label_directorate': "المديرية",
        'label_village': "القرية/الحي",
        'label_complaint_text': "نص الشكوى",
        'label_english_summary': "ملخص بالإنجليزية",
        'summary_not_yet_generated': "لم يتم إنشاء ملخص بعد",
        
        # New messages
        'data_not_available': 'غير متوفر',
        'not_available_placeholder': 'غير متاح',
        'conversation_cancelled': 'تم إلغاء المحادثة'
    },
    
    'en': {
        # Welcome and main menu messages
        'welcome_options': "Welcome {user_first_name} to the {institution_name} bot. Please select an option:",
        'welcome_back': "Welcome back {user_first_name}! How can I help you today?",
        'how_can_i_help_today': "How can I help you today?",
        
        # Main menu options
        'option_complaint': "📝 Submit Complaint",
        'option_inquiry': "❓ Inquiry",
        'option_status': "📊 Complaint Status",
        'option_help': "ℹ️ Help",
        'option_settings': "⚙️ Settings",
        'option_contact': "📞 Contact",
        'option_suggestion': "💡 Submit Suggestion",
        'option_feedback': "📋 Submit Feedback",
        
        # Complaint flow messages
        'complaint_start': "I'll help you submit a new complaint. Please fill in the following information:",
        'complaint_name_prompt': "Please enter your full name:",
        'complaint_phone_prompt': "Please enter your phone number:",
        'complaint_email_prompt': "Please enter your email address (optional):",
        'complaint_sex_prompt': "Please select your gender:",
        'complaint_age_prompt': "Please enter your age:",
        'complaint_description_prompt': "Please describe your complaint in detail:",
        'complaint_location_prompt': "Please specify the incident location or send location:",
        'complaint_new_or_reminder': "Would you like to submit a new complaint or follow up on an existing one?",
        'complaint_use_original_text': "Use Original Text",
        'complaint_write_new_text': "Write New Text",
        
        # Confirmation and completion messages
        'complaint_review': "Review complaint details:\n\n{complaint_details}\n\nDo you want to confirm and submit the complaint?",
        'complaint_submitted': "✅ Your complaint has been submitted successfully!\n\nComplaint ID: {complaint_id}\n\nWe will contact you within {response_time}",
        'complaint_cancelled': "❌ Complaint submission cancelled. You can start over anytime.",
        'complaint_data_collected': "Data collected successfully. Please review the information.",
        
        # Status and inquiry messages
        'status_prompt': "Please enter the complaint ID to check its status:",
        'status_not_found': "❌ No complaint found with ID: {complaint_id}",
        'status_found': "📊 Status of complaint #{complaint_id}:\n\n{status_details}",
        
        # Input validation messages
        'invalid_phone': "❌ Invalid phone number. Please enter a valid number (e.g., 05xxxxxxxx)",
        'invalid_phone_format': "❌ Invalid phone number format. Please enter a number in the correct format",
        'invalid_email': "❌ Invalid email address. Please enter a valid email or choose 'Skip'",
        'invalid_age': "❌ Invalid age. Please enter a number between 1 and 120",
        'input_too_long': "❌ Input too long. Maximum {max_length} characters allowed",
        'input_required': "❌ This field is required. Please enter the required value",
        'name_too_short': "❌ Name too short. Please enter your full name",
        'invalid_selection': "❌ Invalid selection. Please choose one of the available options",
        'invalid_name_format': "❌ Please enter a valid name (at least two words)",
        'input_too_short': "❌ The text is too short. Please provide more details",
        
        # New messages from complaint_flow_handlers.py
        'prompt_enter_residence': "Please specify your residence status:",
        'prompt_enter_governorate': "Please specify the governorate:",
        'prompt_enter_directorate': "Please specify the directorate:",
        'prompt_enter_village': "Please specify the village/area:",
        'prompt_enter_department': "Please enter the department:",
        'prompt_enter_position': "Please enter your position/job title:",
        'prompt_enter_complaint_type': "Please enter the complaint type:",
        'critical_complaint_detected_prompt_name': "❗ Your complaint has been flagged as urgent. Please enter your full name:",
        'prompt_enter_critical_phone': "❗ Please enter an urgent contact phone number:",
        'validation_error_name': "❌ Please enter a valid name (at least two words)",
        'validation_error_phone': "❌ Invalid phone number. Please enter a valid number",
        'validation_error_email': "❌ Invalid email address. Please enter a valid email",
        'validation_error_complaint_text_too_short': "❌ Complaint description is too short. Please provide more details (at least 20 characters)",
        'validation_error_department': "❌ Please enter the department name",
        'validation_error_position': "❌ Please enter your position",
        'validation_error_complaint_type': "❌ Please enter the complaint type",
        
        # Button labels
        'btn_yes': "Yes ✅",
        'btn_no': "No ❌",
        'btn_confirm': "Confirm",
        'btn_cancel': "Cancel",
        'btn_skip': "Skip",
        'btn_back': "Back",
        'btn_next': "Next",
        'btn_main_menu': "Main Menu 🏠",
        'btn_male': "Male",
        'btn_female': "Female",
        'btn_prefer_not_say': "Prefer not to say",
        'btn_submit_confirm': "Confirm Submission",
        'btn_new_complaint': "New Complaint",
        'btn_follow_complaint': "Follow Complaint",
        'btn_reminder_previous': "Remind About Previous",
        'btn_yes_use_data': "Yes, Use My Data",
        'btn_no_new_data': "No, Enter New Data",
        'btn_submit_final': "Submit Final",
        'btn_cancel_submission': "Cancel Submission",
        
        # Error messages
        'error_generic': "Sorry, an unexpected error occurred. Please try again later.",
        'error_network': "❌ Connection error. Please check your internet and try again",
        'error_server': "❌ Server error. Please try again later",
        'error_permission': "❌ You don't have permission to access this service",
        'error_session_expired': "❌ Session expired. Please start over",
        'error_start_command': "Sorry, an error occurred while starting. Please try again.",
        'error_unknown_intent': "Sorry, I couldn't understand your request clearly.",
        'error_processing_message': "Sorry, an error occurred while processing your message.",
        'error_invalid_selection': "Sorry, your selection is invalid.",
        'error_processing_selection': "Sorry, an error occurred while processing your selection.",
        'error_no_user_context': "❌ Unable to identify your context. Please start over by sending /start",
        'error_submission_failed': "❌ Failed to submit complaint. Please try again.",
        'error_submission_failed_critical': "❌ Failed to submit critical complaint. Please contact us directly.",
        'error_generic_unexpected': "An unexpected error occurred",
        
        # Help and information messages
        'help_main': "📖 {institution_name} Bot Help\n\nYou can use this bot to:\n• Submit complaints\n• Track complaint status\n• General inquiries\n\nFor help contact: {contact_info}",
        'contact_info': "📞 Contact Information:\n\nPhone: {phone}\nEmail: {email}\nWebsite: {website}\nAddress: {address}",
        'contact_details_full': "📞 Full Contact Information:\n\nOfficial Name: {institution_name}\nPhone: {phone}\nEmail: {email}\nWebsite: {website}\nAddress: {address}",
        
        # Settings messages
        'settings_language': "Choose your preferred language:",
        'settings_notifications': "Notification settings:",
        'language_changed': "✅ Language changed successfully",
        
        # Suggestion/Feedback Flow Messages
        'prompt_enter_suggestion_text': "Please write your suggestion or feedback in detail:",
        'confirm_suggestion_text': "📋 Review Suggestion:\n\n`{suggestion_text}`\n\nDo you want to confirm and submit this suggestion?",
        'suggestion_submitted_successfully': "✅ Thank you! Your suggestion has been received successfully.",
        'suggestion_submission_cancelled': "❌ Suggestion submission has been cancelled.",
        'suggestion_flow_cancelled': "❌ The suggestion submission process has been cancelled.",
        
        # Admin messages (if applicable)
        'admin_dashboard': "Admin Dashboard - Statistics:\n\n{statistics}",
        'admin_unauthorized': "❌ You are not authorized to access the admin dashboard",
        
        # Admin messages and dashboard
        'admin_welcome': "Welcome Admin *{user_first_name}* to the main dashboard\.",
        'admin_menu_prompt': "Please select an action from the menu below:",
        'admin_option_stats': "📊 View Statistics",
        'admin_option_export': "📤 Export Data",
        'admin_stats_loading': "⏳ Loading statistics, please wait...",
        'admin_stats_header': "📊 *Complaint Statistics Summary*",
        'admin_stats_total': "Total Complaints: *{count}*",
        'admin_stats_critical': "Critical Complaints: *{count}* \({percentage}%\)",
        'admin_stats_breakdown': "\nBreakdown by Status:",
        'admin_stats_item': "• {status}: *{count}* \({percentage}%\)",
        'admin_stats_no_data': "No statistical data available at this time.",
        'admin_stats_timestamp': "\n_Report generated at: {timestamp}_",
        'admin_export_placeholder': "The data export feature is currently under development\. You will be notified when it's available\.",
        'admin_exit_message': "Exited from the admin panel\. Thank you\.",
        'admin_cancel_message': "Admin session cancelled.",
        'btn_back_to_admin': "⬅️ Back to Menu",
        'btn_exit': "🚪 Exit",
        
        # Time and status labels
        'status_pending': "Pending Review",
        'status_in_progress': "In Progress",
        'status_resolved': "Resolved",
        'status_closed': "Closed",
        'created_at': "Created At",
        'updated_at': "Last Updated",
        
        # Reminders and notifications
        'reminder_followup': "Reminder: Your complaint #{complaint_id} is under review. We'll contact you soon.",
        'notification_status_update': "🔔 Complaint {complaint_id} status update: {new_status}",
        'reminder_no_complaints_found': "❌ No previous complaints found.",
        'reminder_acknowledged': "✅ Reminder request for complaint #{complaint_id} logged. We'll contact you soon.",
        'reminder_log_error': "❌ Error logging reminder request. Please try again.",
        
        # Data collection prompts
        'prompt_enter_name': "Please enter your full name:",
        'prompt_enter_phone': "Please enter your phone number:",
        'prompt_enter_email': "Please enter your email address (optional):",
        'prompt_select_sex': "Please select your gender:",
        'prompt_enter_age': "Please enter your age:",
        'prompt_enter_complaint_text': "Please describe your complaint in detail:",
        'prompt_enter_location': "Please specify the incident location:",
        'prompt_enter_residence': "Please specify your residence status:",
        'prompt_enter_governorate': "Please specify the governorate:",
        'prompt_enter_directorate': "Please specify the directorate:",
        'prompt_enter_village': "Please specify the village/area:",
        'prompt_enter_critical_phone': "❗ Please enter an urgent contact phone number:",
        
        # Profile and complaint flow messages
        'ask_new_or_reminder': "You have {num_complaints} previous complaint(s). Would you like to submit a new complaint or get a reminder about a previous one?",
        'new_complaint_selected': "✅ Starting new complaint submission.",
        'existing_profile_summary': "📋 You have an existing profile:\n\nName: {name}\nGender: {sex}\nPhone: {phone}\n\nWould you like to use this data?",
        'profile_data_confirmed': "✅ Confirmed use of your existing data.",
        'collecting_new_profile_data': "Now collecting your new profile data.",
        'offer_use_original_complaint': "You have a pre-existing complaint text:\n\n{original_text_snippet}...\n\nWould you like to use this text?",
        'using_original_complaint': "✅ Will use the original complaint text.",
        'prompt_enter_new_complaint_text': "Please enter your new complaint text:",
        'complaint_review_summary_header': "📋 Complaint Summary:\n",
        'confirm_submission_prompt': "Do you want to confirm submission of this complaint?",
        'complaint_submitted_successfully': "✅ Your complaint has been submitted successfully with ID {complaint_id}. Thank you.",
        'complaint_flow_cancelled': "❌ Complaint submission process cancelled.",
        'critical_complaint_detected_prompt_name': "❗ Your complaint has been flagged as urgent. Please enter your full name:",
        'critical_complaint_default_text': "Urgent complaint - submitted via bot",
        'critical_complaint_submitted_successfully': "❗ Your urgent complaint has been submitted with ID {complaint_id}. We will contact you immediately.",
        
        # Summary labels
        'label_name': "Name",
        'label_sex': "Gender",
        'label_phone': "Phone",
        'label_residence_status': "Residence Status",
        'label_governorate': "Governorate",
        'label_directorate': "Directorate",
        'label_village': "Village/Area",
        'label_complaint_text': "Complaint Text",
        'label_english_summary': "English Summary",
        'summary_not_yet_generated': "Summary not yet generated",
        
        # New messages
        'data_not_available': 'Not available',
        'not_available_placeholder': 'Not available',
        'conversation_cancelled': 'Conversation cancelled'
    }
}


def get_user_preferred_language_is_arabic(update: Update, bot_instance: 'InstitutionBot') -> bool:
    """
    Determine if the user's preferred language is Arabic.
    
    Priority order:
    1. User's Telegram language_code
    2. Institution's primary_language from config
    3. Default to Arabic (True)
    
    Args:
        update: Telegram Update object
        bot_instance: InstitutionBot instance
        
    Returns:
        bool: True if Arabic is preferred, False for English
    """
    try:
        # Check user's Telegram language preference
        if update.effective_user and update.effective_user.language_code:
            user_lang = update.effective_user.language_code.lower()
            # Arabic language codes: ar, ar-SA, ar-EG, etc.
            if user_lang.startswith('ar'):
                return True
            # English language codes: en, en-US, en-GB, etc.
            elif user_lang.startswith('en'):
                return False
        
        # Fall back to institution's primary language from config
        if hasattr(bot_instance, 'config') and bot_instance.config:
            institution_config = bot_instance.config.institution
            primary_lang = institution_config.primary_language.lower() if hasattr(institution_config, 'primary_language') else 'ar'
            if primary_lang in ['ar', 'arabic', 'العربية']:
                return True
            elif primary_lang in ['en', 'english']:
                return False
        
        # Default to Arabic
        return True
        
    except Exception as e:
        logger.warning(f"Error determining user language preference: {e}")
        return True  # Default to Arabic


def get_message(message_key: str, bot_instance: 'InstitutionBot', is_arabic_reply: bool, **kwargs) -> str:
    """
    Retrieve a localized message with placeholder formatting.
    
    Priority order for message source:
    1. Custom messages from bot_instance.config.application_settings.ui_messages
    2. DEFAULT_MESSAGES from this module
    3. Fallback error message
    
    Args:
        message_key: Key to look up in message dictionaries
        bot_instance: InstitutionBot instance
        is_arabic_reply: True for Arabic, False for English
        **kwargs: Additional placeholders for message formatting
        
    Returns:
        str: Formatted localized message
    """
    language = 'ar' if is_arabic_reply else 'en'
    
    try:
        # Try to get message from application_settings.ui_messages first
        message_template = None
        
        if hasattr(bot_instance, 'config') and bot_instance.config:
            # Access ui_messages through the Pydantic model structure
            ui_messages = bot_instance.config.application_settings.ui_messages
            message_template = getattr(ui_messages, message_key, None)
        
        # Fall back to default messages if not found in config
        if message_template is None:
            if language in DEFAULT_MESSAGES and message_key in DEFAULT_MESSAGES[language]:
                message_template = DEFAULT_MESSAGES[language][message_key]
        
        # If no message found, return error placeholder
        if message_template is None:
            logger.warning(f"Message key '{message_key}' not found for language '{language}'")
            return f"[MSG_NOT_FOUND: {message_key}]"
        
        # Prepare common placeholders from bot config with refined access
        format_kwargs = {}  # Start with empty dict for clarity
        if hasattr(bot_instance, 'config') and bot_instance.config:
            institution_config = bot_instance.config.institution
            contact_config = institution_config.contact
            
            # Determine institution name based on reply language
            inst_name_key = 'name_ar' if is_arabic_reply else 'name_en'
            default_inst_name = 'المؤسسة' if is_arabic_reply else 'The Institution'
            format_kwargs['institution_name'] = getattr(
                institution_config, 
                inst_name_key, 
                getattr(institution_config, 'name', default_inst_name)
            )
            
            # Contact information with robust fallbacks
            format_kwargs['phone'] = getattr(contact_config, 'phone', '[Phone Placeholder]')
            format_kwargs['email'] = getattr(contact_config, 'email', '[Email Placeholder]')
            
            # Address with language-specific variants
            address_key = 'address_ar' if is_arabic_reply else 'address_en'
            format_kwargs['address'] = getattr(
                contact_config, 
                address_key, 
                getattr(contact_config, 'address', '[Address Placeholder]')
            )
            
            # Additional common placeholders
            format_kwargs['website'] = getattr(institution_config, 'website', '[Website Placeholder]')
            format_kwargs['response_time'] = getattr(
                institution_config, 
                'response_time', 
                '48 ساعة' if is_arabic_reply else '48 hours'
            )
            
            # Contact info for help messages
            contact_info = f"{format_kwargs['phone']}"
            if format_kwargs['email'] != '[Email Placeholder]':
                contact_info += f" - {format_kwargs['email']}"
            format_kwargs['contact_info'] = contact_info
        
        # Merge with explicitly passed kwargs (kwargs take precedence)
        format_kwargs.update(kwargs)
        
        # Format message with placeholders
        try:
            return message_template.format_map(format_kwargs)
        except (KeyError, AttributeError) as e:
            logger.warning(f"Missing placeholder {e} for message key '{message_key}'")
            # Return template with unfilled placeholders rather than crash
            return message_template
            
    except Exception as e:
        logger.error(f"Error retrieving message '{message_key}': {e}")
        return f"[ERROR: {message_key}]"


def get_main_menu_keyboard(bot_instance: 'InstitutionBot', is_arabic: bool) -> ReplyKeyboardMarkup:
    """
    Create the main menu keyboard with localized options.
    
    Args:
        bot_instance: InstitutionBot instance
        is_arabic: True for Arabic, False for English
        
    Returns:
        ReplyKeyboardMarkup: Main menu keyboard
    """
    keyboard = [
        [KeyboardButton(get_message('option_complaint', bot_instance, is_arabic))],
        [
            KeyboardButton(get_message('option_status', bot_instance, is_arabic)),
            KeyboardButton(get_message('option_inquiry', bot_instance, is_arabic))
        ],
        [
            KeyboardButton(get_message('option_help', bot_instance, is_arabic)),
            KeyboardButton(get_message('option_contact', bot_instance, is_arabic))
        ]
    ]
    
    return ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True, 
        one_time_keyboard=False
    )


def get_initial_action_buttons_keyboard(bot_instance: 'InstitutionBot', is_arabic: bool) -> InlineKeyboardMarkup:
    """
    Create an inline keyboard with initial action buttons for complaint, suggestion, and feedback.
    
    Args:
        bot_instance: InstitutionBot instance
        is_arabic: True for Arabic, False for English
        
    Returns:
        InlineKeyboardMarkup: Initial action buttons keyboard
    """
    keyboard = [
        [InlineKeyboardButton(
            text=get_message('option_complaint', bot_instance, is_arabic),
            callback_data="initial_action:complaint"
        )],
        [InlineKeyboardButton(
            text=get_message('option_suggestion', bot_instance, is_arabic),
            callback_data="initial_action:suggestion"
        )],
        [InlineKeyboardButton(
            text=get_message('option_feedback', bot_instance, is_arabic),
            callback_data="initial_action:feedback"
        )]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_yes_no_keyboard(bot_instance: 'InstitutionBot', is_arabic: bool) -> ReplyKeyboardMarkup:
    """
    Create a Yes/No keyboard with localized labels.
    
    Args:
        bot_instance: InstitutionBot instance
        is_arabic: True for Arabic, False for English
        
    Returns:
        ReplyKeyboardMarkup: Yes/No keyboard
    """
    keyboard = [
        [
            KeyboardButton(get_message('btn_yes', bot_instance, is_arabic)),
            KeyboardButton(get_message('btn_no', bot_instance, is_arabic))
        ]
    ]
    
    return ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True, 
        one_time_keyboard=True
    )


def get_confirm_cancel_keyboard(bot_instance: 'InstitutionBot', is_arabic: bool) -> ReplyKeyboardMarkup:
    """
    Create a Confirm/Cancel keyboard with localized labels.
    
    Args:
        bot_instance: InstitutionBot instance
        is_arabic: True for Arabic, False for English
        
    Returns:
        ReplyKeyboardMarkup: Confirm/Cancel keyboard
    """
    keyboard = [
        [
            KeyboardButton(get_message('btn_confirm', bot_instance, is_arabic)),
            KeyboardButton(get_message('btn_cancel', bot_instance, is_arabic))
        ]
    ]
    
    return ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True, 
        one_time_keyboard=True
    )


def get_sex_keyboard(bot_instance: 'InstitutionBot', is_arabic: bool) -> ReplyKeyboardMarkup:
    """
    Create a gender selection keyboard with localized labels.
    
    Args:
        bot_instance: InstitutionBot instance
        is_arabic: True for Arabic, False for English
        
    Returns:
        ReplyKeyboardMarkup: Gender selection keyboard
    """
    keyboard = [
        [
            KeyboardButton(get_message('btn_male', bot_instance, is_arabic)),
            KeyboardButton(get_message('btn_female', bot_instance, is_arabic))
        ],
        [KeyboardButton(get_message('btn_prefer_not_say', bot_instance, is_arabic))],
        [KeyboardButton(get_message('btn_skip', bot_instance, is_arabic))]
    ]
    
    return ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True, 
        one_time_keyboard=True
    )


def get_back_main_menu_keyboard(bot_instance: 'InstitutionBot', is_arabic: bool) -> ReplyKeyboardMarkup:
    """
    Create a keyboard with Back and Main Menu options.
    
    Args:
        bot_instance: InstitutionBot instance
        is_arabic: True for Arabic, False for English
        
    Returns:
        ReplyKeyboardMarkup: Back/Main Menu keyboard
    """
    keyboard = [
        [
            KeyboardButton(get_message('btn_back', bot_instance, is_arabic)),
            KeyboardButton(get_message('btn_main_menu', bot_instance, is_arabic))
        ]
    ]
    
    return ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True, 
        one_time_keyboard=False
    )


def get_new_or_followup_keyboard(bot_instance: 'InstitutionBot', is_arabic: bool) -> ReplyKeyboardMarkup:
    """
    Create a keyboard for choosing between new complaint or follow-up.
    
    Args:
        bot_instance: InstitutionBot instance
        is_arabic: True for Arabic, False for English
        
    Returns:
        ReplyKeyboardMarkup: New/Follow-up keyboard
    """
    keyboard = [
        [
            KeyboardButton(get_message('btn_new_complaint', bot_instance, is_arabic)),
            KeyboardButton(get_message('btn_follow_complaint', bot_instance, is_arabic))
        ],
        [KeyboardButton(get_message('btn_main_menu', bot_instance, is_arabic))]
    ]
    
    return ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True, 
        one_time_keyboard=True
    )


def get_text_choice_keyboard(bot_instance: 'InstitutionBot', is_arabic: bool) -> ReplyKeyboardMarkup:
    """
    Create a keyboard for choosing between original text or writing new text.
    
    Args:
        bot_instance: InstitutionBot instance
        is_arabic: True for Arabic, False for English
        
    Returns:
        ReplyKeyboardMarkup: Text choice keyboard
    """
    keyboard = [
        [
            KeyboardButton(get_message('complaint_use_original_text', bot_instance, is_arabic)),
            KeyboardButton(get_message('complaint_write_new_text', bot_instance, is_arabic))
        ],
        [KeyboardButton(get_message('btn_cancel', bot_instance, is_arabic))]
    ]
    
    return ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True, 
        one_time_keyboard=True
    )


def validate_phone_number(phone: str, bot_instance: 'InstitutionBot') -> bool:
    """
    Validate phone number format based on patterns from config.
    Falls back to hardcoded patterns if config is not available.
    
    Args:
        phone: Phone number string to validate
        bot_instance: The InstitutionBot instance to access config
        
    Returns:
        bool: True if valid, False otherwise
    """
    
    # Get patterns from config
    try:
        if hasattr(bot_instance, 'config') and bot_instance.config:
            patterns = bot_instance.config.application_settings.validation.phone_patterns
            if not isinstance(patterns, list) or not patterns:
                raise AttributeError("Phone patterns are not a valid list.")
        else:
            raise AttributeError("Bot instance has no config")
    except (AttributeError, KeyError):
        logger.warning("Could not find phone validation patterns in config. Using fallback.")
        # Fallback to hardcoded Yemeni phone patterns
        patterns = [
            r'^07\d{8}$',
            r'^\+9677\d{8}$',
        ]

    # Clean the phone number input
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Check against all provided patterns
    return any(re.match(pattern, clean_phone) for pattern in patterns)


def validate_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email address string to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    
    if not email or email.strip() == '':
        return False
    
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def validate_age(age_str: str) -> tuple[bool, Optional[int]]:
    """
    Validate and parse age input.
    
    Args:
        age_str: Age string to validate
        
    Returns:
        tuple: (is_valid, parsed_age_or_none)
    """
    try:
        age = int(age_str.strip())
        if 1 <= age <= 120:
            return True, age
        return False, None
    except (ValueError, AttributeError):
        return False, None


def format_complaint_details(complaint_data: Dict[str, Any], is_arabic: bool) -> str:
    """
    Format complaint details for review display.
    
    Args:
        complaint_data: Dictionary containing complaint information
        is_arabic: True for Arabic formatting, False for English
        
    Returns:
        str: Formatted complaint details string
    """
    if is_arabic:
        details = f"""الاسم: {complaint_data.get('name', 'غير محدد')}
الهاتف: {complaint_data.get('phone', 'غير محدد')}"""
        
        if complaint_data.get('email'):
            details += f"\nالبريد الإلكتروني: {complaint_data['email']}"
        
        if complaint_data.get('sex'):
            details += f"\nالجنس: {complaint_data['sex']}"
        
        if complaint_data.get('age'):
            details += f"\nالعمر: {complaint_data['age']}"
        
        details += f"\nوصف الشكوى: {complaint_data.get('description', 'غير محدد')}"
        
        if complaint_data.get('location'):
            details += f"\nالموقع: {complaint_data['location']}"
            
    else:
        details = f"""Name: {complaint_data.get('name', 'Not specified')}
Phone: {complaint_data.get('phone', 'Not specified')}"""
        
        if complaint_data.get('email'):
            details += f"\nEmail: {complaint_data['email']}"
        
        if complaint_data.get('sex'):
            details += f"\nGender: {complaint_data['sex']}"
        
        if complaint_data.get('age'):
            details += f"\nAge: {complaint_data['age']}"
        
        details += f"\nComplaint Description: {complaint_data.get('description', 'Not specified')}"
        
        if complaint_data.get('location'):
            details += f"\nLocation: {complaint_data['location']}"
    
    return details


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to specified length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating
        
    Returns:
        str: Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def sanitize_input(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize user input by removing unwanted characters and limiting length.
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length (optional)
        
    Returns:
        str: Sanitized text
    """
    if not text:
        return ""
    
    # Strip whitespace
    sanitized = text.strip()
    
    # Remove or replace problematic characters if needed
    sanitized = sanitized.replace('\x00', '')  # Remove null bytes
    
    # Limit length if specified
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def get_next_step_keyboard(bot_instance: 'InstitutionBot', is_arabic: bool) -> ReplyKeyboardMarkup:
    """
    Create a keyboard with Next and Back options.
    
    Args:
        bot_instance: InstitutionBot instance
        is_arabic: True for Arabic, False for English
        
    Returns:
        ReplyKeyboardMarkup: Next/Back keyboard
    """
    keyboard = [
        [
            KeyboardButton(get_message('btn_next', bot_instance, is_arabic)),
            KeyboardButton(get_message('btn_back', bot_instance, is_arabic))
        ],
        [KeyboardButton(get_message('btn_main_menu', bot_instance, is_arabic))]
    ]
    
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_submit_keyboard(bot_instance: 'InstitutionBot', is_arabic: bool) -> ReplyKeyboardMarkup:
    """
    Create a keyboard with Submit and Cancel options.
    
    Args:
        bot_instance: InstitutionBot instance
        is_arabic: True for Arabic, False for English
        
    Returns:
        ReplyKeyboardMarkup: Submit/Cancel keyboard
    """
    keyboard = [
        [
            KeyboardButton(get_message('btn_submit_confirm', bot_instance, is_arabic)),
            KeyboardButton(get_message('btn_cancel', bot_instance, is_arabic))
        ]
    ]
    
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_new_reminder_inline_keyboard(bot_instance: 'InstitutionBot', is_arabic: bool) -> InlineKeyboardMarkup:
    """
    Create an inline keyboard for choosing between new complaint or reminder.
    
    Args:
        bot_instance: InstitutionBot instance
        is_arabic: True for Arabic, False for English
        
    Returns:
        InlineKeyboardMarkup: New/Reminder inline keyboard
    """
    keyboard = [
        [InlineKeyboardButton(
            get_message('btn_new_complaint', bot_instance, is_arabic),
            callback_data="complaint_flow:new"
        )],
        [InlineKeyboardButton(
            get_message('btn_reminder_previous', bot_instance, is_arabic),
            callback_data="complaint_flow:reminder"
        )]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_profile_inline_keyboard(bot_instance: 'InstitutionBot', is_arabic: bool) -> InlineKeyboardMarkup:
    """
    Create an inline keyboard for confirming profile data usage.
    
    Args:
        bot_instance: InstitutionBot instance
        is_arabic: True for Arabic, False for English
        
    Returns:
        InlineKeyboardMarkup: Confirm profile inline keyboard
    """
    keyboard = [
        [InlineKeyboardButton(
            get_message('btn_yes_use_data', bot_instance, is_arabic),
            callback_data="profile_confirm:yes"
        )],
        [InlineKeyboardButton(
            get_message('btn_no_new_data', bot_instance, is_arabic),
            callback_data="profile_confirm:no"
        )]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_complaint_text_choice_inline_keyboard(bot_instance: 'InstitutionBot', is_arabic: bool) -> InlineKeyboardMarkup:
    """
    Create an inline keyboard for choosing between original or new complaint text.
    
    Args:
        bot_instance: InstitutionBot instance
        is_arabic: True for Arabic, False for English
        
    Returns:
        InlineKeyboardMarkup: Text choice inline keyboard
    """
    keyboard = [
        [InlineKeyboardButton(
            get_message('complaint_use_original_text', bot_instance, is_arabic),
            callback_data="complaint_text_choice:use_original"
        )],
        [InlineKeyboardButton(
            get_message('complaint_write_new_text', bot_instance, is_arabic),
            callback_data="complaint_text_choice:write_new"
        )]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_final_submission_inline_keyboard(bot_instance: 'InstitutionBot', is_arabic: bool, prefix: str = "final_submission") -> InlineKeyboardMarkup:
    """
    Create an inline keyboard for final submission confirmation.
    
    Args:
        bot_instance: InstitutionBot instance
        is_arabic: True for Arabic, False for English
        prefix: Prefix for callback data (default: "final_submission")
        
    Returns:
        InlineKeyboardMarkup: Final submission inline keyboard
    """
    keyboard = [
        [InlineKeyboardButton(
            get_message('btn_submit_final', bot_instance, is_arabic),
            callback_data=f"{prefix}:confirm"
        )],
        [InlineKeyboardButton(
            get_message('btn_cancel_submission', bot_instance, is_arabic),
            callback_data=f"{prefix}:cancel"
        )]
    ]
    return InlineKeyboardMarkup(keyboard)