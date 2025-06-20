"""
AI Gate for Artificial Intelligence Applications
Shared State Definitions Module for Institution Complaint Management Bot

Centralized Conversation State Definitions for Institution Complaint Management Bot

This module serves as the central repository for all conversation state constants
used throughout the bot application. It ensures consistent state management and 
simplifies transitions between different conversation handlers.

All states are defined as sequential integers starting from 0, making them suitable
for use with python-telegram-bot's ConversationHandler.

Author: Institution Complaint Management Bot Team
"""

# Define all conversation states as sequential integers
(
    # Entry Point & Initial Action States
    SELECTING_INITIAL_ACTION,           # For handling user's choice after /start or AI greeting (e.g., Complaint, Suggestion)

    # Complaint Flow States
    ASK_NEW_OR_REMINDER,               # Asks if user wants new complaint or reminder about previous one
    HANDLE_NEW_OR_REMINDER_CHOICE,     # Processes the choice from ASK_NEW_OR_REMINDER (CallbackQuery)
    CONFIRM_EXISTING_PROFILE,          # Asks user to confirm using existing profile data (CallbackQuery expected)
    
    # Profile Collection States
    COLLECTING_NAME,                   # Collecting user's full name
    COLLECTING_SEX,                    # Collecting user's gender/sex
    COLLECTING_PHONE,                  # Collecting user's phone number
    COLLECTING_RESIDENCE,              # Collecting user's residence status/type
    COLLECTING_GOVERNORATE,            # Collecting user's governorate
    COLLECTING_DIRECTORATE,            # Collecting user's directorate/district
    COLLECTING_VILLAGE,                # Collecting user's village/area
    
    # Complaint Content States
    CHOOSING_COMPLAINT_TEXT,           # For user to choose using LLM-derived text or writing new (CallbackQuery)
    COLLECTING_COMPLAINT_TEXT,         # Collecting the actual complaint text from user
    CONFIRM_SUBMISSION,                # For user to confirm all details before final submission (CallbackQuery)

    # Critical Complaint Flow States (Expedited process for urgent matters)
    CRITICAL_COLLECTING_NAME,          # Collecting name for critical complaints
    CRITICAL_COLLECTING_PHONE,         # Collecting phone for critical complaints

    # Suggestion/Feedback Flow States
    COLLECTING_SUGGESTION_TEXT,        # Collecting suggestion or feedback text from user
    CONFIRM_SUGGESTION_SUBMISSION,     # Optional confirmation step for suggestions

    # Administrative States
    ADMIN_MENU,                        # Administrative menu for authorized users
    ADMIN_VIEW_STATS,                  # Viewing complaint statistics
    ADMIN_EXPORT_DATA,                 # Exporting complaint data
    
    # Error Handling States
    HANDLING_ERROR,                    # Generic error handling state
    RETRY_INPUT,                       # Asking user to retry their input
    
    # Utility States
    WAITING_FOR_INPUT,                 # Generic waiting state
    PROCESSING_REQUEST,                # Processing user request state
    
    # Reserved States for Future Expansion
    RESERVED_STATE_1,                  # Reserved for future features
    RESERVED_STATE_2,                  # Reserved for future features
    RESERVED_STATE_3,                  # Reserved for future features
    RESERVED_STATE_4,                  # Reserved for future features
    RESERVED_STATE_5,                  # Reserved for future features

) = range(30)  # Adjust range as needed for future expansion


