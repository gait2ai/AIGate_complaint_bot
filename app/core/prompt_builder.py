"""
AI Gate for Artificial Intelligence Applications
Institution Prompt Builder Module

This module handles the construction of comprehensive system prompts by combining
institution-specific templates, institution data, and task-specific instructions for
the Institution Telegram complaint bot. It manages prompt optimization for different
complaint handling tasks such as classification, summarization, and critical complaint identification.
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
    institutional protocols and requirements.
    """

    def __init__(self, config_dir: Path, institution_data: Dict[str, Any], templates: Dict[str, Any]):
        """
        Initialize the PromptBuilder with Institution configuration and templates.
        
        Args:
            config_dir: Directory containing configuration files (app/config/)
            institution_data: Institution-specific configuration data from config.yaml
            templates: Template configuration for prompts from config.yaml prompts section
        """
        self.config_dir = Path(config_dir)
        self.institution_data = institution_data
        self.templates = templates
        
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
        
        # Load Institution system prompt template
        self.system_prompt_template = self._load_system_prompt_template()
        
        # Default output format instructions for common tasks
        self.default_output_formats = {
            'classification': 'Provide the response in JSON format with keys: "category", "subcategory", "sensitivity_level", "confidence_score".',
            'summarization': 'Provide a concise summary in 2-3 sentences highlighting the main complaint and key details.',
            'critical_identification': 'Respond with "CRITICAL" or "NON_CRITICAL" followed by a brief justification.',
            'response_generation': 'Provide a professional response that acknowledges the complaint and indicates next steps.',
            'default': 'Provide a clear and structured response addressing the specific task requirements.'
        }
        
        logger.info("Institution PromptBuilder initialized successfully")

    def _load_system_prompt_template(self) -> str:
        """
        Load the Institution system prompt template from system_prompt.txt.
        
        The method loads the template from the filename specified in
        templates.system_template_file (should be "system_prompt.txt").
        If loading fails, it falls back to a basic Institution-specific template.
        
        Returns:
            str: Institution system prompt template
        """
        # Step 1: Retrieve filename from configuration
        configured_filename = self.templates.get('system_template_file')
        
        # Step 2: Validate the configured filename
        if not configured_filename:
            logger.warning("No 'system_template_file' configured for Institution bot, using default template")
            return self._get_default_institution_system_prompt_template()
        
        if not isinstance(configured_filename, str) or not configured_filename.strip():
            logger.warning(f"Invalid 'system_template_file' value: {configured_filename!r}. Using default Institution template")
            return self._get_default_institution_system_prompt_template()
        
        # Clean the filename
        configured_filename = configured_filename.strip()
        
        # Step 3: Attempt to load from configured file
        template_file = self.config_dir / configured_filename
        
        try:
            if not template_file.exists():
                logger.error(f"Institution system prompt template file not found: '{configured_filename}' (full path: {template_file}). This is critical for the complaint bot.")
                return self._get_default_institution_system_prompt_template()
            
            if not template_file.is_file():
                logger.error(f"Institution system prompt template path is not a file: '{configured_filename}' (full path: {template_file})")
                return self._get_default_institution_system_prompt_template()
            
            # Attempt to read the file
            with open(template_file, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # Check if the file has meaningful content
            if not template_content or not template_content.strip():
                logger.error(f"Institution system prompt template file is empty: '{configured_filename}'")
                return self._get_default_institution_system_prompt_template()
            
            # Successfully loaded template from configured file
            template_content = template_content.strip()
            logger.info(f"Successfully loaded Institution system prompt template from: '{configured_filename}'")
            return template_content
            
        except PermissionError:
            logger.error(f"Permission denied reading Institution template file: '{configured_filename}'")
            return self._get_default_institution_system_prompt_template()
        
        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error reading Institution template file: '{configured_filename}': {e}")
            return self._get_default_institution_system_prompt_template()
        
        except OSError as e:
            logger.error(f"OS error reading Institution template file: '{configured_filename}': {e}")
            return self._get_default_institution_system_prompt_template()
        
        except Exception as e:
            logger.error(f"Unexpected error reading Institution template file: '{configured_filename}': {e}")
            return self._get_default_institution_system_prompt_template()

    def _get_default_institution_system_prompt_template(self) -> str:
        """
        Get the default Institution system prompt template as fallback.
        
        Returns:
            str: Default Institution system prompt template
        """
        return """### Role Definition
You are an AI-powered Virtual Complaints Officer for {institution_name}. You assist in processing, analyzing, and responding to beneficiary complaints with professionalism and empathy.

### Persona and Behavior Protocol
- Maintain a professional, empathetic, and helpful demeanor
- Prioritize beneficiary welfare and satisfaction
- Follow institutional protocols and guidelines strictly
- Ensure confidentiality and respectful communication

### Operational Boundaries and Restrictions
- Focus exclusively on complaint-related tasks
- Do not provide information outside your designated scope
- Escalate complex or sensitive issues appropriately
- Maintain data privacy and confidentiality

### Core Task Instructions
Process complaints according to institutional standards, ensuring proper classification, documentation, and response generation.

### Institution Complaint Handling Protocol Snippets & Reference Data
{context}

### Specific Task Instruction from System
{task_specific_instruction}

### User's Current Message / Complaint Text
{user_input_text}

### Required Output Format
{output_format_instruction}

### Language for User-Facing Responses (If Applicable)
{language_instruction}"""

    async def build_institution_task_prompt(self,
                                    task_specific_instruction: str,
                                    user_input_text: str,
                                    context_data: Optional[Union[str, List[Dict[str, Any]], Dict[str, Any]]] = None,
                                    output_format_instruction: Optional[str] = None,
                                    user_language_code: str = 'ar') -> str:
        """
        Build a comprehensive system prompt for Institution complaint bot tasks.
        
        Args:
            task_specific_instruction: Specific instruction for the AI task
            user_input_text: The user's complaint or message text
            context_data: Context data (complaint types, protocols, etc.)
            output_format_instruction: How the AI should format its response
            user_language_code: Language code for response (default: Arabic)
            
        Returns:
            str: Complete system prompt ready for AI model
        """
        try:
            logger.debug(f"Building Institution task prompt for: {task_specific_instruction[:50]}...")
            
            # Format context data appropriately
            context = self._format_task_context(context_data)
            
            # Get language instruction
            language_instruction = self._get_language_instruction(user_language_code)
            
            # Get institution name
            institution_name = self.institution_data.get('name', 'Institution')
            
            # Set default output format if not provided
            if not output_format_instruction:
                # Try to infer format from task instruction
                output_format_instruction = self._infer_output_format(task_specific_instruction)
            
            # Format the system prompt with all placeholders
            formatted_prompt = self.system_prompt_template.format(
                institution_name=institution_name,
                context=context,
                language_instruction=language_instruction,
                task_specific_instruction=task_specific_instruction,
                user_input_text=user_input_text,
                output_format_instruction=output_format_instruction
            )
            
            # Apply prompt optimization if enabled
            if self.templates.get('prompt_optimization', True):
                formatted_prompt = self._optimize_institution_prompt(formatted_prompt, task_specific_instruction, user_input_text)
            
            # Ensure prompt doesn't exceed length limits
            formatted_prompt = self._truncate_if_needed(formatted_prompt)
            
            logger.debug("Institution system prompt built successfully")
            return formatted_prompt
            
        except Exception as e:
            logger.error(f"Error building Institution prompt: {e}")
            # Return a basic fallback prompt
            return self._get_fallback_institution_prompt(task_specific_instruction, user_input_text)

    def _format_task_context(self, context_data: Optional[Union[str, List[Dict[str, Any]], Dict[str, Any]]]) -> str:
        """
        Format context data into a readable string for the system prompt.
        
        Args:
            context_data: Various types of context data
            
        Returns:
            str: Formatted context string
        """
        if not context_data:
            return "No specific context data provided for this task."
        
        try:
            # Handle string context (e.g., protocol text)
            if isinstance(context_data, str):
                return context_data.strip()
            
            # Handle list of dictionaries (e.g., classification keys)
            elif isinstance(context_data, list):
                if not context_data:
                    return "No context data provided."
                
                # Check if it's a list of classification_keys dictionaries
                if all(isinstance(item, dict) for item in context_data):
                    # Check if this is classification_keys data structure
                    if context_data and all('key_type' in item and 'key_value' in item for item in context_data):
                        return self._format_classification_keys(context_data)
                    
                    # Check if it's legacy complaint categories/types structure
                    elif context_data and any('category' in item or 'type' in item for item in context_data):
                        return self._format_legacy_complaint_categories(context_data)
                    
                    # Generic dictionary formatting for other structures
                    else:
                        formatted_items = []
                        for i, item in enumerate(context_data, 1):
                            item_str = f"{i}. " + ", ".join([f"{k}: {v}" for k, v in item.items()])
                            formatted_items.append(item_str)
                        return "Context items:\n" + "\n".join(formatted_items)
                else:
                    # List of non-dictionaries
                    return "Context items:\n" + "\n".join([f"- {str(item)}" for item in context_data])
            
            # Handle single dictionary (e.g., protocol info)
            elif isinstance(context_data, dict):
                if 'institution_protocol_info' in context_data:
                    # Extract Institution protocol information
                    protocol_info = context_data['institution_protocol_info']
                    if isinstance(protocol_info, str):
                        return f"Institution Protocol Information:\n{protocol_info}"
                    elif isinstance(protocol_info, dict):
                        formatted_protocol = []
                        for key, value in protocol_info.items():
                            formatted_protocol.append(f"{key.replace('_', ' ').title()}: {value}")
                        return "Institution Protocol Information:\n" + "\n".join(formatted_protocol)
                
                # Generic dictionary formatting
                formatted_dict = []
                for key, value in context_data.items():
                    formatted_dict.append(f"{key.replace('_', ' ').title()}: {value}")
                return "Context Information:\n" + "\n".join(formatted_dict)
            
            else:
                # Fallback for other types
                return f"Context Data: {str(context_data)}"
                
        except Exception as e:
            logger.warning(f"Error formatting task context: {e}")
            return f"Context data provided but could not be formatted properly: {str(context_data)[:200]}..."

    def _format_classification_keys(self, classification_keys: List[Dict[str, Any]]) -> str:
        """
        Format classification_keys data structure for the system prompt.
        
        Args:
            classification_keys: List of dictionaries with key_type, key_value, and optional parent_value
            
        Returns:
            str: Formatted classification keys string
        """
        try:
            formatted_items = []
            
            # Group items by key_type for better organization
            grouped_keys = {}
            for item in classification_keys:
                key_type = item.get('key_type', 'Unknown Type')
                if key_type not in grouped_keys:
                    grouped_keys[key_type] = []
                grouped_keys[key_type].append(item)
            
            # Format each group
            for key_type, items in grouped_keys.items():
                formatted_items.append(f"\n{key_type}:")
                
                for i, item in enumerate(items, 1):
                    key_value = item.get('key_value', 'Unknown Value')
                    parent_value = item.get('parent_value')
                    
                    item_str = f"  {i}. {key_value}"
                    
                    # Add parent value if present
                    if parent_value:
                        item_str += f" (Parent: {parent_value})"
                    
                    # Add any additional information from the item
                    additional_info = []
                    for key, value in item.items():
                        if key not in ['key_type', 'key_value', 'parent_value'] and value:
                            additional_info.append(f"{key.replace('_', ' ').title()}: {value}")
                    
                    if additional_info:
                        item_str += f" - {', '.join(additional_info)}"
                    
                    formatted_items.append(item_str)
            
            return "Available Classification Keys:" + "\n".join(formatted_items)
            
        except Exception as e:
            logger.warning(f"Error formatting classification keys: {e}")
            # Fallback to simple formatting
            simple_items = []
            for i, item in enumerate(classification_keys, 1):
                key_type = item.get('key_type', 'Unknown')
                key_value = item.get('key_value', 'Unknown')
                simple_items.append(f"{i}. {key_type}: {key_value}")
            
            return "Available Classification Keys:\n" + "\n".join(simple_items)

    def _format_legacy_complaint_categories(self, categories: List[Dict[str, Any]]) -> str:
        """
        Format legacy complaint categories structure for backward compatibility.
        
        Args:
            categories: List of dictionaries with category, type, sensitivity, etc.
            
        Returns:
            str: Formatted categories string
        """
        try:
            formatted_items = []
            for i, item in enumerate(categories, 1):
                item_str = f"{i}. "
                
                # Handle legacy structure
                if 'category' in item or 'type' in item:
                    item_str += f"Category: {item.get('category', item.get('type', 'Unknown'))}"
                    if 'subcategory' in item:
                        item_str += f", Subcategory: {item['subcategory']}"
                    if 'sensitivity' in item or 'sensitivity_level' in item:
                        item_str += f", Sensitivity: {item.get('sensitivity', item.get('sensitivity_level', 'Unknown'))}"
                    if 'description' in item:
                        item_str += f"\n   Description: {item['description']}"
                else:
                    # Generic dictionary formatting
                    item_str += ", ".join([f"{k}: {v}" for k, v in item.items()])
                
                formatted_items.append(item_str)
            
            return "Available Categories/Types:\n" + "\n".join(formatted_items)
            
        except Exception as e:
            logger.warning(f"Error formatting legacy complaint categories: {e}")
            return "Categories data provided but could not be formatted properly."

    def _get_language_instruction(self, language_code: str) -> str:
        """
        Get language-specific instruction for the AI model.
        
        Args:
            language_code: ISO language code
            
        Returns:
            str: Language instruction
        """
        return self.language_instructions.get(language_code.lower(), self.language_instructions['ar'])

    def _infer_output_format(self, task_instruction: str) -> str:
        """
        Infer appropriate output format based on task instruction.
        
        Args:
            task_instruction: The specific task instruction
            
        Returns:
            str: Appropriate output format instruction
        """
        task_lower = task_instruction.lower()
        
        if 'classif' in task_lower or 'categor' in task_lower:
            return self.default_output_formats['classification']
        elif 'summar' in task_lower:
            return self.default_output_formats['summarization']
        elif 'critical' in task_lower or 'urgent' in task_lower or 'priority' in task_lower:
            return self.default_output_formats['critical_identification']
        elif 'respond' in task_lower or 'reply' in task_lower:
            return self.default_output_formats['response_generation']
        else:
            return self.default_output_formats['default']

    def _optimize_institution_prompt(self, prompt: str, task_instruction: str, user_input: str) -> str:
        """
        Optimize the prompt based on Institution-specific requirements and task context.
        
        Args:
            prompt: The base prompt to optimize
            task_instruction: The specific task instruction
            user_input: The user's input text
            
        Returns:
            str: Optimized prompt
        """
        try:
            optimization_notes = []
            
            # Task-specific optimizations
            task_lower = task_instruction.lower()
            
            if 'classif' in task_lower:
                optimization_notes.append("Ensure classification matches provided categories exactly")
                optimization_notes.append("Provide confidence scores for classification decisions")
            
            elif 'critical' in task_lower or 'urgent' in task_lower:
                optimization_notes.append("Focus on identifying urgency indicators and safety concerns")
                optimization_notes.append("Consider beneficiary vulnerability and immediate needs")
            
            elif 'summar' in task_lower:
                optimization_notes.append("Capture key complaint details while maintaining brevity")
                optimization_notes.append("Highlight actionable items and required follow-up")
            
            elif 'respond' in task_lower:
                optimization_notes.append("Maintain empathetic and professional tone")
                optimization_notes.append("Provide clear next steps and contact information")
            
            # Input-specific optimizations
            if len(user_input) > 500:
                optimization_notes.append("Handle detailed complaint text thoroughly")
            
            if any(word in user_input.lower() for word in ['urgent', 'emergency', 'help', 'immediate']):
                optimization_notes.append("Pay special attention to urgency indicators in the complaint")
            
            # Append optimization notes to prompt
            if optimization_notes:
                optimization_section = "\n### Additional Processing Guidelines\n" + "\n".join(f"- {note}" for note in optimization_notes)
                prompt += optimization_section
            
            return prompt
            
        except Exception as e:
            logger.warning(f"Error optimizing Institution prompt: {e}")
            return prompt

    def _truncate_if_needed(self, prompt: str) -> str:
        """
        Truncate prompt if it exceeds maximum length limits, preserving critical sections.
        
        Args:
            prompt: The prompt to check and potentially truncate
            
        Returns:
            str: Truncated prompt if necessary
        """
        max_length = self.templates.get('max_prompt_length', 12000)
        
        if len(prompt) <= max_length:
            return prompt
        
        logger.warning(f"Institution prompt length ({len(prompt)}) exceeds maximum ({max_length}), truncating...")
        
        # Split prompt into sections
        lines = prompt.split('\n')
        
        # Identify critical sections that should be preserved
        critical_sections = [
            '### Role Definition',
            '### Persona and Behavior Protocol',
            '### Specific Task Instruction from System',
            '### User\'s Current Message / Complaint Text',
            '### Required Output Format',
            '### Language for User-Facing Responses'
        ]
        
        # Find context section for potential truncation
        context_start = -1
        context_end = -1
        
        for i, line in enumerate(lines):
            if '### Institution Complaint Handling Protocol Snippets & Reference Data' in line:
                context_start = i + 1
            elif context_start > -1 and line.startswith('###') and 'Protocol Snippets' not in line:
                context_end = i
                break
        
        if context_start > -1:
            if context_end == -1:
                context_end = len(lines)
            
            # Calculate available space for context
            context_lines = lines[context_start:context_end]
            other_lines = lines[:context_start] + lines[context_end:]
            other_length = len('\n'.join(other_lines))
            
            available_for_context = max_length - other_length - 200  # Buffer
            
            if available_for_context > 0:
                # Truncate context to fit
                truncated_context = []
                current_length = 0
                
                for line in context_lines:
                    if current_length + len(line) + 1 > available_for_context:
                        if truncated_context:
                            truncated_context.append("...[Context truncated due to length limits]")
                        break
                    truncated_context.append(line)
                    current_length += len(line) + 1
                
                # Reconstruct prompt
                lines = lines[:context_start] + truncated_context + lines[context_end:]
        
        truncated_prompt = '\n'.join(lines)
        
        # Final length check and hard truncation if still too long
        if len(truncated_prompt) > max_length:
            truncated_prompt = truncated_prompt[:max_length - 100] + "\n...[Prompt truncated due to length limits]"
        
        return truncated_prompt

    def _get_fallback_institution_prompt(self, task_instruction: str, user_input: str) -> str:
        """
        Get a basic Institution fallback prompt when prompt building fails.
        
        Args:
            task_instruction: The task instruction
            user_input: The user input text
            
        Returns:
            str: Basic Institution fallback prompt
        """
        institution_name = self.institution_data.get('name', 'Institution')
        
        return f"""You are a Virtual Complaints Officer for {institution_name}.

Task: {task_instruction}

User Input: {user_input}

Please process this complaint according to institutional standards and provide an appropriate response in Arabic unless otherwise specified.

Maintain professionalism, empathy, and follow proper complaint handling protocols."""

    async def get_template_variables(self) -> Dict[str, Any]:
        """
        Get available template variables for Institution prompt customization.
        
        Returns:
            Dict[str, Any]: Available template variables
        """
        return {
            'institution_name': self.institution_data.get('name', 'Institution'),
            'institution_website': self.institution_data.get('website', ''),
            'institution_description': self.institution_data.get('description', ''),
            'supported_languages': list(self.language_instructions.keys()),
            'template_file': str(self.config_dir / self.templates.get('system_template_file', 'system_prompt.txt')),
            'default_language': 'ar',
            'available_output_formats': list(self.default_output_formats.keys()),
            'institution_protocol_info': self.templates.get('institution_protocol_info', {})
        }

    async def validate_institution_template(self, template_content: str) -> Dict[str, Any]:
        """
        Validate an Institution prompt template for required placeholders and format.
        
        Args:
            template_content: The template content to validate
            
        Returns:
            Dict[str, Any]: Validation results
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'required_placeholders': [
                'institution_name', 'context', 'language_instruction',
                'task_specific_instruction', 'user_input_text', 'output_format_instruction'
            ],
            'found_placeholders': []
        }
        
        try:
            # Check for required placeholders
            for placeholder in validation_result['required_placeholders']:
                placeholder_pattern = f"{{{placeholder}}}"
                if placeholder_pattern in template_content:
                    validation_result['found_placeholders'].append(placeholder)
                else:
                    validation_result['errors'].append(f"Missing required placeholder: {placeholder_pattern}")
                    validation_result['is_valid'] = False
            
            # Check for Institution-specific sections
            required_sections = [
                '### Role Definition',
                '### Institution Complaint Handling Protocol Snippets & Reference Data',
                '### Specific Task Instruction from System',
                '### User\'s Current Message / Complaint Text'
            ]
            
            for section in required_sections:
                if section not in template_content:
                    validation_result['warnings'].append(f"Missing recommended section: {section}")
            
            # Check template length
            if len(template_content) > 3000:
                validation_result['warnings'].append("Template is quite long, consider condensing for better performance")
            
        except Exception as e:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f"Template validation error: {str(e)}")
        
        return validation_result

    def is_healthy(self) -> bool:
        """
        Check if the Institution PromptBuilder is healthy and functioning properly.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            # Check if we have a valid Institution template
            if not self.system_prompt_template:
                logger.error("Institution system prompt template is not loaded")
                return False
            
            # Check if institution data is available
            if not self.institution_data:
                logger.error("Institution data is not available")
                return False
            
            # Check for required placeholders in template
            required_placeholders = [
                '{institution_name}', '{context}', '{language_instruction}',
                '{task_specific_instruction}', '{user_input_text}', '{output_format_instruction}'
            ]
            
            for placeholder in required_placeholders:
                if placeholder not in self.system_prompt_template:
                    logger.error(f"Required placeholder {placeholder} not found in Institution template")
                    return False
            
            # Try to format a test prompt
            test_prompt = self.system_prompt_template.format(
                institution_name=self.institution_data.get('name', 'Institution'),
                context="Test context",
                language_instruction=self.language_instructions['ar'],
                task_specific_instruction="Test task",
                user_input_text="Test input",
                output_format_instruction="Test format"
            )
            
            return len(test_prompt) > 0
            
        except Exception as e:
            logger.error(f"Institution PromptBuilder health check failed: {e}")
            return False

    async def cleanup(self):
        """Clean up resources and connections."""
        logger.info("Institution PromptBuilder cleanup completed")
        pass

    # Legacy method kept for backward compatibility but marked as deprecated
    async def build_prompt(self, 
                          original_question: str, 
                          processed_question: Dict[str, Any], 
                          research_results: List[Dict[str, Any]]) -> str:
        """
        Legacy method for backward compatibility.
        For Institution bot, use build_institution_task_prompt instead.
        """
        logger.warning("Using deprecated build_prompt method. Use build_institution_task_prompt for Institution bot tasks.")
        
        # Convert to Institution format
        task_instruction = f"Answer the following question: {original_question}"
        user_input = original_question
        context_data = research_results if research_results else None
        
        return await self.build_institution_task_prompt(
            task_specific_instruction=task_instruction,
            user_input_text=user_input,
            context_data=context_data,
            user_language_code=processed_question.get('language', 'ar')
        )