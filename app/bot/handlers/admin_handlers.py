"""
AI Gate for Artificial Intelligence Applications
Administrative Handlers Module for Institution Complaint Management Bot

This module provides administrative functionality for authorized users, including
complaint statistics viewing, data export capabilities, and system monitoring.
All administrative functions are protected by authorization checks.

Author: Institution Complaint Management Bot Team
"""

import logging
from functools import wraps
from typing import Dict, Any, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, 
    CallbackQueryHandler, MessageHandler, filters
)

# Import state definitions
from app.bot.states import (
    ADMIN_MENU, ADMIN_VIEW_STATS, ADMIN_EXPORT_DATA,
    get_state_name
)

# Import utilities
from app.bot.utils import (
    get_message, 
    get_user_preferred_language_is_arabic,
    escape_markdown_v2,
    send_typing_action
)

# Setup logger
logger = logging.getLogger(__name__)


def admin_only(func):
    """
    Decorator to ensure only authorized administrators can access certain functions.
    
    Args:
        func: The handler function to protect
        
    Returns:
        Wrapped function that performs authorization check
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Get user ID from update
        user_id = None
        if update.message:
            user_id = update.message.from_user.id
        elif update.callback_query:
            user_id = update.callback_query.from_user.id
            
        if not user_id:
            logger.warning("Could not determine user ID for admin check")
            return ConversationHandler.END
            
        # Get bot instance from context
        bot_instance = context.bot_data.get('bot_instance')
        if not bot_instance:
            logger.error("Bot instance not found in context for admin check")
            is_arabic = True  # Default to Arabic if we can't determine
            await update.effective_message.reply_text(
                get_message('error_generic', bot_instance, is_arabic)
            )
            return ConversationHandler.END
            
        # Check if user is admin
        if not bot_instance.is_admin(user_id):
            logger.warning(f"Unauthorized admin access attempt by user {user_id}")
            is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
            await update.effective_message.reply_text(
                get_message('error_permission', bot_instance, is_arabic)
            )
            return ConversationHandler.END
            
        # User is authorized, proceed with original function
        return await func(update, context)
    
    return wrapper


def escape_markdown_v2_safe(text: str) -> str:
    """
    Safely escape MarkdownV2 special characters, including decimal points.
    
    Args:
        text: The text to escape
        
    Returns:
        str: Text with all MarkdownV2 special characters properly escaped
    """
    if not isinstance(text, str):
        text = str(text)
    
    # Characters that need to be escaped in MarkdownV2
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text


@admin_only
@send_typing_action
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point for administrative interface.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        int: Next conversation state (ADMIN_MENU)
    """
    user = update.effective_user
    logger.info(f"Admin interface accessed by user {user.id} ({user.first_name})")
    
    bot_instance = context.bot_data.get('bot_instance')
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    
    # Create admin menu keyboard
    keyboard = [
        [InlineKeyboardButton(
            get_message('admin_option_stats', bot_instance, is_arabic),
            callback_data="admin_stats"
        )],
        [InlineKeyboardButton(
            get_message('admin_option_export', bot_instance, is_arabic),
            callback_data="admin_export"
        )],
        [InlineKeyboardButton(
            get_message('btn_exit', bot_instance, is_arabic),
            callback_data="admin_exit"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = get_message(
        'admin_welcome',
        bot_instance,
        is_arabic,
        user_first_name=escape_markdown_v2_safe(user.first_name)
    )
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup,
        parse_mode='MarkdownV2'
    )
    
    return ADMIN_MENU


async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle admin menu button selections.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        int: Next conversation state or ConversationHandler.END
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    choice = query.data
    
    logger.info(f"Admin menu choice '{choice}' by user {user_id}")
    
    if choice == "admin_stats":
        return await show_statistics(update, context)
    elif choice == "admin_export":
        return await export_data(update, context)
    elif choice == "admin_exit":
        return await admin_exit(update, context)
    else:
        bot_instance = context.bot_data.get('bot_instance')
        is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
        await query.edit_message_text(
            get_message('error_invalid_selection', bot_instance, is_arabic)
        )
        return ADMIN_MENU


@admin_only
async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Display complaint statistics to the administrator.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        int: ADMIN_MENU state to return to menu
    """
    query = update.callback_query
    user_id = query.from_user.id
    bot_instance = context.bot_data.get('bot_instance')
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    
    try:
        # Show loading message
        await query.edit_message_text(
            get_message('admin_stats_loading', bot_instance, is_arabic)
        )
        
        # Get bot instance and fetch statistics
        if not bot_instance:
            await query.edit_message_text(
                get_message('error_generic', bot_instance, is_arabic)
            )
            return ConversationHandler.END
            
        stats = await bot_instance.get_complaint_statistics()
        
        # Format statistics message
        stats_message = format_statistics_message(stats, bot_instance, is_arabic)
        
        # Create back button
        keyboard = [[InlineKeyboardButton(
            get_message('btn_back_to_admin', bot_instance, is_arabic),
            callback_data="admin_back"
        )]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            stats_message,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
        
        logger.info(f"Statistics displayed to admin user {user_id}")
        return ADMIN_VIEW_STATS
        
    except Exception as e:
        logger.error(f"Error displaying statistics for user {user_id}: {e}")
        await query.edit_message_text(
            get_message('error_generic', bot_instance, is_arabic)
        )
        return ADMIN_MENU


@admin_only
async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle data export request (placeholder implementation).
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        int: ADMIN_MENU state to return to menu
    """
    query = update.callback_query
    user_id = query.from_user.id
    bot_instance = context.bot_data.get('bot_instance')
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    
    logger.info(f"Data export requested by admin user {user_id}")
    
    # Create back button
    keyboard = [[InlineKeyboardButton(
        get_message('btn_back_to_admin', bot_instance, is_arabic),
        callback_data="admin_back"
    )]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        get_message('admin_export_placeholder', bot_instance, is_arabic),
        reply_markup=reply_markup,
        parse_mode='MarkdownV2'
    )
    
    return ADMIN_EXPORT_DATA


async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Return to the main admin menu.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        int: ADMIN_MENU state
    """
    query = update.callback_query
    await query.answer()
    
    bot_instance = context.bot_data.get('bot_instance')
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    
    # Recreate admin menu
    keyboard = [
        [InlineKeyboardButton(
            get_message('admin_option_stats', bot_instance, is_arabic),
            callback_data="admin_stats"
        )],
        [InlineKeyboardButton(
            get_message('admin_option_export', bot_instance, is_arabic),
            callback_data="admin_export"
        )],
        [InlineKeyboardButton(
            get_message('btn_exit', bot_instance, is_arabic),
            callback_data="admin_exit"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        get_message('admin_menu_prompt', bot_instance, is_arabic),
        reply_markup=reply_markup,
        parse_mode='MarkdownV2'
    )
    
    return ADMIN_MENU


async def admin_exit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Exit the admin conversation.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        int: ConversationHandler.END
    """
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    logger.info(f"Admin session ended by user {user.id} ({user.first_name})")
    
    bot_instance = context.bot_data.get('bot_instance')
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    
    await query.edit_message_text(
        get_message('admin_exit_message', bot_instance, is_arabic),
        parse_mode='MarkdownV2'
    )
    
    return ConversationHandler.END


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle /cancel command in admin conversation.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        int: ConversationHandler.END
    """
    user = update.effective_user
    logger.info(f"Admin conversation cancelled by user {user.id}")
    
    bot_instance = context.bot_data.get('bot_instance')
    is_arabic = get_user_preferred_language_is_arabic(update, bot_instance)
    
    await update.message.reply_text(
        get_message('admin_cancel_message', bot_instance, is_arabic)
    )
    
    return ConversationHandler.END


def format_statistics_message(stats: Dict[str, Any], bot_instance: Any, is_arabic: bool) -> str:
    """
    Format complaint statistics into a readable message.
    
    Args:
        stats: Dictionary containing complaint statistics
        bot_instance: Bot instance for message localization
        is_arabic: Whether to use Arabic language
        
    Returns:
        str: Formatted statistics message with MarkdownV2 escaping
    """
    try:
        total = stats.get('total_complaints', 0)
        critical = stats.get('critical_complaints', 0)
        status_counts = stats.get('status_counts', {})
        
        # Calculate percentages
        critical_percentage = (critical / total * 100) if total > 0 else 0
        
        # Escape all numerical values using our safe function
        total_escaped = escape_markdown_v2_safe(str(total))
        critical_escaped = escape_markdown_v2_safe(str(critical))
        critical_percentage_escaped = escape_markdown_v2_safe(f"{critical_percentage:.1f}")
        
        message_parts = [
            get_message('admin_stats_header', bot_instance, is_arabic),
            get_message('admin_stats_total', bot_instance, is_arabic, count=total_escaped),
            get_message('admin_stats_critical', bot_instance, is_arabic, 
                       count=critical_escaped, percentage=critical_percentage_escaped)
        ]
        
        if status_counts:
            message_parts.append(get_message('admin_stats_breakdown', bot_instance, is_arabic))
            for status, count in sorted(status_counts.items()):
                percentage = (count / total * 100) if total > 0 else 0
                
                # Escape all dynamic values for this status
                count_escaped = escape_markdown_v2_safe(str(count))
                percentage_escaped = escape_markdown_v2_safe(f"{percentage:.1f}")
                
                # Get status display name with fallback and escape it
                status_message = get_message(f'status_{status.lower()}', bot_instance, is_arabic)
                if not status_message or status_message == f'status_{status.lower()}':
                    # Fallback to the raw status if no translation found
                    status_message = status
                status_display = escape_markdown_v2_safe(status_message)
                
                message_parts.append(
                    get_message('admin_stats_item', bot_instance, is_arabic,
                              status=status_display, count=count_escaped, percentage=percentage_escaped)
                )
        else:
            message_parts.append(get_message('admin_stats_no_data', bot_instance, is_arabic))
        
        # Add timestamp with proper escaping
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp_escaped = escape_markdown_v2_safe(timestamp)
        message_parts.append(
            get_message('admin_stats_timestamp', bot_instance, is_arabic, timestamp=timestamp_escaped)
        )
        
        return "\n".join(message_parts)
        
    except Exception as e:
        logger.error(f"Error formatting statistics message: {e}")
        return escape_markdown_v2_safe(
            get_message('error_generic', bot_instance, is_arabic)
        )


def get_admin_conversation_handler() -> ConversationHandler:
    """
    Create and return the administrative ConversationHandler.
    
    Returns:
        ConversationHandler: Configured conversation handler for admin functionality
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler('admin', admin_start)
        ],
        states={
            ADMIN_MENU: [
                CallbackQueryHandler(admin_menu_handler, pattern=r"^admin_(stats|export|exit)$")
            ],
            ADMIN_VIEW_STATS: [
                CallbackQueryHandler(admin_back, pattern="^admin_back$")
            ],
            ADMIN_EXPORT_DATA: [
                CallbackQueryHandler(admin_back, pattern="^admin_back$")
            ]
        },
        fallbacks=[
            CommandHandler('cancel', admin_cancel)
        ],
        name="admin_conversation",
        persistent=False,
        allow_reentry=True
    )


# Export the main function for easy importing
__all__ = ['get_admin_conversation_handler']