I would like you to rebuild the entry_point_handlers.py file based on the following specifications:

Technical Modification Brief: Removing Redundant Text-Based Entry Logic

File to be Modified: app/bot/handlers/entry_point_handlers.py

Objective:
To align this module with the new command-only entry point strategy by removing the now-obsolete logic for handling initial text messages.

Required Modifications:

Delete the handle_initial_text_message Function:

Locate the entire async def handle_initial_text_message(...) function block.

Delete this function completely. Since it is no longer referenced in main_conversation_handler.py, it serves no purpose and should be removed to maintain code cleanliness.

Verify Remaining Functions:

The start_command function should remain exactly as it is, as it is now the sole entry point.

The handle_initial_action_selection function (which handles button presses after /start) should also remain unchanged.

Outcome of Modifications:
This file will now be simplified and will only contain the handlers that are actively used in the new, more stable conversation flow. By removing the unused code, the module becomes easier to read, understand, and maintain, and it eliminates the risk of the obsolete function being called by mistake in the future.