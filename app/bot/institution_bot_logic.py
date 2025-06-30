"""
AI Gate for Artificial Intelligence Applications

Institution Bot Logic Module
This module contains the primary InstitutionBot class, which encapsulates the core business logic 
for the complaint management system. This class integrates all core services (AI, Database, Cache, 
Prompts, LLMOrchestrator) and manages data processing, AI-driven analysis, and database interactions, 
serving as the backend brain for the Telegram handlers.

REFACTORED: Updated to use Pydantic AppConfig model with attribute-style access
instead of dictionary-style configuration access for improved type safety and code quality.

PERFORMANCE FIX: All db_manager calls now wrapped with asyncio.to_thread() to prevent
blocking the event loop and enable concurrent request handling.
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
from telegram.ext import Application, ContextTypes, PicklePersistence

# Core modules
from app.core.ai_handler import AIHandler
from app.core.cache_manager import CacheManager
from app.core.prompt_builder import PromptBuilder
from app.core.database_manager import DatabaseManager
from app.core.llm_orchestrator import LLMOrchestrator
from app.core.email_service import EmailService

# Import the Pydantic configuration model and ComplaintData DTO
from app.config.config_model import AppConfig, ComplaintData


class InstitutionBot:
    """
    Primary bot class for institution's Telegram-based complaint management system.
    Integrates AI services, database operations, and configuration management to provide
    comprehensive complaint processing and analysis capabilities.
    
    REFACTORED: Now uses Pydantic AppConfig model for type-safe configuration access.
    PERFORMANCE FIX: All database operations are now non-blocking using asyncio.to_thread().
    """
    
    def __init__(self, config: AppConfig, ai_handler: AIHandler, 
                 cache_manager: Optional[CacheManager], 
                 prompt_builder: PromptBuilder, telegram_token: str,
                 database_manager: DatabaseManager,
                 persistence: Optional[PicklePersistence] = None,
                 email_service: EmailService = None):
        """
        Initialize InstitutionBot with required services and configuration.
        
        Args:
            config: Pydantic AppConfig model instance for type-safe configuration access
            ai_handler: AI service handler for LLM interactions
            cache_manager: Optional cache manager for performance optimization
            prompt_builder: Service for building AI prompts
            telegram_token: Telegram bot API token
            database_manager: Database operations manager
            persistence: Optional PicklePersistence object for conversation persistence
            email_service: Email service for sending notifications
        """
        
        # Store core dependencies with type-safe config
        self.config = config
        self.ai_handler = ai_handler
        self.cache_manager = cache_manager
        self.prompt_builder = prompt_builder
        self.telegram_token = telegram_token
        self.db_manager = database_manager
        self.persistence = persistence
        self.email_service = email_service
        
        # Initialize LLMOrchestrator
        self.llm_orchestrator = LLMOrchestrator(self.prompt_builder, self.ai_handler)
        
        # Set timezone using attribute access
        self.local_tz = pytz.timezone(self.config.institution.timezone)
        
        # Initialize data structures
        self.user_data: Dict[int, ComplaintData] = {}
        self.complaint_classification_keys: List[Dict] = []
        
        # Setup logger
        self.logger = logging.getLogger(__name__)
    
    async def setup_application(self) -> Application:
        """
        Create and configure the telegram.ext.Application object.
        
        Returns:
            Application: Configured Telegram application instance
        """
        try:
            # Create Telegram application builder
            builder = Application.builder().token(self.telegram_token)
            
            # Add persistence if configured
            if self.persistence:
                builder.persistence(self.persistence)
            
            # Build the application
            application = builder.build()
            
            # Set post-init to initialize internal services
            application.post_init = self.initialize_internal_services
            
            # Import and setup Telegram handlers
            # from app.bot.bot_telegram_handlers import setup_telegram_handlers
            # setup_telegram_handlers(application, self)
            
            self.logger.info("Institution Telegram Bot application configured successfully")
            return application
            
        except Exception as e:
            self.logger.error(f"Error setting up application: {e}")
            raise
    
    async def initialize_internal_services(self, application=None):
        """Initialize services and load classification keys"""
        await self._load_classification_keys()
    
    async def _load_classification_keys(self):
        """Load complaint classification keys from database"""
        try:
            # Fetch all active classification keys from database (async)
            keys_data = await asyncio.to_thread(
                self.db_manager.fetch_all,
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
    
    async def ensure_beneficiary_record(self, user_id: int, user_first_name: str):
        """
        Ensure beneficiary record exists for new users.
        Called upon receiving the first message from a new user.
        
        Args:
            user_id: Telegram user ID
            user_first_name: First name from Telegram
        """
        try:
            # Check if beneficiary already exists (async)
            existing = await asyncio.to_thread(
                self.db_manager.fetch_one,
                "SELECT id, name FROM beneficiaries WHERE user_telegram_id = ?",
                (user_id,)
            )
            if existing:
                # Update last_seen_at if such field exists (optional)
                self.logger.info(f"Beneficiary already exists for user {user_id}")
                # Optionally update last_seen_at timestamp here if field is added to schema
                return
            
            # Create new beneficiary record (async)
            current_timestamp = self._get_current_local_timestamp()
            await asyncio.to_thread(
                self.db_manager.execute_query,
                """INSERT INTO beneficiaries 
                   (user_telegram_id, name, sex, phone, residence_status, 
                    governorate, directorate, village_area, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, user_first_name, "", "", "", "", "", "", 
                 current_timestamp, current_timestamp)
            )
            
            self.logger.info(f"Created initial beneficiary record for user {user_id} with name: {user_first_name}")
            
        except Exception as e:
            self.logger.error(f"Error ensuring beneficiary record for user {user_id}: {e}")
    
    async def analyze_first_contact_message(
        self, 
        user_input_text: str, 
        user_first_name: str
    ) -> Tuple[str, str, Optional[str]]:
        """
        Analyze initial user message using LLMOrchestrator.
        
        Args:
            user_input_text: The user's message text
            user_first_name: User's first name from Telegram
            
        Returns:
            Tuple[str, str, Optional[str]]: (signal, llm_response_text, user_facing_summary)
        """
        try:
            self.logger.info(f"Starting analysis of first contact message for user: {user_first_name}")
            
            # Retrieve institution name using attribute access
            institution_name = self.config.institution.name_en
            
            # Retrieve critical complaint criteria using attribute access
            critical_complaint_criteria = self.config.critical_complaint_config.identification_criteria
            
            # Generate current date/time text
            current_date_time = self._get_current_local_timestamp()
            
            # Call LLMOrchestrator for analysis
            signal, llm_response_text, user_facing_summary = await self.llm_orchestrator.analyze_initial_message(
                user_input_text=user_input_text,
                user_first_name=user_first_name,
                institution_name=institution_name,
                critical_complaint_criteria=critical_complaint_criteria,
                current_date_time=current_date_time
            )
            
            self.logger.info(f"Analysis completed with signal: {signal}")
            return signal, llm_response_text, user_facing_summary
            
        except Exception as e:
            self.logger.error(f"Error in analyze_first_contact_message: {e}")
            return "CLARIFICATION_NEEDED", "I'm sorry, I encountered an issue processing your message. Could you please try again?", None
    
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
                # Assume naive datetime is in UTF, then convert to local timezone
                utc_date = pytz.UTC.localize(telegram_date)
                local_date = utc_date.astimezone(self.local_tz)
            else:
                # Already timezone-aware, convert to local timezone
                local_date = telegram_date.astimezone(self.local_tz)
            
            return local_date.isoformat()
            
        except Exception as e:
            self.logger.warning(f"Error processing telegram timestamp: {e}, using current time")
            return self._get_current_local_timestamp()
    
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
    
    async def _check_existing_beneficiary_profile(self, user_id: int) -> Optional[Dict]:
        """Check if beneficiary exists in the database"""
        try:
            result = await asyncio.to_thread(
                self.db_manager.fetch_one,
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
        Enhanced to handle placeholder names and preserve user_first_name when appropriate.
        
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
            
            # Get anonymous user placeholder from config using attribute access
            anonymous_user_name = self.config.application_settings.placeholders.anonymous_user_name
            
            # Check if the name is empty or matches the placeholder
            if not profile_data['name'] or profile_data['name'] == anonymous_user_name:
                # Fetch the user's first_name from the initial beneficiary record (async)
                try:
                    result = await asyncio.to_thread(
                        self.db_manager.fetch_one,
                        "SELECT name FROM beneficiaries WHERE user_telegram_id = ?",
                        (data.user_id,)
                    )
                    if result and result[0] and result[0] != anonymous_user_name:
                        profile_data['name'] = result[0]
                        self.logger.info(f"Using preserved first_name for user {data.user_id}: {profile_data['name']}")
                except Exception as e:
                    self.logger.warning(f"Could not retrieve preserved first_name for user {data.user_id}: {e}")
            
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
                    await asyncio.to_thread(
                        self.db_manager.execute_query, 
                        query, 
                        tuple(update_values)
                    )
                    
            else:
                # Insert new beneficiary (async)
                await asyncio.to_thread(
                    self.db_manager.execute_query,
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
        Uses centralized configuration for anonymous user name.
        
        Returns:
            int: beneficiary_id or None if failed
        """
        try:
            # Get anonymous user name from config using attribute access
            anonymous_user_name = self.config.application_settings.placeholders.anonymous_user_name
            
            # Check if anonymous beneficiary exists (async)
            result = await asyncio.to_thread(
                self.db_manager.fetch_one,
                "SELECT id FROM beneficiaries WHERE name = ? AND user_telegram_id IS NULL",
                (anonymous_user_name,)
            )
            
            if result:
                return result[0]
            
            # Create anonymous beneficiary (async)
            current_timestamp = self._get_current_local_timestamp()
            await asyncio.to_thread(
                self.db_manager.execute_query,
                """INSERT INTO beneficiaries 
                   (user_telegram_id, name, sex, phone, residence_status, 
                    governorate, directorate, village_area, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (None, anonymous_user_name, "", "", "", "", "", "", 
                 current_timestamp, current_timestamp)
            )
            
            # Get the newly created beneficiary ID (async)
            result = await asyncio.to_thread(
                self.db_manager.fetch_one,
                "SELECT id FROM beneficiaries WHERE name = ? AND created_at = ?",
                (anonymous_user_name, current_timestamp)
            )
            
            if result:
                self.logger.info("Created anonymous beneficiary for suggestions/feedback")
                return result[0]
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error creating anonymous beneficiary: {e}")
            return None
    
    async def _log_complaint(self, data: ComplaintData) -> Optional[str]:
        """
        Log complaint to database with full processing.
        Handles both full complaints and simple suggestions/feedback.
        
        Args:
            data: ComplaintData object with complaint information
            
        Returns:
            str: The generated reference ID if successful, None otherwise
        """
        try:
            # Determine beneficiary ID based on available data
            beneficiary_id = None
            
            if self._has_minimal_profile_data(data):
                # Save/update full beneficiary profile
                profile_saved = await self._save_beneficiary_profile(data)
                if profile_saved:
                    beneficiary_result = await asyncio.to_thread(
                        self.db_manager.fetch_one,
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
                    return None
            
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
            
            # Insert complaint into database (without reference_id initially) (async)
            await asyncio.to_thread(
                self.db_manager.execute_query,
                """INSERT INTO complaints 
                   (beneficiary_id, original_complaint_text, complaint_summary_en, 
                    complaint_type, complaint_category, complaint_sensitivity, is_critical, status, 
                    source_channel, submitted_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (beneficiary_id, data.original_complaint_text, data.complaint_details,
                 complaint_type, complaint_category, complaint_sensitivity, data.is_critical, "PENDING",
                 "TELEGRAM", submitted_at, current_timestamp, current_timestamp)
            )
            
            # Get the auto-incremented ID (async)
            numeric_id_result = await asyncio.to_thread(
                self.db_manager.fetch_one, 
                "SELECT last_insert_rowid()"
            )
            if not numeric_id_result:
                self.logger.error("Failed to retrieve new complaint ID after insertion")
                return None
            numeric_id = numeric_id_result[0]
            
            # Generate the reference ID
            prefix = self.config.application_settings.complaint_id_prefix
            reference_id = f"{prefix}-{numeric_id}" if prefix else str(numeric_id)
            
            # Save the reference ID back to the database (async)
            await asyncio.to_thread(
                self.db_manager.execute_query,
                "UPDATE complaints SET reference_id = ? WHERE id = ?",
                (reference_id, numeric_id)
            )
            
            # Send critical complaint notification if needed
            if data.is_critical and self.email_service:
                notification_email = self.config.critical_complaint_config.notification_email
                await self.email_service.send_critical_complaint_email(data, notification_email)
            
            self.logger.info(f"Complaint logged for user {data.user_id} with reference ID: {reference_id}")
            return reference_id
            
        except Exception as e:
            self.logger.error(f"Error logging complaint: {e}")
            return None
    
    async def get_user_previous_complaints_summary(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get summary of user's previous complaints from database.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of dictionaries containing complaint summaries
        """
        try:
            # Query to join complaints with beneficiaries table (async)
            query = """
            SELECT c.id, c.complaint_summary_en, c.submitted_at, c.status
            FROM complaints c
            JOIN beneficiaries b ON c.beneficiary_id = b.id
            WHERE b.user_telegram_id = ?
            ORDER BY c.submitted_at DESC
            """
            
            complaints = await asyncio.to_thread(
                self.db_manager.fetch_all,
                query,
                (user_id,)
            )
            
            # Convert to list of dictionaries
            result = []
            for complaint in complaints:
                result.append({
                    'id': complaint[0],
                    'summary': complaint[1] or "No summary available",
                    'date': complaint[2],
                    'status': complaint[3] or "UNKNOWN"
                })
            
            self.logger.info(f"Retrieved {len(result)} previous complaints for user {user_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error fetching previous complaints for user {user_id}: {e}")
            return []
    
    async def log_complaint_reminder_note(
        self, 
        user_id: int, 
        original_complaint_id: int, 
        retrieved_complaint_details: Dict[str, str]
    ) -> bool:
        """
        Log a note about complaint reminder interaction.
        
        Args:
            user_id: Telegram user ID
            original_complaint_id: ID of the original complaint being referenced
            retrieved_complaint_details: Details retrieved about the complaint
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            note_text = f"User requested a reminder for this complaint. Original details: {retrieved_complaint_details.get('summary', 'No summary available')}"
            created_by = f"USER:{user_id}"
            
            success = await asyncio.to_thread(
                self.db_manager.add_complaint_note,
                complaint_id=original_complaint_id,
                note_text=note_text,
                created_by=created_by
            )
            
            if success:
                self.logger.info(f"Logged reminder note for complaint {original_complaint_id} by user {user_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error logging complaint reminder note: {e}")
            return False
    
    def is_admin(self, user_id: int) -> bool:
        """
        Check if a user is an authorized administrator.
        
        Args:
            user_id: Telegram user ID to check
            
        Returns:
            bool: True if user is admin, False otherwise
        """
        try:
            admin_ids = self.config.admin_settings.admin_user_ids
            return user_id in admin_ids
        except Exception as e:
            self.logger.error(f"Error checking admin status for user {user_id}: {e}")
            return False
    
    async def get_complaint_statistics(self) -> Dict[str, Any]:
        """
        Retrieve and compile key complaint statistics from the database.
        
        Returns:
            Dictionary containing complaint statistics with structure:
            {
                'total_complaints': int,
                'critical_complaints': int,
                'status_counts': Dict[str, int]
            }
        """
        try:
            stats = {
                'total_complaints': 0,
                'critical_complaints': 0,
                'status_counts': {}
            }
            
            # Get total complaints count (async)
            total_result = await asyncio.to_thread(
                self.db_manager.fetch_one,
                "SELECT COUNT(*) FROM complaints"
            )
            if total_result:
                stats['total_complaints'] = total_result[0]
            
            # Get critical complaints count (async)
            critical_result = await asyncio.to_thread(
                self.db_manager.fetch_one,
                "SELECT COUNT(*) FROM complaints WHERE is_critical = 1"
            )
            if critical_result:
                stats['critical_complaints'] = critical_result[0]
            
            # Get status counts (async)
            status_results = await asyncio.to_thread(
                self.db_manager.fetch_all,
                "SELECT status, COUNT(*) FROM complaints GROUP BY status"
            )
            for status, count in status_results:
                stats['status_counts'][status] = count
            
            self.logger.info("Successfully retrieved complaint statistics")
            return stats
            
        except Exception as e:
            self.logger.error(f"Error retrieving complaint statistics: {e}")
            return {
                'total_complaints': 0,
                'critical_complaints': 0,
                'status_counts': {}
            }
