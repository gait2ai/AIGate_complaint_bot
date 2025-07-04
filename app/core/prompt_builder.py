"""
AI Gate for Artificial Intelligence Applications
Institution Prompt Builder Module

This module handles the construction of comprehensive system prompts by combining
institution-specific templates, institution data, and task-specific instructions for
the Institution Telegram complaint bot. It manages prompt optimization for different
complaint handling tasks using a multi-prompt architecture with specialized templates.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class PromptBuilder:
    """
    Handles construction and optimization of system prompts for Institution complaint bot tasks.
    
    This class combines institution-specific data sources to create contextually appropriate
    system prompts that guide AI model responses for complaint handling according to
    institutional protocols and requirements. Now supports multi-prompt architecture with
    specialized templates for different analysis stages.
    """

    def __init__(self, config_dir: Path, institution_config, prompts_config, analysis_settings):
        """
        Initialize the PromptBuilder with Institution configuration and templates.
        
        Args:
            config_dir: Directory containing configuration files (app/config/)
            institution_config: InstitutionModel instance with institution-specific configuration
            prompts_config: PromptsModel instance with template configuration for prompts
            analysis_settings: AnalysisSettingsModel instance with analysis configuration
        """
        self.config_dir = Path(config_dir)
        self.institution_config = institution_config
        self.prompts_config = prompts_config
        self.analysis_settings = analysis_settings
        
        # Default configuration for Institution bot
        self.default_config = {
            'max_context_length': 6000,  # Increased for complaint handling context
            'context_truncation_strategy': 'smart',
            'prompt_optimization': True,
            'max_prompt_length': 12000,  # Increased for detailed Institution prompts
            'template_variables': {}
        }
        
        # Language mapping for Institution responses (Arabic-focused)
        self.language_instructions = {
            'ar': "يرجى الرد باللغة العربية بطريقة مهنية ومتعاطفة مناسبة لمسؤول الشكاوى.",
            'en': "Please respond in English in a professional and empathetic manner appropriate for a complaints officer.",
            'es': "Por favor responde en español de manera profesional y empática apropiada para un oficial de quejas.",
            'fr': "Veuillez répondre en français de manière professionnelle et empathique appropriée pour un agent des plaintes.",
            'de': "Bitte antworten Sie auf Deutsch in einer professionellen und einfühlsamen Art, die für einen Beschwerdebeamten angemessen ist.",
            'it': "Per favore rispondi in italiano in modo professionale ed empatico appropriato per un ufficiale reclami.",
            'pt': "Por favor responda em português de forma profissional e empática apropriada para um oficial de reclamações.",
            'zh': "请用中文以适合投诉官员的专业和同理心方式回答。",
            'ja': "苦情処理担当者にふさわしい専門的で共感的な方法で日本語でお答えください。",
            'ko': "불만 처리 담당자에게 적합한 전문적이고 공감적인 방식으로 한국어로 답변해 주세요.",
            'ru': "Пожалуйста, отвечайте на русском языке профессионально и с пониманием, подходящим для сотрудника по жалобам.",
            'hi': "कृपया शिकायत अधिकारी के लिए उपयुक्त पेशेवर और सहानुभूतिपूर्ण तरीके से हिंदी में उत्तर दें।"
        }
        
        # Override with configured language instructions if available
        if hasattr(self.prompts_config, 'language_instructions') and self.prompts_config.language_instructions:
            self.language_instructions.update(self.prompts_config.language_instructions)
        
        # Load prompt templates for multi-prompt architecture
        self.initial_analysis_template = self._load_template('initial_analysis_prompt.txt')
        self.final_analysis_template = self._load_template('final_analysis_prompt.txt')
        self.input_validation_template = self._load_template('input_validation_prompt.txt')
        
        # Default output format instructions for common tasks
        self.default_output_formats = {
            'classification': 'Provide the response in JSON format with keys: "category", "subcategory", "sensitivity_level", "confidence_score".',
            'summarization': 'Provide a concise summary in 2-3 sentences highlighting the main complaint and key details.',
            'critical_identification': 'Respond with "CRITICAL" or "NON_CRITICAL" followed by a brief justification.',
            'response_generation': 'Provide a professional response that acknowledges the complaint and indicates next steps.',
            'default': 'Provide a clear and structured response addressing the specific task requirements.'
        }
        
        # Override with configured output formats if available
        if hasattr(self.prompts_config, 'default_output_formats') and self.prompts_config.default_output_formats:
            self.default_output_formats.update(self.prompts_config.default_output_formats)
        
        logger.info("Institution PromptBuilder initialized successfully with multi-prompt architecture")

    def _load_template(self, template_filename: str) -> str:
        """
        Load a prompt template from the specified filename.
        
        Args:
            template_filename: Name of the template file to load
            
        Returns:
            str: Template content or default template if loading fails
        """
        template_file = self.config_dir / template_filename
        
        try:
            if not template_file.exists():
                logger.error(f"Template file not found: '{template_filename}' (full path: {template_file})")
                return self._get_default_template(template_filename)
            
            if not template_file.is_file():
                logger.error(f"Template path is not a file: '{template_filename}' (full path: {template_file})")
                return self._get_default_template(template_filename)
            
            # Read the template file
            with open(template_file, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # Check if the file has meaningful content
            if not template_content or not template_content.strip():
                logger.error(f"Template file is empty: '{template_filename}'")
                return self._get_default_template(template_filename)
            
            # Successfully loaded template
            template_content = template_content.strip()
            logger.info(f"Successfully loaded template: '{template_filename}'")
            return template_content
            
        except PermissionError:
            logger.error(f"Permission denied reading template file: '{template_filename}'")
            return self._get_default_template(template_filename)
        
        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error reading template file: '{template_filename}': {e}")
            return self._get_default_template(template_filename)
        
        except OSError as e:
            logger.error(f"OS error reading template file: '{template_filename}': {e}")
            return self._get_default_template(template_filename)
        
        except Exception as e:
            logger.error(f"Unexpected error reading template file: '{template_filename}': {e}")
            return self._get_default_template(template_filename)

    def _get_default_template(self, template_filename: str) -> str:
        """
        Get default template content based on filename.
        
        Args:
            template_filename: Name of the template file
            
        Returns:
            str: Default template content
        """
        if template_filename == 'initial_analysis_prompt.txt':
            return """### Initial Analysis Template
