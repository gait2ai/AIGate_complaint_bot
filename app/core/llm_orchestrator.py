"""
LLM Orchestrator Module

This module contains the LLMOrchestrator class responsible for managing 
the specialized interaction flow with the Large Language Model (LLM) for 
the initial intent analysis of user messages within the Institution Complaint 
Management Bot.
"""

import json
import logging
import re
from typing import Tuple, Optional, Dict, Any, List

# Adjust import paths based on your project structure
from .prompt_builder import PromptBuilder
from .ai_handler import AIHandler
# Alternative imports:
# from app.core.prompt_builder import PromptBuilder
# from app.core.ai_handler import AIHandler


class LLMOrchestrator:
    """
    Orchestrates AI-driven user interactions for initial intent analysis.
    
    This class abstracts the complexities of prompt generation, LLM communication,
    and structured response parsing for the "first contact" scenario in the
    Institution Complaint Management Bot. It focuses exclusively on determining
    the user's initial intent from their first message.
    """
    
    # Predefined valid signals that the LLM can return for initial intent analysis
    VALID_SIGNALS = {
        "COMPLAINT_START",
        "SUGGESTION_START", 
        "GENERAL_INQUIRY",
        "IRRELEVANT"
    }
    
    def __init__(self, prompt_builder: PromptBuilder, ai_handler: AIHandler):
        """
        Initialize the LLMOrchestrator with required dependencies.
        
        Args:
            prompt_builder: Instance of PromptBuilder for generating prompts
            ai_handler: Instance of AIHandler for LLM communication
            
        Raises:
            ValueError: If either dependency is not provided
        """
        if not isinstance(prompt_builder, PromptBuilder):
            raise ValueError("prompt_builder must be an instance of PromptBuilder")
        
        if not isinstance(ai_handler, AIHandler):
            raise ValueError("ai_handler must be an instance of AIHandler")
        
        self.prompt_builder = prompt_builder
        self.ai_handler = ai_handler
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("LLMOrchestrator initialized successfully")
    
    async def analyze_initial_message(
        self,
        user_input_text: str,
        user_first_name: str,
        institution_name: str,
        current_date_time: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Analyze the initial user message and determine appropriate intent.
        
        Args:
            user_input_text: The raw text message from the user
            user_first_name: The first name of the user (from Telegram API)
            institution_name: The name of the institution
            current_date_time: Optional ISO formatted current date/time string
            
        Returns:
            Tuple containing:
            - signal (str): Intent signal determined by LLM
            - response_text (str): Primary textual output from LLM with placeholders formatted
        """
        self.logger.info(
            f"Starting initial intent analysis for user: {user_first_name}, "
            f"institution: {institution_name}"
        )
        
        try:
            # Step 1: Generate system prompt via PromptBuilder
            system_prompt = await self._generate_system_prompt(
                user_input_text=user_input_text,
                user_first_name=user_first_name,
                institution_name=institution_name,
                current_date_time=current_date_time
            )
            
            # Step 2: Send request to LLM via AIHandler
            llm_raw_response = await self._call_llm(system_prompt)
            
            # Step 3: Parse LLM's JSON response
            parsed_response = self._parse_llm_response(llm_raw_response)
            
            # Step 4: Validate parsed data
            signal, response_text = self._validate_and_extract_data(parsed_response)
            
            # Step 5: Format response text with actual values
            final_response_text = response_text.format(
                institution_name=self.prompt_builder.institution_config.name
            )
            
            # Step 6: Log successful outcome
            self.logger.info(
                f"Intent analysis completed successfully. Signal: {signal}, "
                f"Response length: {len(final_response_text)} chars"
            )
            
            return signal, final_response_text
            
        except Exception as e:
            # Comprehensive error handling
            self.logger.error(
                f"Error during initial intent analysis: {str(e)}", 
                exc_info=True
            )
            
            # Return safe default response with formatting applied
            signal, response_text = self._get_safe_default_response()
            final_default_text = response_text.format(
                institution_name=self.prompt_builder.institution_config.name
            )
            return signal, final_default_text
    
    async def _generate_system_prompt(
        self,
        user_input_text: str,
        user_first_name: str,
        institution_name: str,
        current_date_time: Optional[str]
    ) -> str:
        """
        Generate the system prompt using PromptBuilder's dedicated method.
        
        Args:
            user_input_text: User's input text
            user_first_name: User's first name
            institution_name: Institution name
            current_date_time: Current date/time string
            
        Returns:
            Generated system prompt string
            
        Raises:
            Exception: If prompt generation fails
        """
        try:
            # Call the dedicated PromptBuilder method for initial interaction
            system_prompt = await self.prompt_builder.generate_initial_interaction_prompt(
                user_input_text=user_input_text,
                user_first_name=user_first_name,
                institution_name=institution_name,
                current_date_time=current_date_time
            )
            
            self.logger.debug("System prompt generated successfully")
            return system_prompt
            
        except Exception as e:
            self.logger.error(f"Failed to generate system prompt: {str(e)}")
            raise
    
    async def _call_llm(self, system_prompt: str) -> str:
        """
        Call the LLM via AIHandler with the generated system prompt.
        
        Args:
            system_prompt: The complete system prompt
            
        Returns:
            Raw string response from the LLM
            
        Raises:
            Exception: If LLM call fails
        """
        try:
            # Use minimal or empty user message since system prompt contains everything
            llm_response = await self.ai_handler.generate_response(
                system_prompt=system_prompt,
                user_message=""  # Empty as system prompt contains user input
            )
            
            self.logger.debug(f"LLM response received, length: {len(llm_response)} chars")
            return llm_response
            
        except Exception as e:
            self.logger.error(f"Failed to get LLM response: {str(e)}")
            raise
    
    def _parse_llm_response(self, raw_response: str) -> Dict[str, Any]:
        """
        Parse the LLM's JSON response string, now with flexible extraction.
        This function attempts to find a JSON object embedded within the raw text response.
        
        Args:
            raw_response: Raw string response from LLM
            
        Returns:
            Parsed JSON dictionary
            
        Raises:
            json.JSONDecodeError: If JSON parsing fails
        """
        self.logger.debug(f"Attempting to parse raw LLM response: {raw_response[:200]}...")
        
        try:
            # First, try to parse the whole string directly
            return json.loads(raw_response)
        except json.JSONDecodeError:
            # If that fails, search for a JSON object within the string
            self.logger.warning("Direct JSON parsing failed. Searching for embedded JSON object...")
            
            # Regex to find a string that starts with { and ends with }
            # It handles nested braces.
            match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            
            if match:
                json_part = match.group(0)
                self.logger.info(f"Found potential JSON part: {json_part[:200]}...")
                try:
                    # Try to parse the extracted part
                    return json.loads(json_part)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse extracted JSON part: {e}")
                    self.logger.debug(f"Extracted part was: {json_part}")
                    raise  # Re-raise the exception to be caught by the calling function
            else:
                self.logger.error("No JSON object found in the LLM response.")
                raise json.JSONDecodeError("No JSON object found in response", raw_response, 0)
    
    def _validate_and_extract_data(
        self, 
        parsed_response: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Validate the parsed LLM response and extract required data.
        
        Args:
            parsed_response: Parsed JSON response from LLM
            
        Returns:
            Tuple of (signal, response_text)
        """
        # Extract basic fields
        signal = parsed_response.get("signal")
        response_text = parsed_response.get("response_text")
        
        # Validate signal
        if not isinstance(signal, str) or not signal:
            self.logger.warning("Invalid or missing signal in LLM response")
            signal = "GENERAL_INQUIRY"
        
        # Check if signal is valid
        if signal not in self.VALID_SIGNALS:
            self.logger.warning(f"Unknown signal received: {signal}")
            signal = "GENERAL_INQUIRY"
        
        # Validate response_text
        if not isinstance(response_text, str) or not response_text:
            self.logger.warning("Invalid or missing response_text in LLM response")
            response_text = "I'm having trouble processing your message. Could you please try rephrasing?"
        
        self.logger.debug(f"Data validation completed for signal: {signal}")
        return signal, response_text
    
    def _get_safe_default_response(self) -> Tuple[str, str]:
        """
        Get a safe default response for error scenarios.
        
        Returns:
            Safe default tuple (signal, response_text)
        """
        return (
            "GENERAL_INQUIRY",
            "I'm encountering a technical issue. Could you please try rephrasing or try again shortly?"
        )
    
    async def cleanup(self):
        """
        Clean up resources (optional method for future extensibility).
        
        Currently a no-op as dependencies handle their own cleanup.
        """
        self.logger.debug("LLMOrchestrator cleanup called")
        # No cleanup needed for this class as dependencies handle their own cleanup
        pass