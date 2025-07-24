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

LATEST REFACTOR: Implemented multi-stage AI workflow with new analysis methods and streamlined complaint processing.

ENHANCED: Updated JSON parsing with regex-based fallback for robust AI response handling.
"""

import os
import logging
import asyncio
import json
import re
import io
import csv
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
    ENHANCED: Robust JSON parsing with regex-based fallback for AI responses.
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
        
        self.author_info = None
        if not self._verify_integrity_and_load_author_info():
            self.logger.critical("CRITICAL: Application integrity check failed. "
            "The license key is missing, invalid, or has been tampered with. Shutting down."
            )
            raise SystemExit("Integrity Check Failed: Application license is invalid.")
        self.logger.info(f"Application integrity check passed. Copyright held by: {self.author_info.get('author', 'Developer')}"
        )
    def _verify_integrity_and_load_author_info(self) -> bool:
        """
        Verifies the integrity of the application's license key and decodes it.
        
        This crucial method checks for the presence and validity of the base64 encoded
        license key in the configuration. If successful, it decodes the author
        information and stores it in `self.author_info`.
        
        Returns:
            bool: True on successful verification and decoding, False otherwise.
        """
        import base64
        try:
            license_key = self.config.application_meta.license_key
            if not license_key:
                self.logger.error("Integrity Check Failed: license_key is missing from config.")
                return False
            decoded_bytes = base64.b64decode(license_key)
            decoded_str = decoded_bytes.decode('utf-8')
            author_data = json.loads(decoded_str)
            if 'author' in author_data and 'contact' in author_data:
                self.author_info = author_data
                return True
            else:
                self.logger.error("Integrity Check Failed: Decoded license key is missing required fields ('author', 'contact').")
                return False
        except (AttributeError, KeyError):
            self.logger.error("Integrity Check Failed: 'application_meta' or 'license_key' not found in the configuration.")
            return False
        except (base64.binascii.Error, UnicodeDecodeError):
            self.logger.error("Integrity Check Failed: license_key is not a valid base64 encoded string.")
            return False
        except json.JSONDecodeError:
            self.logger.error("Integrity Check Failed: Decoded license key is not valid JSON.")
            return False
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during integrity check: {e}")
            return False
    
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
    
    async def generate_export_file(self, export_type: str) -> Tuple[Optional[io.BytesIO], Optional[str]]:
        """
        Generate an in-memory CSV file for the requested export type.
        
        Args:
            export_type: Type of data to export ('complaints', 'beneficiaries', or 'notes')
            
        Returns:
            Tuple containing:
            - io.BytesIO: In-memory file object containing the CSV data
            - str: Suggested filename for the export
            Or (None, None) if no data or error occurred
        """
        try:
            # Define export type mappings
            if export_type == 'complaints':
                headers = [
                    'ID', 'Reference ID', 'Beneficiary Name', 'Beneficiary Phone', 'Governorate', 
                    'Directorate', 'Village/Area', 'Original Complaint Text', 'Complaint Summary (EN)',
                    'Complaint Type', 'Complaint Category', 'Complaint Sensitivity', 'Is Critical', 
                    'Status', 'Assigned To', 'Resolution Notes', 'Created At', 'Submitted At', 
                    'Updated At', 'Resolved At', 'Source Channel', 'Internal Notes', 'Follow-up Required'
                ]
                data = await asyncio.to_thread(self.db_manager.get_complaints_export_data)
                
            elif export_type == 'beneficiaries':
                headers = [
                    'ID', 'User Telegram ID', 'Name', 'Sex', 'Phone', 'Residence Status', 
                    'Governorate', 'Directorate', 'Village/Area', 'Last Seen At', 'Created At', 'Updated At'
                ]
                data = await asyncio.to_thread(self.db_manager.get_beneficiaries_export_data)
                
            elif export_type == 'notes':
                headers = [
                    'ID', 'Complaint ID', 'Complaint Reference ID', 'Note Text', 'Created By', 'Created At'
                ]
                data = await asyncio.to_thread(self.db_manager.get_notes_export_data)
                
            else:
                self.logger.error(f"Invalid export type requested: {export_type}")
                return None, None
            
            # Check if we have data to export
            if not data:
                self.logger.info(f"No data available for export type: {export_type}")
                return None, None
            
            # Create in-memory text buffer and CSV writer
            with io.StringIO() as text_buffer:
                writer = csv.writer(text_buffer)
                
                # Write header row
                writer.writerow(headers)
                
                # Write all data rows
                writer.writerows(data)
                
                # Get CSV content as string
                csv_content = text_buffer.getvalue()
            
            # Convert to bytes and create in-memory binary buffer
            bytes_buffer = io.BytesIO(csv_content.encode('utf-8-sig'))
            
            # Generate filename with timestamp
            filename = f"{export_type}_export_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
            
            self.logger.info(f"Successfully generated {export_type} export file with {len(data)} records")
            return bytes_buffer, filename
            
        except Exception as e:
            self.logger.error(f"Error generating {export_type} export file: {e}")
            return None, None
    
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
    ) -> Tuple[str, str, bool]:
        """
        Analyze initial user message using LLMOrchestrator.
        
        Args:
            user_input_text: The user's message text
            user_first_name: User's first name from Telegram
            
        Returns:
            Tuple[str, str]: (signal, llm_response_text)
        """
        try:
            self.logger.info(f"Starting analysis of first contact message for user: {user_first_name}")
            
            # Call LLMOrchestrator for analysis (modified to expect exactly two return values)
            signal, llm_response_text, is_critical = await self.llm_orchestrator.analyze_initial_message(
                user_input_text=user_input_text,
                user_first_name=user_first_name,
                institution_name=self.config.institution.name_en,
                current_date_time=self._get_current_local_timestamp()
            )
            
            self.logger.info(f"Analysis completed with signal: {signal}, is_critical: {is_critical}")
            return signal, llm_response_text, is_critical
            
        except Exception as e:
            self.logger.error(f"Error in analyze_first_contact_message: {e}")
            return "CLARIFICATION_NEEDED", "I'm sorry, I encountered an issue processing your message. Could you please try again?", False
    
    async def is_name_valid(self, question_asked: str, user_answer: str) -> bool:
        """
        Validate if user's answer is relevant to the question asked.
        Enhanced with robust JSON parsing.
        
        Args:
            question_asked: The question that was asked
            user_answer: The user's response
            
        Returns:
            bool: True if answer is valid/relevant, False otherwise
        """
        try:
            # الخطوة 1: قم بإنشاء القالب الصحيح باستخدام PromptBuilder
            prompt = await self.prompt_builder.generate_input_validation_prompt(question_asked, user_answer)
            
            # الخطوة 2: أرسل هذا القالب الصحيح إلى الذكاء الاصطناعي
            response = await self.ai_handler.generate_response(user_message="", system_prompt=prompt)
            
            # الخطوة 3: (تبقى كما هي) عالج الإجابة
            try:
                result = json.loads(response.strip())
                return result.get("is_relevant", True)
            except json.JSONDecodeError:
                self.logger.warning("Direct JSON parsing failed in is_name_valid. Searching for embedded JSON.")
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    json_part = match.group(0)
                    try:
                        result = json.loads(json_part)
                        return result.get("is_relevant", True)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Failed to parse extracted JSON in is_name_valid: {e}")
                        self.logger.debug(f"Extracted part was: {json_part}")
                        return True
                else:
                    self.logger.error(f"No JSON object found in is_name_valid response: {response}")
                    return True
                
        except Exception as e:
            self.logger.error(f"Error in is_name_valid: {e}")
            return True
    
    async def perform_final_complaint_analysis(self, complaint_text: str) -> Dict:
        """
        Perform final AI-driven analysis of complaint text.
        Enhanced with robust JSON parsing with regex-based fallback.
        
        Args:
            complaint_text: The complaint text to analyze
            
        Returns:
            Dict: Analysis results with complaint categorization and metadata
        """
        try:
            # Generate final analysis prompt (synchronous call)
            prompt = self.prompt_builder.generate_final_analysis_prompt(complaint_text)
            
            # Get AI response
            response = await self.ai_handler.generate_response(user_message="", system_prompt=prompt)
            
            # Enhanced JSON parsing with fallback mechanism
            try:
                # First, attempt to parse the entire stripped string directly
                return json.loads(response.strip())
            except json.JSONDecodeError:
                # If direct parsing fails, search for an embedded JSON object
                self.logger.warning("Direct JSON parsing failed in final analysis. Searching for embedded JSON.")
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    json_part = match.group(0)
                    try:
                        # Attempt to parse the extracted JSON part
                        return json.loads(json_part)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Failed to parse extracted JSON in final analysis: {e}")
                        self.logger.debug(f"Extracted part was: {json_part}")
                        return self._get_default_analysis_results()
                else:
                    self.logger.error(f"No JSON object found in final analysis response: {response}")
                    return self._get_default_analysis_results()
                
        except Exception as e:
            self.logger.error(f"Error in perform_final_complaint_analysis: {e}")
            return self._get_default_analysis_results()
    
    def _get_default_analysis_results(self) -> Dict:
        """
        Get default analysis results when AI analysis fails.
        
        Returns:
            Dict: Default analysis values
        """
        return {
            'complaint_category': 'General',
            'sector': 'Unclassified',
            'sensitivity': 'Normal',
            'content_assessment': 'Review Required',
            'summary': 'AI summary unavailable',
            'is_critical': False,
            'complaint_type': 'User Complaint'
        }
    
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
        Log complaint to database with full processing using new AI workflow.
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
            
            # Step 1: Perform final complaint analysis using new AI workflow
            analysis_results = await self.perform_final_complaint_analysis(data.original_complaint_text)
            
            # Handle timestamps with improved processing
            current_timestamp = self._get_current_local_timestamp()
            submitted_at = self._process_telegram_message_timestamp(data.telegram_message_date)
            
            # Step 3: Insert complaint into database using analysis results
            await asyncio.to_thread(
                self.db_manager.execute_query,
                """INSERT INTO complaints (
                    beneficiary_id, reference_id,
                    -- Submitter Profile Snapshot
                    submitter_name, submitter_sex, submitter_age, submitter_nationality,
                    submitter_phone, submitter_email, submitter_residence_status,
                    submitter_governorate, submitter_directorate, submitter_village,
                    submitter_disability,
                    -- Complaint & AI Analysis Data
                    sector, original_complaint_text, complaint_summary_en,
                    complaint_type, complaint_category, complaint_sensitivity,
                    is_critical, status, source_channel,
                    -- Timestamps
                    submitted_at, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    beneficiary_id,
                    "TBD",  # Placeholder, will be updated later
                    # Submitter Profile Snapshot Values
                    data.name,
                    data.sex,
                    data.age,
                    data.nationality,
                    data.phone,
                    data.email,
                    data.residence_status,
                    data.governorate,
                    data.directorate,
                    data.village,
                    data.disability,
                    # Complaint & AI Analysis Values
                    analysis_results.get('sector', ''), # Assuming AI might provide a 'sector'
                    data.original_complaint_text,
                    analysis_results.get('summary', ''),
                    analysis_results.get('complaint_type', 'User Complaint'),
                    analysis_results.get('complaint_category', 'General'),
                    analysis_results.get('sensitivity', 'Normal'),
                    int(analysis_results.get('is_critical', False)),
                    "PENDING",
                    "TELEGRAM",
                    # Timestamp Values
                    submitted_at,
                    current_timestamp,
                    current_timestamp
                )
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
            
            # Step 4: Send critical complaint notification using is_critical flag from analysis
            if analysis_results.get('is_critical', False) and self.email_service:
                notification_email = self.config.critical_complaint_config.notification_email
                await self.email_service.send_critical_complaint_email(data, notification_email, analysis_results)
            
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