You are an AI assistant for {{institution_name}} complaint analysis.

User Message: {{user_message}}

Please analyze this message in {{language}}.

Provide initial analysis of the complaint."""
        
        elif template_filename == 'final_analysis_prompt.txt':
            return """### Final Analysis Template
Complaint Text: {{complaint_text}}

Available Categories: {{allowed_categories}}
Available Sensitivity Levels: {{allowed_sensitivities}}

Please provide final analysis with appropriate categorization."""
        
        elif template_filename == 'input_validation_prompt.txt':
            return """### Input Validation Template
Question Asked: {{question_asked}}
User Answer: {{user_answer}}

Please validate if the user's answer appropriately addresses the question."""
        
        else:
            return f"""### Default Template for {template_filename}
This is a default template for {template_filename}.
Please replace with actual template content."""

    async def generate_initial_interaction_prompt(
        self,
        user_input_text: str,
        user_first_name: str,
        institution_name: str,
        critical_complaint_criteria_text: Optional[str] = None,
        current_date_time: Optional[str] = None
    ) -> str:
        """
        Generate a specialized system prompt for initial user message analysis.
        
        This method creates a comprehensive system prompt specifically tailored for the "initial user message 
        analysis" task by populating the initial_analysis_prompt.txt template with contextual information.
        
        Args:
            user_input_text: The user's initial message/complaint text to be analyzed
            user_first_name: The first name of the user for personalized interaction
            institution_name: Name of the institution
            critical_complaint_criteria_text: Optional text containing critical complaint identification criteria
            current_date_time: Optional timestamp information for the interaction
        
        Returns:
            str: Complete system prompt ready for LLM consumption, formatted for initial analysis
        
        Raises:
            Exception: If template formatting fails due to missing placeholders or other formatting errors
        """
        try:
            logger.debug(f"Generating initial interaction prompt for user: {user_first_name}")
            
            # Get institution name from configuration
            institution_name = getattr(self.institution_config, 'name', 'Institution')
            
            # Determine language based on user input or default to Arabic
            language = self._detect_language(user_input_text)
            
            # Prepare template variables dictionary for formatting
            template_variables = {
                'user_message': user_input_text,
                'language': language,
                'institution_name': institution_name
            }
            
            # Log template variables for debugging (excluding sensitive user input)
            logger.debug(f"Template variables prepared: institution_name={institution_name}, "
                        f"language={language}, user_input_length={len(user_input_text)}")
            
            # Format the initial analysis template with prepared variables
            formatted_prompt = self.initial_analysis_template.format(**template_variables)
            
            # Validate the formatted prompt
            if not formatted_prompt or not formatted_prompt.strip():
                raise ValueError("Formatted prompt is empty after template processing")
            
            # Apply length truncation if needed to prevent exceeding model limits
            formatted_prompt = self._truncate_if_needed(formatted_prompt)
            
            logger.info(f"Successfully generated initial interaction prompt for user: {user_first_name} "
                       f"(prompt length: {len(formatted_prompt)} characters)")
            
            return formatted_prompt
            
        except KeyError as e:
            error_msg = f"Missing template placeholder in initial analysis template: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e
        
        except Exception as e:
            error_msg = f"Error generating initial interaction prompt for user {user_first_name}: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e

    def generate_final_analysis_prompt(self, complaint_text: str) -> str:
        """
        Generate a specialized system prompt for final complaint analysis.
        
        This method creates a comprehensive system prompt for final analysis by populating
        the final_analysis_prompt.txt template with complaint text and dynamic configuration
        data including allowed categories and sensitivity levels.
        
        Args:
            complaint_text: The complaint text to be analyzed
            
        Returns:
            str: Complete system prompt ready for final analysis
            
        Raises:
            Exception: If template formatting fails or configuration data is missing
        """
        try:
            logger.debug("Generating final analysis prompt")
            
            # Retrieve complaint categories from analysis settings
            complaint_categories = getattr(self.analysis_settings, 'complaint_categories', [])
            if not complaint_categories:
                logger.warning("No complaint categories found in analysis settings")
                allowed_categories = "No categories configured"
            else:
                # Format as comma-separated, double-quoted strings
                allowed_categories = ', '.join([f'"{category}"' for category in complaint_categories])
            
            # Retrieve sensitivity levels from analysis settings
            sensitivity_levels = getattr(self.analysis_settings, 'sensitivity_levels', [])
            if not sensitivity_levels:
                logger.warning("No sensitivity levels found in analysis settings")
                allowed_sensitivities = "No sensitivity levels configured"
            else:
                # Format as comma-separated, double-quoted strings
                allowed_sensitivities = ', '.join([f'"{level}"' for level in sensitivity_levels])
            
            # Prepare template variables dictionary for formatting
            template_variables = {
                'complaint_text': complaint_text,
                'allowed_categories': allowed_categories,
                'allowed_sensitivities': allowed_sensitivities
            }
            
            # Log template variables for debugging (excluding sensitive complaint text)
            logger.debug(f"Template variables prepared: allowed_categories={allowed_categories}, "
                        f"allowed_sensitivities={allowed_sensitivities}, "
                        f"complaint_text_length={len(complaint_text)}")
            
            # Format the final analysis template with prepared variables
            formatted_prompt = self.final_analysis_template.format(**template_variables)
            
            # Validate the formatted prompt
            if not formatted_prompt or not formatted_prompt.strip():
                raise ValueError("Formatted prompt is empty after template processing")
            
            # Apply length truncation if needed to prevent exceeding model limits
            formatted_prompt = self._truncate_if_needed(formatted_prompt)
            
            logger.info(f"Successfully generated final analysis prompt "
                       f"(prompt length: {len(formatted_prompt)} characters)")
            
            return formatted_prompt
            
        except KeyError as e:
            error_msg = f"Missing template placeholder in final analysis template: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e
        
        except Exception as e:
            error_msg = f"Error generating final analysis prompt: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e

    def generate_input_validation_prompt(self, question_asked: str, user_answer: str) -> str:
        """
        Generate a specialized system prompt for input validation.
        
        This method creates a system prompt for validating user input by populating
        the input_validation_prompt.txt template with the question and user's answer.
        
        Args:
            question_asked: The question that was asked to the user
            user_answer: The user's answer to the question
            
        Returns:
            str: Complete system prompt ready for input validation
            
        Raises:
            Exception: If template formatting fails
        """
        try:
            logger.debug("Generating input validation prompt")
            
            # Prepare template variables dictionary for formatting
            template_variables = {
                'question_asked': question_asked,
                'user_answer': user_answer
            }
            
            # Log template variables for debugging
            logger.debug(f"Template variables prepared: question_length={len(question_asked)}, "
                        f"answer_length={len(user_answer)}")
            
            # Format the input validation template with prepared variables
            formatted_prompt = self.input_validation_template.format(**template_variables)
            
            # Validate the formatted prompt
            if not formatted_prompt or not formatted_prompt.strip():
                raise ValueError("Formatted prompt is empty after template processing")
            
            # Apply length truncation if needed to prevent exceeding model limits
            formatted_prompt = self._truncate_if_needed(formatted_prompt)
            
            logger.info(f"Successfully generated input validation prompt "
                       f"(prompt length: {len(formatted_prompt)} characters)")
            
            return formatted_prompt
            
        except KeyError as e:
            error_msg = f"Missing template placeholder in input validation template: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e
        
        except Exception as e:
            error_msg = f"Error generating input validation prompt: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e

    def _detect_language(self, text: str) -> str:
        """
        Detect the language of the input text.
        
        Args:
            text: Text to analyze for language detection
            
        Returns:
            str: Language code (defaults to 'ar' for Arabic)
        """
        # Simple language detection based on character patterns
        # This is a basic implementation - could be enhanced with proper language detection
        if not text:
            return 'ar'  # Default to Arabic
        
        # Check for Arabic characters
        arabic_chars = sum(1 for char in text if '\u0600' <= char <= '\u06FF')
        
        # Check for English characters
        english_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)
        
        # Simple heuristic: if more than 30% are Arabic characters, assume Arabic
        if arabic_chars > len(text) * 0.3:
            return 'ar'
        elif english_chars > len(text) * 0.3:
            return 'en'
        else:
            return 'ar'  # Default to Arabic

    def _truncate_if_needed(self, prompt: str) -> str:
        """
        Truncate prompt if it exceeds maximum length limits, preserving critical sections.
        
        Args:
            prompt: The prompt to check and potentially truncate
            
        Returns:
            str: Truncated prompt if necessary
        """
        # Get max_prompt_length from Pydantic model or use default
        max_length = getattr(self.prompts_config, 'max_prompt_length', self.default_config['max_prompt_length'])
        
        if len(prompt) <= max_length:
            return prompt
        
        logger.warning(f"Prompt length ({len(prompt)}) exceeds maximum ({max_length}), truncating...")
        
        # Simple truncation with buffer for truncation message
        truncated_prompt = prompt[:max_length - 100] + "\n...[Prompt truncated due to length limits]"
        
        return truncated_prompt

    def is_healthy(self) -> bool:
        """
        Check if the PromptBuilder is healthy and functioning properly.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            # Check if we have valid templates
            if not self.initial_analysis_template:
                logger.error("Initial analysis template is not loaded")
                return False
            
            if not self.final_analysis_template:
                logger.error("Final analysis template is not loaded")
                return False
            
            if not self.input_validation_template:
                logger.error("Input validation template is not loaded")
                return False
            
            # Check if required configurations are available
            if not self.institution_config:
                logger.error("Institution configuration is not available")
                return False
            
            if not self.analysis_settings:
                logger.error("Analysis settings are not available")
                return False
            
            # Test template formatting with sample data
            try:
                # Test initial analysis template
                test_initial = self.initial_analysis_template.format(
                    user_message="Test message",
                    language="ar",
                    institution_name="Test Institution"
                )
                
                # Test final analysis template
                test_final = self.final_analysis_template.format(
                    complaint_text="Test complaint",
                    allowed_categories='"Test Category"',
                    allowed_sensitivities='"Test Sensitivity"'
                )
                
                # Test input validation template
                test_validation = self.input_validation_template.format(
                    question_asked="Test question",
                    user_answer="Test answer"
                )
                
                return all([len(test_initial) > 0, len(test_final) > 0, len(test_validation) > 0])
                
            except Exception as e:
                logger.error(f"Template formatting test failed: {e}")
                return False
            
        except Exception as e:
            logger.error(f"PromptBuilder health check failed: {e}")
            return False

    async def cleanup(self):
        """Clean up resources and connections."""
        logger.info("PromptBuilder cleanup completed")
        pass

    async def get_template_variables(self) -> Dict[str, Any]:
        """
        Get available template variables for prompt customization.
        
        Returns:
            Dict[str, Any]: Available template variables
        """
        return {
            'institution_name': getattr(self.institution_config, 'name', 'Institution'),
            'institution_website': getattr(self.institution_config, 'website', ''),
            'institution_description': getattr(self.institution_config, 'description', ''),
            'supported_languages': list(self.language_instructions.keys()),
            'complaint_categories': getattr(self.analysis_settings, 'complaint_categories', []),
            'sensitivity_levels': getattr(self.analysis_settings, 'sensitivity_levels', []),
            'default_language': 'ar',
            'available_output_formats': list(self.default_output_formats.keys()),
            'templates': {
                'initial_analysis': 'initial_analysis_prompt.txt',
                'final_analysis': 'final_analysis_prompt.txt',
                'input_validation': 'input_validation_prompt.txt'
            }
        }

    async def validate_template(self, template_name: str, template_content: str) -> Dict[str, Any]:
        """
        Validate a prompt template for required placeholders and format.
        
        Args:
            template_name: Name of the template being validated
            template_content: The template content to validate
            
        Returns:
            Dict[str, Any]: Validation results
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'required_placeholders': [],
            'found_placeholders': []
        }
        
        # Define required placeholders for each template
        required_placeholders_map = {
            'initial_analysis_prompt.txt': ['user_message', 'language', 'institution_name'],
            'final_analysis_prompt.txt': ['complaint_text', 'allowed_categories', 'allowed_sensitivities'],
            'input_validation_prompt.txt': ['question_asked', 'user_answer']
        }
        
        required_placeholders = required_placeholders_map.get(template_name, [])
        validation_result['required_placeholders'] = required_placeholders
        
        try:
            # Check for required placeholders
            for placeholder in required_placeholders:
                placeholder_pattern = f"{{{placeholder}}}"
                if placeholder_pattern in template_content:
                    validation_result['found_placeholders'].append(placeholder)
                else:
                    validation_result['errors'].append(f"Missing required placeholder: {placeholder_pattern}")
                    validation_result['is_valid'] = False
            
            # Check template length
            if len(template_content) > 3000:
                validation_result['warnings'].append("Template is quite long, consider condensing for better performance")
            
        except Exception as e:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f"Template validation error: {str(e)}")
        
        return validation_result