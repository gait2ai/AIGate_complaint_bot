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
import re

logger = logging.getLogger(__name__)


class PromptBuilder:
    """
    Handles construction and optimization of system prompts for Institution complaint bot tasks.
    
    This class combines institution-specific data sources to create contextually appropriate
    system prompts that guide AI model responses for complaint handling according to
    institutional protocols and requirements. Now supports multi-prompt architecture with
    specialized templates for different analysis stages.
    """

    def __init__(self, config_dir: Path, institution_config, prompts_config, analysis_settings, critical_complaint_config):
        """
        Initialize the PromptBuilder with Institution configuration and templates.
        
        Args:
            config_dir: Directory containing configuration files (app/config/)
            institution_config: InstitutionModel instance with institution-specific configuration
            prompts_config: PromptsModel instance with template configuration for prompts
            analysis_settings: AnalysisSettingsModel instance with analysis configuration
            critical_complaint_config: CriticalComplaintModel instance with critical complaint configuration
        """
        self.config_dir = Path(config_dir)
        self.institution_config = institution_config
        self.prompts_config = prompts_config
        self.analysis_settings = analysis_settings
        self.critical_complaint_config = critical_complaint_config
        self.logger = logger
        
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
        
        # Validate templates after loading
        self._validate_all_templates()
        
        logger.info("Institution PromptBuilder initialized successfully with multi-prompt architecture")

    def _validate_placeholder_replacement(self, template: str, variables: dict) -> bool:
        """Validate that all placeholders in template can be replaced."""
        try:
            # Find all placeholder patterns, including incomplete ones
            placeholder_pattern = r'\{([^}]*)\}'
            matches = re.findall(placeholder_pattern, template)
            
            valid_placeholders = []
            malformed_placeholders = []
            
            for match in matches:
                # Skip empty matches
                if not match:
                    continue
                    
                # Check for valid variable names (letters, numbers, underscore, no spaces)
                if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', match):
                    valid_placeholders.append(match)
                else:
                    # This is likely JSON or other content, not a template variable
                    malformed_placeholders.append(match)
            
            # Only log actual malformed placeholders that look like they should be variables
            actual_malformed = [p for p in malformed_placeholders 
                              if not any(char in p for char in ['"', ':', ',', '\n', ' '])]
            
            if actual_malformed:
                self.logger.error(f"Malformed placeholders found: {actual_malformed}")
                return False
            
            # Check for missing variables
            missing_vars = [p for p in valid_placeholders if p not in variables]
            if missing_vars:
                self.logger.error(f"Missing template variables: {missing_vars}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating placeholders: {e}")
            return False

    def _preprocess_template(self, template: str) -> str:
        """Preprocess template to fix common formatting issues."""
        try:
            # First, protect JSON-like structures by temporarily replacing them
            json_blocks = []
            
            # Find and protect JSON blocks (content between triple braces)
            def protect_json_block(match):
                json_content = match.group(0)
                placeholder = f"__JSON_BLOCK_{len(json_blocks)}__"
                json_blocks.append(json_content)
                return placeholder
            
            # Protect triple brace blocks that contain JSON
            template = re.sub(r'\{\{\{[^}]*\}\}\}', protect_json_block, template, flags=re.DOTALL)
            
            # Fix broken placeholders that are missing closing braces
            # Look for { followed by a valid variable name but no closing }
            template = re.sub(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\b(?!\})', r'{\1}', template)
            
            # Restore JSON blocks
            for i, json_block in enumerate(json_blocks):
                template = template.replace(f"__JSON_BLOCK_{i}__", json_block)
            
            return template
            
        except Exception as e:
            self.logger.error(f"Error preprocessing template: {e}")
            return template  # Return original if preprocessing fails

    def _safe_format_template(self, template: str, variables: dict) -> str:
        """Safely format template with proper error handling."""
        try:
            # Pre-process template to fix common issues
            processed_template = self._preprocess_template(template)
            
            # Validate placeholders
            if not self._validate_placeholder_replacement(processed_template, variables):
                # If validation fails, try to continue with a fallback approach
                self.logger.warning("Template validation failed, attempting fallback formatting")
                
                # Create a safe copy of variables with string conversion
                safe_variables = {}
                for key, value in variables.items():
                    if isinstance(value, str):
                        safe_variables[key] = value
                    else:
                        safe_variables[key] = str(value) if value is not None else ""
                
                # Try formatting with safe variables
                try:
                    formatted = processed_template.format(**safe_variables)
                except KeyError as ke:
                    # If we still have missing keys, provide defaults
                    self.logger.warning(f"Missing variable {ke}, using default")
                    safe_variables[str(ke).strip("'")] = f"[{ke}]"
                    formatted = processed_template.format(**safe_variables)
            else:
                # Normal formatting path
                formatted = processed_template.format(**variables)
            
            # Final validation - check for any remaining unformatted placeholders
            remaining_placeholders = re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', formatted)
            if remaining_placeholders:
                self.logger.warning(f"Unformatted placeholders remaining: {remaining_placeholders}")
                # Replace remaining placeholders with safe defaults
                for placeholder in remaining_placeholders:
                    formatted = formatted.replace(f"{{{placeholder}}}", f"[{placeholder}]")
            
            return formatted
            
        except Exception as e:
            error_msg = f"Template formatting error: {e}"
            self.logger.error(error_msg)
            
            # Return a minimal safe template as last resort
            return f"""
Template formatting failed: {error_msg}
User Input: {variables.get('user_message', 'N/A')}
Institution: {variables.get('institution_name', 'N/A')}
Please review template configuration.
"""

    def _get_allowed_categories_text(self) -> str:
        """Get allowed categories text with fallback."""
        complaint_categories = getattr(self.analysis_settings, 'complaint_categories', [])
        if not complaint_categories:
            return '"General"'  # Fallback
        return ', '.join([f'"{cat.name}"' for cat in complaint_categories])

    def _get_category_guidance_text(self) -> str:
        """Get category guidance text with fallback."""
        complaint_categories = getattr(self.analysis_settings, 'complaint_categories', [])
        if not complaint_categories:
            return '*   "General": General complaints and inquiries'  # Fallback
        
        guidance_lines = [f'*   "{cat.name}": {cat.description}' for cat in complaint_categories]
        return '\n'.join(guidance_lines)
        
    def _get_allowed_sectors_text(self) -> str:
        """Get allowed sectors text with fallback."""
        sectors = getattr(self.analysis_settings, 'sectors', [])
        if not sectors:
            return '"General Services"'  # Fallback
        return ', '.join([f'"{sec.name}"' for sec in sectors])

    def _get_sector_guidance_text(self) -> str:
        """Get sector guidance text with fallback."""
        sectors = getattr(self.analysis_settings, 'sectors', [])
        if not sectors:
            return '*   "General Services": For complaints that do not fit into a specific sector.'  # Fallback
        
        guidance_lines = [f'*   "{sec.name}": {sec.description}' for sec in sectors]
        return '\n'.join(guidance_lines)

    def _get_allowed_sensitivities_text(self) -> str:
        """Get allowed sensitivities text with fallback."""
        sensitivity_levels = getattr(self.analysis_settings, 'sensitivity_levels', [])
        if not sensitivity_levels:
            return '"Low", "Medium", "High"'  # Default levels
        return ', '.join([f'"{level}"' for level in sensitivity_levels])

    def _get_critical_keywords_text(self) -> str:
        """Get critical keywords text with fallback."""
        critical_keywords = getattr(self.critical_complaint_config, 'keywords', [])
        if not critical_keywords:
            return '"urgent", "emergency"'  # Default keywords
        return ', '.join([f'"{keyword}"' for keyword in critical_keywords])

    def _get_fallback_prompt(self, variables: dict) -> str:
        """Generate a fallback prompt when template processing fails."""
        return f"""
You are an AI assistant for {variables.get('institution_name', 'Institution')} complaint analysis.

User: {variables.get('user_first_name', 'User')}
Message: {variables.get('user_message', 'No message provided')}

Please analyze this message and respond with a JSON object containing:
- "signal": one of "COMPLAINT_START", "SUGGESTION_START", "GENERAL_INQUIRY", or "IRRELEVANT"
- "response_text": appropriate response in Arabic

Current Date/Time: {variables.get('current_date_time', datetime.now().isoformat())}

Please respond in Arabic in a professional and empathetic manner.
"""

    def _get_fallback_validation_prompt(self, variables: dict) -> str:
        """Generate a fallback validation prompt when template processing fails."""
        return f"""
Validate the following user response:

Question Asked: {variables.get('question_asked', 'N/A')}
User Answer: {variables.get('user_answer', 'N/A')}

Please respond with a JSON object containing:
- "is_relevant": true or false
- "explanation": brief explanation of your assessment

Determine if the user's answer appropriately addresses the question.
"""

    def _validate_all_templates(self):
        """Validate all loaded templates have proper format."""
        templates = {
            'initial_analysis': self.initial_analysis_template,
            'final_analysis': self.final_analysis_template,
            'input_validation': self.input_validation_template
        }
        
        for name, template in templates.items():
            if not template or not template.strip():
                logger.error(f"Template {name} is empty or invalid")

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
You are an AI assistant for {institution_name} complaint analysis.

