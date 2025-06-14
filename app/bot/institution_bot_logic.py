"""
AI Gate for Artificial Intelligence Applications

Institution Telegram Bot Core Logic
Contains the primary InstitutionBot class for complaint management system.
"""

import os
import logging
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import pytz
import yaml

# Telegram libraries
from telegram import Update
from telegram.ext import Application, ContextTypes

# Core modules
from app.core.ai_handler import AIHandler
from app.core.cache_manager import CacheManager
from app.core.prompt_builder import PromptBuilder
from app.core.database_manager import DatabaseManager


@dataclass
class ComplaintData:
    """Data structure for complaint information"""
    user_id: int
    name: str = ""
    sex: str = ""
    phone: str = ""
    residence_status: str = ""
    governorate: str = ""
    directorate: str = ""
    village: str = ""
    complaint_details: str = ""  # English summary
    is_critical: bool = False
    original_complaint_text: str = ""
    telegram_message_date: Optional[datetime] = None


class InstitutionBot:
    """
    Primary bot class for institution's Telegram-based complaint management system.
    """
    
    def __init__(self, config: Dict, ai_handler: AIHandler, 
                 cache_manager: Optional[CacheManager], 
                 prompt_builder: PromptBuilder, telegram_token: str,
                 database_manager: DatabaseManager):
        """Initialize InstitutionBot with required services and configuration"""
        
        # Store core dependencies
        self.config = config
        self.ai_handler = ai_handler
        self.cache_manager = cache_manager
        self.prompt_builder = prompt_builder
        self.telegram_token = telegram_token
        self.db_manager = database_manager
        
        # Extract institution-specific settings
        institution_settings = self.config.get('institution_bot_settings', self.config.get('bcfhd_bot_settings', {}))
        self.critical_email = institution_settings.get('critical_complaint_email', '')
        
        # Set timezone
        self.local_tz = pytz.timezone(self.config['institution']['timezone'])
        
        # Initialize data structures
        self.user_data: Dict[int, ComplaintData] = {}
        self.complaint_classification_keys: List[Dict] = []
        
        # Setup logger
        self.logger = logging.getLogger(__name__)
    
    async def initialize_internal_services(self, application=None):
        """Initialize services and load classification keys"""
        await self._load_classification_keys()
    
    async def _load_classification_keys(self):
        """Load complaint classification keys from database"""
        try:
            # Fetch all active classification keys from database
            keys_data = self.db_manager.fetch_all(
                "SELECT key_type, key_value, parent_value FROM classification_keys WHERE is_active = 1"
            )
            
            # Convert to list of dictionaries for compatibility
            self.complaint_classification_keys = []
            for row in keys_data:
                self.complaint_classification_keys.append({
                    'key_type': row[0],
                    'key_value': row[1],
                    'parent_value': row[2]
                })
            
            self.logger.info(f"Loaded {len(self.complaint_classification_keys)} classification keys from database")
            
        except Exception as e:
            self.logger.error(f"Failed to load classification keys: {e}")
            self.complaint_classification_keys = []
    
    # Timestamp Helper Methods
    
    def _get_current_local_timestamp(self) -> str:
        """Get current timestamp in local timezone as ISO string"""
        return datetime.now(self.local_tz).isoformat()
    
    def _process_telegram_message_timestamp(self, telegram_date: Optional[datetime]) -> str:
        """
        Process Telegram message timestamp for submitted_at field.
        
        Args:
            telegram_date: The datetime from Telegram message
            
        Returns:
            ISO formatted timestamp string in local timezone
        """
        if telegram_date is None:
            # Use current time in local timezone
            return self._get_current_local_timestamp()
        
        try:
            if telegram_date.tzinfo is None:
                # Assume naive datetime is in UTC, then convert to local timezone
                utc_date = pytz.UTC.localize(telegram_date)
                local_date = utc_date.astimezone(self.local_tz)
            else:
                # Already timezone-aware, convert to local timezone
                local_date = telegram_date.astimezone(self.local_tz)
            
            return local_date.isoformat()
            
        except Exception as e:
            self.logger.warning(f"Error processing telegram timestamp: {e}, using current time")
            return self._get_current_local_timestamp()
    
    # LLM Interaction Helper Methods
    
    async def _get_llm_response(self, task_specific_instruction: str, 
                               user_input: str, context_data: Optional[Any] = None,
                               output_format_instruction: Optional[str] = None,
                               user_language_code: str = 'ar') -> Optional[str]:
        """Generic helper to get LLM response using prompt builder"""
        try:
            system_prompt = await self.prompt_builder.build_institution_task_prompt(
                task_specific_instruction=task_specific_instruction,
                user_input_text=user_input,
                context_data=context_data,
                output_format_instruction=output_format_instruction,
                user_language_code=user_language_code
            )
            
            response = await self.ai_handler.generate_response(
                user_message=user_input,
                system_prompt=system_prompt,
                context=context_data
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"LLM response error: {e}")
            return None
    
    async def _is_critical_complaint_llm(self, text: str) -> bool:
        """Determine if complaint is critical using LLM"""
        try:
            task_instruction = """Determine if this complaint is CRITICAL or NON_CRITICAL.
            CRITICAL complaints involve: immediate danger, severe health issues, 
            urgent humanitarian needs, life-threatening situations, or severe violations of rights.
            NON_CRITICAL complaints are general feedback, suggestions, or non-urgent issues."""
            
            response = await self._get_llm_response(
                task_specific_instruction=task_instruction,
                user_input=text,
                output_format_instruction="Respond ONLY with CRITICAL or NON_CRITICAL."
            )
            
            if response:
                return response.strip().upper() == "CRITICAL"
            return False
            
        except Exception as e:
            self.logger.error(f"Critical complaint check error: {e}")
            return False
    
    async def _classify_complaint_llm(self, complaint_text: str) -> Tuple[str, str, str]:
        """Classify complaint using LLM and classification keys"""
        try:
            task_instruction = """Classify this complaint based on the provided classification keys.
            Analyze the complaint text and match it to the most appropriate type, category, and sensitivity level."""
            
            output_format = 'Respond ONLY with JSON: {"complaint_type": "TypeValue", "complaint_category": "CategoryValue", "complaint_sensitivity": "SensitivityValue"}'
            
            response = await self._get_llm_response(
                task_specific_instruction=task_instruction,
                user_input=complaint_text,
                context_data=self.complaint_classification_keys,
                output_format_instruction=output_format
            )
            
            if response:
                try:
                    result = json.loads(response.strip())
                    return (
                        result.get("complaint_type", "General"),
                        result.get("complaint_category", "Other"),
                        result.get("complaint_sensitivity", "Normal")
                    )
                except json.JSONDecodeError:
                    self.logger.error(f"Failed to parse classification JSON: {response}")
            
            return ("General", "Other", "Normal")
            
        except Exception as e:
            self.logger.error(f"Complaint classification error: {e}")
            return ("General", "Other", "Normal")
    
    async def _summarize_and_translate_complaint_llm(self, arabic_text: str) -> str:
        """Summarize and translate Arabic complaint to English"""
        try:
            task_instruction = """Summarize and translate this Arabic complaint text to English.
            Provide a clear, concise summary that captures the main points and concerns."""
            
            response = await self._get_llm_response(
                task_specific_instruction=task_instruction,
                user_input=arabic_text,
                output_format_instruction="Provide ONLY the English summary."
            )
            
            return response.strip() if response else arabic_text
            
        except Exception as e:
            self.logger.error(f"Translation/summary error: {e}")
            return arabic_text
    
    async def _determine_user_intent_llm(self, text: str) -> str:
        """Determine user intent from message text"""
        try:
            task_instruction = f"""User sent: '{text}'. Analyze the intent of this message.
            Determine if this is a complaint, suggestion, contact request, or off-topic message."""
            
            output_format = "Respond ONLY with one of: COMPLAINT_INTENT, SUGGESTION_INTENT, CONTACT_INTENT, OFF_TOPIC"
            
            response = await self._get_llm_response(
                task_specific_instruction=task_instruction,
                user_input=text,
                output_format_instruction=output_format
            )
            
            if response and response.strip() in ["COMPLAINT_INTENT", "SUGGESTION_INTENT", "CONTACT_INTENT", "OFF_TOPIC"]:
                return response.strip()
            
            return "OFF_TOPIC"
            
        except Exception as e:
            self.logger.error(f"Intent determination error: {e}")
            return "OFF_TOPIC"
    
    # Python-based Helper Methods
    
    def _transliterate_yemeni_location_py(self, arabic_text: str) -> str:
        """Transliterate Yemeni Arabic location names to English script"""
        if not arabic_text or not self._is_arabic_text(arabic_text):
            return arabic_text
        
        # Basic Arabic to English transliteration mapping
        transliteration_map = {
            'ا': 'a', 'ب': 'b', 'ت': 't', 'ث': 'th', 'ج': 'j', 'ح': 'h',
            'خ': 'kh', 'د': 'd', 'ذ': 'dh', 'ر': 'r', 'ز': 'z', 'س': 's',
            'ش': 'sh', 'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': 'a',
            'غ': 'gh', 'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm',
            'ن': 'n', 'ه': 'h', 'و': 'w', 'ي': 'y', 'ى': 'a', 'ة': 'a',
            'أ': 'a', 'إ': 'i', 'آ': 'aa', 'ء': '', ' ': ' '
        }
        
        # Common Yemeni prefixes and locations
        common_locations = {
            'صنعاء': 'Sana\'a',
            'عدن': 'Aden',
            'تعز': 'Taiz',
            'الحديدة': 'Al-Hudaydah',
            'إب': 'Ibb',
            'ذمار': 'Dhamar',
            'مأرب': 'Marib',
            'لحج': 'Lahij',
            'أبين': 'Abyan',
            'شبوة': 'Shabwah',
            'حضرموت': 'Hadramawt',
            'المهرة': 'Al-Mahrah',
            'سقطرى': 'Soqotra'
        }
        
        # Check for exact matches first
        arabic_text_clean = arabic_text.strip()
        if arabic_text_clean in common_locations:
            return common_locations[arabic_text_clean]
        
        # Transliterate character by character
        result = ""
        for char in arabic_text:
            result += transliteration_map.get(char, char)
        
        # Clean up result
        result = re.sub(r'\s+', ' ', result.strip())
        result = result.title()  # Capitalize first letter of each word
        
        return result if result else arabic_text
    
    def _is_arabic_text(self, text: str) -> bool:
        """Check if text contains Arabic characters"""
        if not text:
            return False
        
        arabic_chars = 0
        total_chars = 0
        
        for char in text:
            if char.isalpha():
                total_chars += 1
                if '\u0600' <= char <= '\u06FF' or '\u0750' <= char <= '\u077F':
                    arabic_chars += 1
        
        return total_chars > 0 and (arabic_chars / total_chars) > 0.5
    
    def _has_minimal_profile_data(self, data: ComplaintData) -> bool:
        """Check if complaint data has minimal required profile information"""
        # At minimum, we need a name for beneficiary profile
        return bool(data.name and data.name.strip())
    
    def _prepare_profile_data_for_db(self, data: ComplaintData) -> Dict[str, str]:
        """Prepare profile data for database insertion, handling missing fields gracefully"""
        return {
            'name': data.name.strip() if data.name else '',
            'sex': data.sex.strip() if data.sex else '',
            'phone': data.phone.strip() if data.phone else '',
            'residence_status': data.residence_status.strip() if data.residence_status else '',
            'governorate': data.governorate.strip() if data.governorate else '',
            'directorate': data.directorate.strip() if data.directorate else '',
            'village_area': data.village.strip() if data.village else ''
        }
    
    # Database Interaction Methods
    
    async def _check_existing_beneficiary_profile(self, user_id: int) -> Optional[Dict]:
        """Check if beneficiary exists in the database"""
        try:
            result = self.db_manager.fetch_one(
                "SELECT name, sex, phone, residence_status, governorate, directorate, village_area FROM beneficiaries WHERE user_telegram_id = ?",
                (user_id,)
            )
            
            if result:
                return {
                    'name': result[0] or '',
                    'sex': result[1] or '',
                    'phone': result[2] or '',
                    'residence_status': result[3] or '',
                    'governorate': result[4] or '',
                    'directorate': result[5] or '',
                    'village_area': result[6] or ''
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking existing beneficiary: {e}")
            return None
    
    async def _save_beneficiary_profile(self, data: ComplaintData) -> bool:
        """
        Save or update beneficiary profile in database.
        Handles cases with minimal profile information gracefully.
        
        Args:
            data: ComplaintData object with profile information
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if we have minimal required data
            if not self._has_minimal_profile_data(data):
                self.logger.warning(f"Insufficient profile data for user {data.user_id}, skipping profile save")
                return False
            
            current_timestamp = self._get_current_local_timestamp()
            profile_data = self._prepare_profile_data_for_db(data)
            
            # Check if beneficiary exists
            existing = await self._check_existing_beneficiary_profile(data.user_id)
            
            if existing:
                # Update existing beneficiary with only non-empty fields
                update_fields = []
                update_values = []
                
                for field, value in profile_data.items():
                    if value:  # Only update non-empty fields
                        update_fields.append(f"{field} = ?")
                        update_values.append(value)
                
                if update_fields:
                    update_fields.append("updated_at = ?")
                    update_values.extend([current_timestamp, data.user_id])
                    
                    query = f"UPDATE beneficiaries SET {', '.join(update_fields)} WHERE user_telegram_id = ?"
                    self.db_manager.execute_query(query, tuple(update_values))
                    
            else:
                # Insert new beneficiary
                self.db_manager.execute_query(
                    """INSERT INTO beneficiaries 
                       (user_telegram_id, name, sex, phone, residence_status, 
                        governorate, directorate, village_area, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (data.user_id, profile_data['name'], profile_data['sex'], 
                     profile_data['phone'], profile_data['residence_status'],
                     profile_data['governorate'], profile_data['directorate'], 
                     profile_data['village_area'], current_timestamp, current_timestamp)
                )
            
            self.logger.info(f"Beneficiary profile saved for user {data.user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving beneficiary profile: {e}")
            return False
    
    async def _get_or_create_anonymous_beneficiary(self) -> Optional[int]:
        """
        Get or create an anonymous beneficiary for suggestions/feedback with minimal data.
        
        Returns:
            int: beneficiary_id or None if failed
        """
        try:
            # Check if anonymous beneficiary exists
            result = self.db_manager.fetch_one(
                "SELECT id FROM beneficiaries WHERE name = ? AND user_telegram_id IS NULL",
                ("Anonymous User",)
            )
            
            if result:
                return result[0]
            
            # Create anonymous beneficiary
            current_timestamp = self._get_current_local_timestamp()
            self.db_manager.execute_query(
                """INSERT INTO beneficiaries 
                   (user_telegram_id, name, sex, phone, residence_status, 
                    governorate, directorate, village_area, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (None, "Anonymous User", "", "", "", "", "", "", 
                 current_timestamp, current_timestamp)
            )
            
            # Get the newly created beneficiary ID
            result = self.db_manager.fetch_one(
                "SELECT id FROM beneficiaries WHERE name = ? AND created_at = ?",
                ("Anonymous User", current_timestamp)
            )
            
            if result:
                self.logger.info("Created anonymous beneficiary for suggestions/feedback")
                return result[0]
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error creating anonymous beneficiary: {e}")
            return None
    
    async def _log_complaint(self, data: ComplaintData) -> bool:
        """
        Log complaint to database with full processing.
        Handles both full complaints and simple suggestions/feedback.
        
        Args:
            data: ComplaintData object with complaint information
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Determine beneficiary ID based on available data
            beneficiary_id = None
            
            if self._has_minimal_profile_data(data):
                # Save/update full beneficiary profile
                profile_saved = await self._save_beneficiary_profile(data)
                if profile_saved:
                    beneficiary_result = self.db_manager.fetch_one(
                        "SELECT id FROM beneficiaries WHERE user_telegram_id = ?",
                        (data.user_id,)
                    )
                    if beneficiary_result:
                        beneficiary_id = beneficiary_result[0]
            
            # If no beneficiary_id found, use anonymous beneficiary for suggestions/feedback
            if not beneficiary_id:
                self.logger.info(f"Using anonymous beneficiary for user {data.user_id} submission")
                beneficiary_id = await self._get_or_create_anonymous_beneficiary()
                
                if not beneficiary_id:
                    self.logger.error("Could not create or find anonymous beneficiary")
                    return False
            
            # Get classification using LLM
            complaint_type, complaint_category, complaint_sensitivity = await self._classify_complaint_llm(
                data.original_complaint_text
            )
            
            # Get English summary if needed
            if self._is_arabic_text(data.original_complaint_text):
                data.complaint_details = await self._summarize_and_translate_complaint_llm(
                    data.original_complaint_text
                )
            else:
                data.complaint_details = data.original_complaint_text
            
            # Handle timestamps with improved processing
            current_timestamp = self._get_current_local_timestamp()
            submitted_at = self._process_telegram_message_timestamp(data.telegram_message_date)
            
            # Insert complaint into database
            self.db_manager.execute_query(
                """INSERT INTO complaints 
                   (beneficiary_id, original_complaint_text, complaint_summary_en, 
                    complaint_type, complaint_category, complaint_sensitivity, is_critical, status, 
                    source_channel, submitted_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (beneficiary_id, data.original_complaint_text, data.complaint_details,
                 complaint_type, complaint_category, complaint_sensitivity, data.is_critical, "PENDING",
                 "TELEGRAM", submitted_at, current_timestamp, current_timestamp)
            )
            
            self.logger.info(f"Complaint logged for user {data.user_id} (beneficiary_id: {beneficiary_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"Error logging complaint: {e}")
            return False
    
    # Email Method (Commented out for now)
    
    async def _send_critical_complaint_email(self, data: ComplaintData) -> bool:
        """Send email notification for critical complaints"""
        # Email functionality temporarily disabled
        return True
    
    async def run(self):
        """Main run method to start the Telegram bot"""
        try:
            # Create Telegram application
            application = Application.builder().token(self.telegram_token).build()
            
            # Set post-init to initialize internal services
            application.post_init = self.initialize_internal_services
            
            # Import and setup Telegram handlers
            from app.bot.bot_telegram_handlers import setup_telegram_handlers
            setup_telegram_handlers(application, self)
            
            self.logger.info("Institution Telegram Bot starting polling...")
            
            # Start polling
            await application.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            self.logger.error(f"Error starting bot: {e}")
            raise