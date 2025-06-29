"""
LLM Orchestrator Module

This module contains the LLMOrchestrator class responsible for managing 
the specialized interaction flow with the Large Language Model (LLM) for 
the initial analysis of user messages within the Institution Complaint 
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
        "FOLLOW_UP_QUESTION",
        "SUGGESTION_RECEIVED"
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
            # Step 1: Generate system prompt using the universal template approach
            system_prompt = await self._generate_system_prompt(
                user_input_text=user_input_text,
                user_first_name=user_first_name,
                institution_name=institution_name,
                critical_complaint_criteria=critical_complaint_criteria,
                current_date_time=current_date_time
            )
            
            # Step 2: Send request to LLM via AIHandler
            llm_raw_response = await self._call_llm(system_prompt)
            
            # Step 3: Parse LLM's JSON response
            parsed_response = self._parse_llm_response(llm_raw_response)
            
            # Step 4: Validate parsed data
            signal, llm_response_text, user_facing_summary = self._validate_and_extract_data(
                parsed_response
            )
            
            # Step 5: Log successful outcome
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
    
    def _build_task_specific_instruction(
        self,
        user_first_name: str,
        institution_name: str,
        critical_complaint_criteria: Optional[List[str]] = None
    ) -> str:
        """
        Build the detailed task-specific instruction for initial message analysis.
        
        Args:
            user_first_name: User's first name
            institution_name: Institution name
            critical_complaint_criteria: Optional list of critical complaint criteria
            
        Returns:
            Detailed task instruction text
        """
        # Format critical complaint criteria if provided
        criteria_text = ""
        if critical_complaint_criteria:
            criteria_text = "\n\n**Critical Complaint Identification Criteria:**\n"
            for criterion in critical_complaint_criteria:
                criteria_text += f"- {criterion}\n"
        
        instruction = f"""
### Task: Initial Message Analysis for {institution_name}

You are an AI-Powered Initial Interaction Analyst for **{institution_name}**. Analyze the user's initial message from Telegram, understand their intent, generate contextually appropriate responses, and return specific action signals for bot processing.

### Persona and Behavior Protocol
- **Empathy & Respect:** Maintain professional empathy, especially for distressing situations
- **Language Matching:** Respond in user's language. Default to institution's primary language if undetermined
- **Personalization:** Use {user_first_name} in greetings where appropriate
- **No Impersonation:** You are an AI assistant, not human staff

### Operational Boundaries
- **Strict Role Focus:** Only analyze initial messages for defined scenarios below
- **Internal Data Only:** Base analysis solely on the provided user input and context
- **No External Advice:** Do not provide legal, medical, financial, or personal advice
- **Redirect Off-Topic:** Guide users back to institutional matters
- **No Internal Process Disclosure**

### Analysis Scenarios

#### Scenario A: Greeting Detection
**Detect:** Simple greetings (Arabic: "السلام عليكم", "أهلاً", "مرحبا", "صباح الخير" | English: "Hello", "Hi", "Good morning")
**Signal:** GREETING_START
**Response:** Warm welcome with offer to help

#### Scenario B: Off-Topic/Irrelevant
**Detect:** Messages unrelated to {institution_name} services, complaints, suggestions, or feedback
**Signal:** OFF_TOPIC_REPLY
**Response:** Polite redirect to institutional matters

#### Scenario C: Complaint Submission
**Detect:** Expressions of dissatisfaction, problem reports, negative experiences, resolution requests, service failure feedback
**Assessment:** Evaluate against critical complaint criteria for severity classification
**Signals:** COMPLAINT_NORMAL or COMPLAINT_CRITICAL
**Response:** Professional acknowledgment with summary

#### Scenario D: Suggestion/Feedback
**Detect:** Constructive suggestions, positive feedback, recommendations, improvement ideas
**Signal:** SUGGESTION_RECEIVED
**Response:** Grateful acknowledgment

#### Scenario E: Unclear/Ambiguous
**Detect:** Vague, incomplete, or ambiguous messages where intent cannot be determined
**Signal:** CLARIFICATION_NEEDED
**Response:** Polite request for clarification

{criteria_text}

### Response Guidelines
- Use literal placeholders: `{{user_first_name}}`, `{{institution_name}}` (bot handles substitution)
- Match user's language when possible
- Professional, empathetic tone
- Complaint summaries: English, concise, professional, suitable for internal logging
- User-facing summaries: User's language, natural, empathetic
"""
        
        return instruction.strip()
    
    def _build_output_format_instruction(self) -> str:
        """
        Build the output format instruction for the JSON response structure.
        
        Returns:
            Detailed output format instruction
        """
        return """