User Message: {user_message}

Please analyze this message in {language}.

{language_instruction}

Current Date/Time: {current_date_time}

User: {user_first_name}

{critical_complaint_criteria_text}

Provide initial analysis of the complaint."""
        
        elif template_filename == 'final_analysis_prompt.txt':
            return """### Final Analysis Template
Complaint Text: {complaint_text}

Available Categories: {allowed_categories}
Category Guidance: {category_guidance}
Available Sensitivity Levels: {allowed_sensitivities}
Critical Keywords: {critical_keywords}

Please provide final analysis with appropriate categorization."""
        
        elif template_filename == 'input_validation_prompt.txt':
            return """### Input Validation Template
Question Asked: {question_asked}
User Answer: {user_answer}

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
        """Generate initial interaction prompt with better error handling."""
        try:
            self.logger.debug(f"Generating initial interaction prompt for user: {user_first_name}")
            
            # Get institution name from configuration with fallback
            institution_name = getattr(self.institution_config, 'name', institution_name or 'Institution')
            
            # Determine language based on user input or default to Arabic
            language = self._detect_language(user_input_text or "")
            
            # Prepare template variables dictionary with all required fields
            template_variables = {
                'user_message': user_input_text or "No message provided",
                'language': language,
                'institution_name': institution_name,
                'user_first_name': user_first_name or "User",
                'current_date_time': current_date_time or datetime.now().isoformat(),
                'critical_keywords': self._get_critical_keywords_text(),
                'language_instruction': self.language_instructions.get(language, self.language_instructions['ar'])
            }
            
            # Validate that we have a template to work with
            if not self.initial_analysis_template or not self.initial_analysis_template.strip():
                self.logger.error("Initial analysis template is empty or not loaded")
                return self._get_fallback_prompt(template_variables)
            
            # Format the template
            formatted_prompt = self._safe_format_template(
                self.initial_analysis_template, 
                template_variables
            )
            
            # Apply length truncation if needed
            formatted_prompt = self._truncate_if_needed(formatted_prompt)
            
            self.logger.info(f"Successfully generated initial interaction prompt for user: {user_first_name}")
            return formatted_prompt
            
        except Exception as e:
            error_msg = f"Error generating initial interaction prompt for user {user_first_name}: {e}"
            self.logger.error(error_msg)
            
            # Return a fallback prompt instead of raising
            return self._get_fallback_prompt({
                'user_message': user_input_text or "No message provided",
                'institution_name': institution_name or "Institution",
                'user_first_name': user_first_name or "User"
            })

    def generate_final_analysis_prompt(self, complaint_text: str) -> str:
        """
        Generate a specialized system prompt for final complaint analysis.
        
        This method creates a comprehensive system prompt for final analysis by populating
        the final_analysis_prompt.txt template with complaint text and dynamic configuration
        data including allowed categories, category guidance, sensitivity levels, and critical keywords.
        
        Args:
            complaint_text: The complaint text to be analyzed
            
        Returns:
            str: Complete system prompt ready for final analysis
            
        Raises:
            Exception: If template formatting fails or configuration data is missing
        """
        try:
            template_variables = {
                'complaint_text': complaint_text or "No complaint text provided",
                'allowed_categories': self._get_allowed_categories_text(),
                'category_guidance': self._get_category_guidance_text(),
                'allowed_sensitivities': self._get_allowed_sensitivities_text(),
                'critical_keywords': self._get_critical_keywords_text(),
                'allowed_sectors': self._get_allowed_sectors_text(),
                'sector_guidance': self._get_sector_guidance_text()
            }
            
            formatted_prompt = self._safe_format_template(
                self.final_analysis_template, 
                template_variables
            )
            
            return self._truncate_if_needed(formatted_prompt)
            
        except Exception as e:
            error_msg = f"Error generating final analysis prompt: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e

    async def generate_input_validation_prompt(self, question_asked: str, user_answer: str) -> str:
        """Generate input validation prompt with better error handling."""
        try:
            self.logger.debug("Generating input validation prompt")
            
            # Prepare template variables
            template_variables = {
                'question_asked': question_asked or "No question provided",
                'user_answer': user_answer or "No answer provided"
            }
            
            # Check if we have a valid template
            if not self.input_validation_template or not self.input_validation_template.strip():
                self.logger.error("Input validation template is empty or not loaded")
                return self._get_fallback_validation_prompt(template_variables)
            
            # Format the template safely
            formatted_prompt = self._safe_format_template(
                self.input_validation_template, 
                template_variables
            )
            
            # Apply truncation if needed
            formatted_prompt = self._truncate_if_needed(formatted_prompt)
            
            self.logger.info("Successfully generated input validation prompt")
            return formatted_prompt
            
        except Exception as e:
            error_msg = f"Error generating input validation prompt: {e}"
            self.logger.error(error_msg)
            
            # Return fallback prompt
            return self._get_fallback_validation_prompt({
                'question_asked': question_asked or "No question provided",
                'user_answer': user_answer or "No answer provided"
            })

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
            
            if not self.critical_complaint_config:
                logger.error("Critical complaint configuration is not available")
                return False
            
            # Test template formatting with sample data
            try:
                # Test initial analysis template
                test_initial = self._safe_format_template(
                    self.initial_analysis_template,
                    {
                        'user_message': "Test message",
                        'language': "ar",
                        'institution_name': "Test Institution",
                        'user_first_name': "Test User",
                        'current_date_time': "2024-01-01T00:00:00",
                        'critical_complaint_criteria_text': "Test criteria",
                        'language_instruction': "Test instruction"
                    }
                )
                
                # Test final analysis template with new placeholders
                test_final = self._safe_format_template(
                    self.final_analysis_template,
                    {
                        'complaint_text': "Test complaint",
                        'allowed_categories': '"Test Category"',
                        'category_guidance': '*   "Test Category": Test description',
                        'allowed_sensitivities': '"Test Sensitivity"',
                        'critical_keywords': '"Test Keyword"'
                    }
                )
                
                # Test input validation template
                test_validation = self._safe_format_template(
                    self.input_validation_template,
                    {
                        'question_asked': "Test question",
                        'user_answer': "Test answer"
                    }
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
            'critical_keywords': getattr(self.critical_complaint_config, 'keywords', []),
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
            'initial_analysis_prompt.txt': ['user_message', 'language', 'institution_name', 'user_first_name', 'current_date_time', 'critical_complaint_criteria_text', 'language_instruction'],
            'final_analysis_prompt.txt': ['complaint_text', 'allowed_categories', 'category_guidance', 'allowed_sensitivities', 'critical_keywords'],
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