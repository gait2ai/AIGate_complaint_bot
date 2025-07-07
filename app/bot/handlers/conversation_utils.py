#!/usr/bin/env python3
"""
Conversation Utilities Module

This module contains shared utility functions for conversation management
that are used across multiple handler modules. By centralizing these utilities,
we avoid circular import issues between handler modules.

Functions:
    cleanup_conversation_state: Cleans up conversation state for users
    format_complaint_summary: Formats complaint data for display
    validate_user_input: Common input validation logic
"""

import logging
from typing import Dict, Any, Optional
from telegram import Update
from telegram.ext import ContextTypes

# Configure module logger
logger = logging.getLogger(__name__)


async def cleanup_conversation_state(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE,
    reason: str = "conversation_ended"
) -> None:
    """
    Clean up conversation state for a user.
    
    This function removes temporary conversation data, resets user state,
    and performs any necessary cleanup when a conversation ends or is reset.
    
    Args:
        update: The Telegram update object
        context: The callback context
        reason: Reason for cleanup (for logging purposes)
    """
    try:
        user_id = update.effective_user.id
        logger.info(f"Cleaning up conversation state for user {user_id}, reason: {reason}")
        
        # Clean up user_data
        if context.user_data:
            # Preserve essential user data while clearing temporary conversation state
            essential_keys = ['user_preferences', 'language', 'timezone']
            temp_data = {k: v for k, v in context.user_data.items() if k in essential_keys}
            
            context.user_data.clear()
            context.user_data.update(temp_data)
            
            logger.debug(f"Cleared conversation state for user {user_id}, preserved essential data")
        
        # Reset any conversation-specific flags
        context.user_data['conversation_active'] = False
        context.user_data['current_step'] = None
        
        logger.info(f"Successfully cleaned up conversation state for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error cleaning up conversation state: {e}", exc_info=True)


def format_complaint_summary(complaint_data: Dict[str, Any]) -> str:
    """
    Format complaint data into a readable summary.
    
    Args:
        complaint_data: Dictionary containing complaint information
        
    Returns:
        Formatted string summary of the complaint
    """
    try:
        summary_lines = []
        
        # Add complaint ID if available
        if 'complaint_id' in complaint_data:
            summary_lines.append(f"🆔 Complaint ID: {complaint_data['complaint_id']}")
        
        # Add category
        if 'category' in complaint_data:
            summary_lines.append(f"📂 Category: {complaint_data['category']}")
        
        # Add description
        if 'description' in complaint_data:
            desc = complaint_data['description']
            if len(desc) > 100:
                desc = desc[:100] + "..."
            summary_lines.append(f"📝 Description: {desc}")
        
        # Add severity level
        if 'severity' in complaint_data:
            summary_lines.append(f"⚠️ Severity: {complaint_data['severity']}")
        
        # Add timestamp
        if 'timestamp' in complaint_data:
            summary_lines.append(f"⏰ Submitted: {complaint_data['timestamp']}")
        
        return "\n".join(summary_lines)
        
    except Exception as e:
        logger.error(f"Error formatting complaint summary: {e}")
        return "❌ Error formatting complaint summary"


def validate_user_input(
    input_text: str, 
    input_type: str,
    min_length: int = 1,
    max_length: int = 1000
) -> tuple[bool, Optional[str]]:
    """
    Validate user input based on type and constraints.
    
    Args:
        input_text: The user's input text
        input_type: Type of input ('description', 'name', 'email', etc.)
        min_length: Minimum required length
        max_length: Maximum allowed length
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Basic length validation
        if len(input_text) < min_length:
            return False, f"Input too short. Minimum {min_length} characters required."
        
        if len(input_text) > max_length:
            return False, f"Input too long. Maximum {max_length} characters allowed."
        
        # Type-specific validation
        if input_type == 'email':
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, input_text):
                return False, "Please enter a valid email address."
        
        elif input_type == 'description':
            # Check for minimum meaningful content
            if len(input_text.strip()) < 10:
                return False, "Please provide a more detailed description (minimum 10 characters)."
        
        elif input_type == 'name':
            # Basic name validation
            if not input_text.strip():
                return False, "Name cannot be empty."
            
            # Check for reasonable name format
            if len(input_text.strip()) < 2:
                return False, "Name must be at least 2 characters long."
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error validating user input: {e}")
        return False, "An error occurred during validation."


def get_user_display_name(update: Update) -> str:
    """
    Get a user-friendly display name from the update.
    
    Args:
        update: The Telegram update object
        
    Returns:
        User display name (first name, username, or user ID)
    """
    try:
        user = update.effective_user
        if user.first_name:
            return user.first_name
        elif user.username:
            return f"@{user.username}"
        else:
            return f"User_{user.id}"
    except Exception:
        return "Unknown User"


# Conversation state constants
class ConversationStates:
    """Constants for conversation states."""
    INITIAL = "initial"
    COLLECTING_DESCRIPTION = "collecting_description"
    COLLECTING_DETAILS = "collecting_details"
    CONFIRMING_SUBMISSION = "confirming_submission"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Common response templates
class ResponseTemplates:
    """Common response message templates."""
    
    WELCOME = """
👋 Welcome to the Institution Complaint Management System!

I'm here to help you submit and track complaints efficiently.

What would you like to do?
• Submit a new complaint
• Check complaint status
• Get help and information

Please select an option from the menu below.
"""
    
    COMPLAINT_SUBMITTED = """
✅ **Complaint Submitted Successfully!**

Your complaint has been recorded and will be reviewed by our team.

📋 **Summary:**
{summary}

📧 You will receive updates via email if provided.
🔍 You can check the status anytime using your complaint ID.

Thank you for bringing this to our attention.
"""
    
    ERROR_OCCURRED = """
❌ **An error occurred while processing your request.**

Please try again or contact support if the problem persists.

You can:
• Try submitting again
• Contact our support team
• Return to the main menu
"""
    
    INVALID_INPUT = """
⚠️ **Invalid input provided.**

{error_message}

Please try again with the correct format.
"""