### Required JSON Output Structure

Your response must be a valid JSON object with the following structure:

```json
{
  "signal": "SIGNAL_NAME",
  "response_text": "Generated response text",
  "user_facing_summary": "Summary text (required only for complaints)"
}
```

### Field Specifications

**"signal"** (required): Must be one of:
- `GREETING_START` - Simple greeting detected
- `OFF_TOPIC_REPLY` - Message unrelated to institution
- `COMPLAINT_NORMAL` - Standard complaint submission
- `COMPLAINT_CRITICAL` - Critical/urgent complaint requiring immediate attention
- `SUGGESTION_RECEIVED` - Constructive feedback or suggestion
- `CLARIFICATION_NEEDED` - Unclear or ambiguous message

**"response_text"** (required): 
- For greetings, suggestions, off-topic: Direct response in user's language
- For complaints: English summary for internal logging (professional, concise)
- For clarification: Polite request for more details

**"user_facing_summary"** (conditional):
- Required ONLY for COMPLAINT_NORMAL and COMPLAINT_CRITICAL signals
- Must be in user's language
- Natural, empathetic acknowledgment of their concern
- Should confirm understanding of their issue

### Example Outputs

**Greeting Example:**
```json
{
  "signal": "GREETING_START",
  "response_text": "وعليكم السلام {user_first_name}! كيف يمكنني مساعدتك اليوم؟"
}
```

**Normal Complaint Example:**
```json
{
  "signal": "COMPLAINT_NORMAL",
  "response_text": "User reports delays in service delivery and requests assistance with expediting their application process.",
  "user_facing_summary": "أتفهم أن لديك مشكلة بخصوص تأخير في تقديم الخدمة. هل هذا ما تقصده؟"
}
```

**Critical Complaint Example:**
```json
{
  "signal": "COMPLAINT_CRITICAL",
  "response_text": "User reports urgent safety hazard at the main facility involving broken equipment that poses immediate risk to visitors.",
  "user_facing_summary": "أتفهم أنك تبلغ عن خطر أمني عاجل في المرفق. هل هذا صحيح؟"
}
```

**CRITICAL: Your entire response must be a raw JSON object only. No additional text, explanations, or formatting. Your response MUST start with `{` and end with `}`.**
"""
    
    def _build_context_data(
        self,
        user_input_text: str,
        user_first_name: str,
        current_date_time: Optional[str] = None
    ) -> str:
        """
        Build the context data string for the prompt.
        
        Args:
            user_input_text: User's input message
            user_first_name: User's first name
            current_date_time: Optional current date/time
            
        Returns:
            Formatted context data string
        """
        context = f"""
### Analysis Context

**User Input Message:** {user_input_text}

**User Details:**
- First Name: {user_first_name}
- Communication Channel: Telegram

**Processing Information:**
- Analysis Type: Initial Message Analysis
- Expected Output: JSON with signal classification and response
"""
        
        if current_date_time:
            context += f"\n- Current Date/Time: {current_date_time}"
        
        return context.strip()
    
    async def _generate_system_prompt(
        self,
        user_input_text: str,
        user_first_name: str,
        institution_name: str,
        critical_complaint_criteria: Optional[List[str]] = None,
        current_date_time: Optional[str] = None
    ) -> str:
        """
        Generate the system prompt using the universal template approach.
        
        Args:
            user_input_text: User's input text
            user_first_name: User's first name
            institution_name: Institution name
            critical_complaint_criteria: Critical complaint criteria
            current_date_time: Current date/time string
            
        Returns:
            Generated system prompt string
            
        Raises:
            Exception: If prompt generation fails
        """
        try:
            # Build the dynamic content components
            task_instruction = self._build_task_specific_instruction(
                user_first_name=user_first_name,
                institution_name=institution_name,
                critical_complaint_criteria=critical_complaint_criteria
            )
            
            output_format = self._build_output_format_instruction()
            
            context_data = self._build_context_data(
                user_input_text=user_input_text,
                user_first_name=user_first_name,
                current_date_time=current_date_time
            )
            
            # Use the generic prompt builder function
            system_prompt = await self.prompt_builder.build_institution_task_prompt(
                task_specific_instruction=task_instruction,
                context_data=context_data,
                output_format_instruction=output_format,
                user_language_code='ar',
                additional_template_vars=
                {'user_first_name': user_first_name}
                
            )
            
            self.logger.debug("System prompt generated successfully using universal template")
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