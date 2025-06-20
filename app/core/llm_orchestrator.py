"""
LLM Orchestrator Module

This module contains the LLMOrchestrator class responsible for managing 
the specialized interaction flow with the Large Language Model (LLM) for 
the initial analysis of user messages within the Institution Complaint 
Management Bot.
"""

import json
import logging
from typing import Tuple, Optional, Dict, Any, List

# Adjust import paths based on your project structure
from .prompt_builder import PromptBuilder
from .ai_handler import AIHandler
# Alternative imports:
# from app.core.prompt_builder import PromptBuilder
# from app.core.ai_handler import AIHandler


class LLMOrchestrator:
    """
    Orchestrates AI-driven user interactions for initial message analysis.
    
    This class abstracts the complexities of prompt generation, LLM communication,
    and structured response parsing for the "first contact" scenario in the
    Institution Complaint Management Bot.
    """
    
    # Predefined valid signals that the LLM can return
    VALID_SIGNALS = {
        "GREETING_START",
        "OFF_TOPIC_REPLY", 
        "CLARIFICATION_NEEDED",
        "COMPLAINT_NORMAL",
        "COMPLAINT_CRITICAL",
        "INFORMATION_REQUEST",
        "FOLLOW_UP_QUESTION"
    }
    
    # Signals that require user_facing_summary
    COMPLAINT_SIGNALS = {"COMPLAINT_NORMAL", "COMPLAINT_CRITICAL"}
    
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
        critical_complaint_criteria: Optional[List[str]] = None,
        current_date_time: Optional[str] = None
    ) -> Tuple[str, str, Optional[str]]:
        """
        Analyze the initial user message and determine appropriate response.
        
        Args:
            user_input_text: The raw text message from the user
            user_first_name: The first name of the user (from Telegram API)
            institution_name: The name of the institution
            critical_complaint_criteria: Optional list of criteria for critical complaints
            current_date_time: Optional ISO formatted current date/time string
            
        Returns:
            Tuple containing:
            - signal (str): Action signal determined by LLM
            - llm_response_text (str): Primary textual output from LLM
            - user_facing_summary (Optional[str]): User-facing summary (only for complaints)
        """
        self.logger.info(
            f"Starting initial message analysis for user: {user_first_name}, "
            f"institution: {institution_name}"
        )
        
        try:
            # Step 1: Prepare data for PromptBuilder
            formatted_criteria = self._format_critical_complaint_criteria(
                critical_complaint_criteria
            )
            
            # Step 2: Generate system prompt via PromptBuilder
            system_prompt = await self._generate_system_prompt(
                user_input_text=user_input_text,
                user_first_name=user_first_name,
                institution_name=institution_name,
                formatted_criteria=formatted_criteria,
                current_date_time=current_date_time
            )
            
            # Step 3: Send request to LLM via AIHandler
            llm_raw_response = await self._call_llm(system_prompt)
            
            # Step 4: Parse LLM's JSON response
            parsed_response = self._parse_llm_response(llm_raw_response)
            
            # Step 5: Validate parsed data
            signal, llm_response_text, user_facing_summary = self._validate_and_extract_data(
                parsed_response
            )
            
            # Step 6: Log successful outcome
            self.logger.info(
                f"Analysis completed successfully. Signal: {signal}, "
                f"Response length: {len(llm_response_text)} chars"
            )
            
            return signal, llm_response_text, user_facing_summary
            
        except Exception as e:
            # Comprehensive error handling
            self.logger.error(
                f"Error during initial message analysis: {str(e)}", 
                exc_info=True
            )
            
            # Return safe default response
            return self._get_safe_default_response()
    
    def _format_critical_complaint_criteria(
        self, 
        criteria: Optional[List[str]]
    ) -> Optional[str]:
        """
        Format critical complaint criteria into a suitable string for prompt injection.
        
        Args:
            criteria: List of critical complaint criteria strings
            
        Returns:
            Formatted string for prompt injection, or None if no criteria
        """
        if not criteria:
            return None
        
        formatted = "Key Critical Complaint Identification Criteria:\n"
        for criterion in criteria:
            formatted += f"- {criterion}\n"
        
        return formatted.strip()
    
    async def _generate_system_prompt(
        self,
        user_input_text: str,
        user_first_name: str,
        institution_name: str,
        formatted_criteria: Optional[str],
        current_date_time: Optional[str]
    ) -> str:
        """
        Generate the system prompt using PromptBuilder's dedicated method.
        
        Args:
            user_input_text: User's input text
            user_first_name: User's first name
            institution_name: Institution name
            formatted_criteria: Formatted critical complaint criteria
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
                critical_complaint_criteria=formatted_criteria,
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
        Parse the LLM's JSON response string.
        
        Args:
            raw_response: Raw string response from LLM
            
        Returns:
            Parsed JSON dictionary
            
        Raises:
            json.JSONDecodeError: If JSON parsing fails
        """
        try:
            parsed = json.loads(raw_response)
            self.logger.debug("LLM response parsed successfully")
            return parsed
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM JSON response: {str(e)}")
            self.logger.debug(f"Raw response: {raw_response[:500]}...")
            raise
    
    def _validate_and_extract_data(
        self, 
        parsed_response: Dict[str, Any]
    ) -> Tuple[str, str, Optional[str]]:
        """
        Validate the parsed LLM response and extract required data.
        
        Args:
            parsed_response: Parsed JSON response from LLM
            
        Returns:
            Tuple of (signal, llm_response_text, user_facing_summary)
        """
        # Extract basic fields
        signal = parsed_response.get("signal")
        llm_response_text = parsed_response.get("response_text")
        user_facing_summary = parsed_response.get("user_facing_summary")
        
        # Validate signal
        if not isinstance(signal, str) or not signal:
            self.logger.warning("Invalid or missing signal in LLM response")
            signal = "CLARIFICATION_NEEDED"
        
        # Check if signal is valid
        if signal not in self.VALID_SIGNALS:
            self.logger.warning(f"Unknown signal received: {signal}")
            signal = "CLARIFICATION_NEEDED"
        
        # Validate response_text
        if not isinstance(llm_response_text, str) or not llm_response_text:
            self.logger.warning("Invalid or missing response_text in LLM response")
            llm_response_text = "I'm having trouble processing your message. Could you please try rephrasing?"
        
        # Validate user_facing_summary for complaint signals
        if signal in self.COMPLAINT_SIGNALS:
            if not isinstance(user_facing_summary, str) or not user_facing_summary:
                self.logger.warning(
                    f"Missing user_facing_summary for complaint signal: {signal}"
                )
                # Allow user_facing_summary to be None, let caller handle it
                user_facing_summary = None
        else:
            # For non-complaint signals, user_facing_summary should be None
            user_facing_summary = None
        
        self.logger.debug(f"Data validation completed for signal: {signal}")
        return signal, llm_response_text, user_facing_summary
    
    def _get_safe_default_response(self) -> Tuple[str, str, Optional[str]]:
        """
        Get a safe default response for error scenarios.
        
        Returns:
            Safe default tuple (signal, response_text, user_facing_summary)
        """
        return (
            "CLARIFICATION_NEEDED",
            "I'm encountering a technical issue. Could you please try rephrasing or try again shortly?",
            None
        )
    
    async def cleanup(self):
        """
        Clean up resources (optional method for future extensibility).
        
        Currently a no-op as dependencies handle their own cleanup.
        """
        self.logger.debug("LLMOrchestrator cleanup called")
        # No cleanup needed for this class as dependencies handle their own cleanup
        pass