# State name mapping for logging and debugging purposes
STATE_NAMES = {
    # Entry Point & Initial Action States
    SELECTING_INITIAL_ACTION: "SELECTING_INITIAL_ACTION",
    
    # Complaint Flow States
    ASK_NEW_OR_REMINDER: "ASK_NEW_OR_REMINDER",
    HANDLE_NEW_OR_REMINDER_CHOICE: "HANDLE_NEW_OR_REMINDER_CHOICE",
    CONFIRM_EXISTING_PROFILE: "CONFIRM_EXISTING_PROFILE",
    
    # Profile Collection States
    COLLECTING_NAME: "COLLECTING_NAME",
    COLLECTING_SEX: "COLLECTING_SEX",
    COLLECTING_PHONE: "COLLECTING_PHONE",
    COLLECTING_RESIDENCE: "COLLECTING_RESIDENCE",
    COLLECTING_GOVERNORATE: "COLLECTING_GOVERNORATE",
    COLLECTING_DIRECTORATE: "COLLECTING_DIRECTORATE",
    COLLECTING_VILLAGE: "COLLECTING_VILLAGE",
    
    # Complaint Content States
    CHOOSING_COMPLAINT_TEXT: "CHOOSING_COMPLAINT_TEXT",
    COLLECTING_COMPLAINT_TEXT: "COLLECTING_COMPLAINT_TEXT",
    CONFIRM_SUBMISSION: "CONFIRM_SUBMISSION",
    
    # Critical Complaint Flow States
    CRITICAL_COLLECTING_NAME: "CRITICAL_COLLECTING_NAME",
    CRITICAL_COLLECTING_PHONE: "CRITICAL_COLLECTING_PHONE",
    
    # Suggestion/Feedback Flow States
    COLLECTING_SUGGESTION_TEXT: "COLLECTING_SUGGESTION_TEXT",
    CONFIRM_SUGGESTION_SUBMISSION: "CONFIRM_SUGGESTION_SUBMISSION",
    
    # Administrative States
    ADMIN_MENU: "ADMIN_MENU",
    ADMIN_VIEW_STATS: "ADMIN_VIEW_STATS",
    ADMIN_EXPORT_DATA: "ADMIN_EXPORT_DATA",
    
    # Error Handling States
    HANDLING_ERROR: "HANDLING_ERROR",
    RETRY_INPUT: "RETRY_INPUT",
    
    # Utility States
    WAITING_FOR_INPUT: "WAITING_FOR_INPUT",
    PROCESSING_REQUEST: "PROCESSING_REQUEST",
    
    # Reserved States
    RESERVED_STATE_1: "RESERVED_STATE_1",
    RESERVED_STATE_2: "RESERVED_STATE_2",
    RESERVED_STATE_3: "RESERVED_STATE_3",
    RESERVED_STATE_4: "RESERVED_STATE_4",
    RESERVED_STATE_5: "RESERVED_STATE_5",
}


def get_state_name(state_code: int) -> str:
    """
    Get the human-readable name for a state code.
    
    This function is particularly useful for logging, debugging, and monitoring
    conversation flows. It provides clear, readable state names instead of 
    raw integer values.
    
    Args:
        state_code (int): The integer state code to look up
        
    Returns:
        str: Human-readable state name or "UNKNOWN_STATE_<code>" if the 
             state code is not found in the STATE_NAMES dictionary
             
    Example:
        >>> get_state_name(COLLECTING_NAME)
        'COLLECTING_NAME'
        >>> get_state_name(999)
        'UNKNOWN_STATE_999'
    """
    return STATE_NAMES.get(state_code, f"UNKNOWN_STATE_{state_code}")


def is_valid_state(state_code: int) -> bool:
    """
    Check if a state code is valid (exists in our defined states).
    
    Args:
        state_code (int): The state code to validate
        
    Returns:
        bool: True if the state code is valid, False otherwise
        
    Example:
        >>> is_valid_state(COLLECTING_NAME)
        True
        >>> is_valid_state(999)
        False
    """
    return state_code in STATE_NAMES


def get_all_states() -> list[int]:
    """
    Get a list of all defined state codes.
    
    Returns:
        list[int]: List of all valid state codes
        
    Example:
        >>> states = get_all_states()
        >>> len(states)
        25
    """
    return list(STATE_NAMES.keys())


def get_states_by_category() -> dict[str, list[int]]:
    """
    Get states organized by their functional categories.
    
    Returns:
        dict[str, list[int]]: Dictionary with category names as keys and 
                              lists of state codes as values
                              
    Example:
        >>> categories = get_states_by_category()
        >>> categories['complaint_flow']
        [1, 2, 3, ...]
    """
    return {
        'entry_point': [SELECTING_INITIAL_ACTION],
        'complaint_flow': [
            ASK_NEW_OR_REMINDER, HANDLE_NEW_OR_REMINDER_CHOICE, 
            CONFIRM_EXISTING_PROFILE, CHOOSING_COMPLAINT_TEXT,
            COLLECTING_COMPLAINT_TEXT, CONFIRM_SUBMISSION
        ],
        'profile_collection': [
            COLLECTING_NAME, COLLECTING_SEX, COLLECTING_PHONE,
            COLLECTING_RESIDENCE, COLLECTING_GOVERNORATE,
            COLLECTING_DIRECTORATE, COLLECTING_VILLAGE
        ],
        'critical_flow': [CRITICAL_COLLECTING_NAME, CRITICAL_COLLECTING_PHONE],
        'suggestion_flow': [COLLECTING_SUGGESTION_TEXT, CONFIRM_SUGGESTION_SUBMISSION],
        'administrative': [ADMIN_MENU, ADMIN_VIEW_STATS, ADMIN_EXPORT_DATA],
        'error_handling': [HANDLING_ERROR, RETRY_INPUT],
        'utility': [WAITING_FOR_INPUT, PROCESSING_REQUEST],
        'reserved': [RESERVED_STATE_1, RESERVED_STATE_2, RESERVED_STATE_3, 
                    RESERVED_STATE_4, RESERVED_STATE_5]
    }
