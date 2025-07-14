"""
AI Gate for Artificial Intelligence Applications
Configuration models for the Institution Complaint Management Bot.

This module defines Pydantic models that provide type safety and validation
for the application's configuration structure, including both YAML-based
settings and environment variable secrets.
"""

from typing import Dict, List, Any, Optional
from os import getenv
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


# ==================================================================================
# Shared Data Transfer Objects (DTOs)
# ==================================================================================

class ComplaintData(BaseModel):
    """
    A shared data transfer object for holding complaint information.
    
    This model serves as the primary DTO for complaint data across the application,
    providing type safety and validation for all complaint-related operations.
    """
    user_id: int = Field(..., description="Telegram user ID of the complainant")
    name: str = Field(default="", description="Full name of the complainant")
    sex: str = Field(default="", description="Gender/sex of the complainant")
    phone: str = Field(default="", description="Phone number of the complainant")
    email: Optional[EmailStr] = Field(default=None, description="Email address of the complainant")
    department: str = Field(default="", description="Department related to the complaint")
    position: str = Field(default="", description="Position/job title of the complainant")
    complaint_type: str = Field(default="", description="Type/category of the complaint")
    complaint_category: str = Field(default="", description="AI-classified complaint category")
    residence_status: str = Field(default="", description="Residence status of the complainant")
    governorate: str = Field(default="", description="Governorate of the complainant")
    directorate: str = Field(default="", description="Directorate of the complainant")
    village: str = Field(default="", description="Village of the complainant")
    original_complaint_text: str = Field(default="", description="Original complaint text in Arabic")
    complaint_details: str = Field(default="", description="Processed complaint details/summary in English")
    is_critical: bool = Field(default=False, description="Whether the complaint is flagged as critical")
    telegram_message_date: Optional[datetime] = Field(default=None, description="Date and time of the original Telegram message")
    complaint_id: Optional[int] = Field(default=None, description="Unique complaint identifier")
    submission_time: Optional[str] = Field(default=None, description="Formatted submission timestamp")
    sensitivity_score: Optional[str] = Field(default=None, description="AI-calculated sensitivity level (e.g., 'Normal', 'High')")
    
    class Config:
        """Pydantic configuration for the ComplaintData model."""
        arbitrary_types_allowed = True  # Allows datetime objects
        validate_assignment = True  # Validates assignments to model fields


# ==================================================================================
# Environment Variable Models (BaseSettings)
# ==================================================================================

class ApiKeys(BaseSettings):
    """
    Model for loading external API keys and tokens from environment variables.
    
    This model automatically loads sensitive API credentials from the .env file,
    keeping them separate from the YAML configuration for security.
    """
    telegram_bot_token: str = Field(..., description="Telegram bot API token")
    openrouter_api_key: str = Field(..., description="OpenRouter API key for AI models")
    hf_api_token: str = Field(..., description="Hugging Face API token")
    
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')


# ==================================================================================
# YAML Structure Models (BaseModel)
# ==================================================================================

class InstitutionContactModel(BaseModel):
    """Model for institution contact information."""
    phone: str = Field(..., description="Institution contact phone number")
    email: EmailStr = Field(..., description="Institution contact email")
    address: str = Field(..., description="Institution address in Arabic")
    address_en: str = Field(..., description="Institution address in English")


class InstitutionModel(BaseModel):
    """Model for top-level institution configuration."""
    name: str = Field(..., description="Institution name in Arabic")
    name_en: str = Field(..., description="Institution name in English")
    contact: InstitutionContactModel = Field(..., description="Institution contact details")
    description: str = Field(..., description="Institution description")
    website: HttpUrl = Field(..., description="Institution website URL")
    timezone: str = Field(default="Asia/Aden", description="Institution timezone")


class DataCollectionFields(BaseModel):
    """Model for configuring which data fields are collected during complaint submission."""
    sex: bool = Field(default=True, description="Collect sex/gender information")
    phone: bool = Field(default=True, description="Collect phone number")
    email: bool = Field(default=True, description="Collect email address")
    department: bool = Field(default=True, description="Collect department information")
    position: bool = Field(default=True, description="Collect position/job title")
    complaint_type: bool = Field(default=True, description="Collect complaint type/category")
    residence_status: bool = Field(default=True, description="Collect residence status")
    governorate: bool = Field(default=True, description="Collect governorate information")
    directorate: bool = Field(default=True, description="Collect directorate information")
    village: bool = Field(default=True, description="Collect village information")


class SelectionOptionsModel(BaseModel):
    """Model for dynamic UI selection options in both Arabic and English."""
    residence_status_ar: List[str] = Field(
        default_factory=list, 
        description="List of residence status options in Arabic"
    )
    residence_status_en: List[str] = Field(
        default_factory=list, 
        description="List of residence status options in English"
    )
    governorates_ar: List[str] = Field(
        default_factory=list, 
        description="List of governorate options in Arabic"
    )
    governorates_en: List[str] = Field(
        default_factory=list, 
        description="List of governorate options in English"
    )


class ValidationSettings(BaseModel):
    """Model for input validation rules and patterns."""
    phone_patterns: List[str] = Field(default_factory=list, description="Regex patterns for phone validation")
    min_name_words: int = Field(default=2, description="Minimum words required for full name")
    min_suggestion_length: int = Field(default=15, description="Minimum length for suggestions/complaints")
    max_input_length: int = Field(default=2000, description="Maximum length for user inputs")
    max_title_length: int = Field(default=200, description="Maximum length for complaint titles")
    min_age: int = Field(default=16, description="Minimum age for complaint submission")


class FlowControlSettings(BaseModel):
    """Model for conversation flow and UI behavior settings."""
    summary_preview_length: int = Field(default=300, description="Max chars in complaint summary preview")
    snippet_preview_length: int = Field(default=100, description="Max chars in complaint snippets")
    max_recent_complaints: int = Field(default=10, description="Number of recent complaints to show")
    user_input_timeout: int = Field(default=300, description="User input timeout in seconds")
    max_retry_attempts: int = Field(default=3, description="Max retry attempts for failed operations")


class PlaceholderSettings(BaseModel):
    """Model for default placeholder texts used throughout the application."""
    anonymous_user_name: str = Field(default="Anonymous User", description="Default name for anonymous users")
    default_complaint_title: str = Field(default="General Inquiry", description="Default complaint title")
    default_category: str = Field(default="General", description="Default complaint category")
    empty_description_placeholder: str = Field(default="No description provided", description="Placeholder for empty descriptions")
    default_contact_method: str = Field(default="phone", description="Default contact method")


class BusinessRules(BaseModel):
    """Model for business logic constants and rules."""
    auto_escalation_days: int = Field(default=7, description="Days before automatic complaint escalation")
    auto_resolution_days: int = Field(default=30, description="Days before automatic complaint resolution")
    supervisor_approval_threshold: int = Field(default=8, description="Sensitivity threshold requiring supervisor approval")
    followup_reminder_days: int = Field(default=3, description="Days before follow-up reminder")


class ApplicationSettingsModel(BaseModel):
    """Model for main application settings and behavior rules."""
    data_collection_fields: DataCollectionFields = Field(default_factory=DataCollectionFields, description="Configuration for which data fields are collected during complaint submission")
    selection_options: SelectionOptionsModel = Field(default_factory=SelectionOptionsModel, description="Dynamic UI selection options for dropdowns and buttons")
    validation: ValidationSettings = Field(default_factory=ValidationSettings, description="Input validation settings")
    flow_control: FlowControlSettings = Field(default_factory=FlowControlSettings, description="Flow control settings")
    placeholders: PlaceholderSettings = Field(default_factory=PlaceholderSettings, description="Placeholder text settings")
    complaint_id_prefix: Optional[str] = Field(default=None, description="An optional prefix for generating custom complaint reference IDs.")
    ai_fallback_responses: List[str] = Field(default_factory=list, description="Fallback responses when AI is unavailable")
    business_rules: BusinessRules = Field(default_factory=BusinessRules, description="Business logic rules")


class AdminSettings(BaseModel):
    """Model for administrator configuration settings."""
    admin_user_ids: List[int] = Field(
        default_factory=list,
        description="A list of Telegram user IDs for authorized administrators."
    )


class SeverityLevel(BaseModel):
    """Model for complaint severity level configuration."""
    score: str = Field(..., description="Score range for this severity level")
    description: str = Field(..., description="Description of this severity level")


class CriticalComplaintConfigModel(BaseModel):
    """Model for critical complaint identification and handling configuration."""
    notification_email: str = Field(..., description="Email addresses for critical complaint notifications")
    sms_notification_enabled: bool = Field(default=False, description="Whether SMS notifications are enabled")
    sms_notification_number: Optional[str] = Field(default=None, description="SMS notification phone number")
    identification_criteria: List[str] = Field(default_factory=list, description="Criteria for identifying critical complaints")
    severity_levels: Dict[str, SeverityLevel] = Field(default_factory=dict, description="Severity level definitions")


class EmailTemplates(BaseModel):
    """Model for email template configuration."""
    critical_subject: str = Field(..., description="Subject line for critical complaint emails")
    regular_subject: str = Field(..., description="Subject line for regular complaint emails") 
    sender_name: str = Field(..., description="Display name for email sender")


class EmailBehavior(BaseModel):
    """Model for email sending behavior settings."""
    max_retries: int = Field(default=3, description="Maximum retry attempts for failed email sends")
    retry_delay: int = Field(default=5, description="Delay between retry attempts in seconds")
    timeout: int = Field(default=30, description="Timeout for SMTP operations in seconds")


class EmailConfigModel(BaseModel):
    """
    Model for email configuration that combines YAML settings with environment credentials.
    It reads non-sensitive settings from YAML and fetches sensitive credentials directly
    from environment variables using os.getenv.
    """
    smtp_server: str = Field(..., description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP server port")
    use_tls: bool = Field(default=True, description="Whether to use TLS encryption")
    use_ssl: bool = Field(default=False, description="Whether to use SSL encryption")
    templates: EmailTemplates = Field(..., description="Email template settings")
    behavior: EmailBehavior = Field(default_factory=EmailBehavior, description="Email behavior settings")
    
    # These fields are now read directly from the environment when the model is initialized
    sender_email: Optional[EmailStr] = Field(default_factory=lambda: getenv('SMTP_EMAIL'))
    sender_password: Optional[str] = Field(default_factory=lambda: getenv('SMTP_PASSWORD'))


class HuggingFaceProviderModel(BaseModel):
    """Model for Hugging Face AI provider configuration."""
    api_key_env_var: str = Field(default="HF_API_TOKEN", description="Environment variable name for HF API key")
    primary_model_hf: str = Field(..., description="Primary Hugging Face model name")
    base_url_hf: HttpUrl = Field(..., description="Hugging Face API base URL")


class AiModelsModel(BaseModel):
    """Model for AI models and API configuration."""
    primary_model: str = Field(..., description="Primary AI model identifier")
    fallback_models: List[str] = Field(default_factory=list, description="Fallback AI models")
    base_url: HttpUrl = Field(..., description="AI API base URL")
    timeout: int = Field(default=60, description="API timeout in seconds")
    max_tokens: int = Field(default=2500, description="Maximum tokens for AI responses")
    temperature: float = Field(default=0.3, description="AI response temperature")
    direct_fallback_enabled: bool = Field(default=True, description="Whether direct fallback is enabled")
    stream_responses: bool = Field(default=False, description="Whether to stream AI responses")
    huggingface_direct_provider: HuggingFaceProviderModel = Field(..., description="Hugging Face provider settings")


class ConversationPrompts(BaseModel):
    """Model for conversation flow prompts."""
    initial_greeting: str = Field(..., description="Initial greeting message")
    collect_details: str = Field(..., description="Message for collecting complaint details")
    confirm_submission: str = Field(..., description="Message for confirming complaint submission")
    completion_message: str = Field(..., description="Completion message after submission")


class PromptsModel(BaseModel):
    """
    Model for AI prompts and behavior configuration.
    
    REFACTORED FOR MULTI-PROMPT ARCHITECTURE:
    - Removed obsolete system_template_file field
    - Added three specialized prompt template fields for the new architecture:
      * initial_analysis_template: For initial complaint analysis
      * final_analysis_template: For final complaint processing
      * input_validation_template: For input validation tasks
    """
    # NEW: Three specialized prompt templates for multi-prompt architecture
    initial_analysis_template: str = Field(..., description="Path to the initial analysis template file (e.g., initial_analysis_prompt.txt)")
    final_analysis_template: str = Field(..., description="Path to the final analysis template file (e.g., final_analysis_prompt.txt)")
    input_validation_template: str = Field(..., description="Path to the input validation template file (e.g., input_validation_prompt.txt)")
    
    # Existing fields remain unchanged
    language_instructions: Dict[str, str] = Field(default_factory=dict, description="Language-specific AI instructions")
    default_output_formats: Dict[str, str] = Field(default_factory=dict, description="Default JSON output formats for AI tasks")
    conversation_prompts: ConversationPrompts = Field(..., description="Conversation flow prompts")


class CacheCategoryModel(BaseModel):
    """Model for cache category-specific settings."""
    ttl: int = Field(..., description="Time-to-live for this cache category in seconds")
    persistent: bool = Field(default=False, description="Whether to persist cache to disk")
    compress: bool = Field(default=False, description="Whether to compress cached data")


class CacheModel(BaseModel):
    """Model for application caching configuration."""
    enabled: bool = Field(default=True, description="Whether caching is enabled")
    cache_dir: str = Field(default="app_cache", description="Directory for cache files")
    max_size: int = Field(default=1000, description="Maximum number of cached items")
    ttl: int = Field(default=3600, description="Default time-to-live in seconds")
    cleanup_interval: int = Field(default=300, description="Cache cleanup frequency in seconds")
    categories: Dict[str, CacheCategoryModel] = Field(default_factory=dict, description="Category-specific cache settings")


class LoggingModel(BaseModel):
    """Model for logging configuration."""
    level: str = Field(default="INFO", description="Global log level")
    log_file_path: str = Field(..., description="Path to log file")
    max_file_size_mb: int = Field(default=10, description="Maximum log file size in MB")
    backup_count: int = Field(default=5, description="Number of backup log files to keep")
    console_output: bool = Field(default=True, description="Whether to output logs to console")
    console_level: str = Field(default="INFO", description="Console log level")
    format: str = Field(..., description="Log message format")
    date_format: str = Field(default="%Y-%m-%d %H:%M:%S", description="Log date format")
    component_levels: Dict[str, str] = Field(default_factory=dict, description="Component-specific log levels")
    mask_sensitive_data: bool = Field(default=True, description="Whether to mask sensitive data in logs")
    sensitive_fields: List[str] = Field(default_factory=list, description="List of sensitive field names to mask")

class ComplaintCategoryModel(BaseModel):
    """Model for a single complaint category with its description."""
    name: str = Field(..., description="The name of the complaint category.")
    description: str = Field(..., description="A brief description of what this category covers.")

class AnalysisSettingsModel(BaseModel):
    """Model for analysis settings configuration."""
    complaint_categories: List[ComplaintCategoryModel] = Field(default_factory=list, description="List of complaint categories with their descriptions for analysis.")
    sensitivity_levels: List[str] = Field(default_factory=list, description="List of sensitivity levels for analysis")


# ==================================================================================
# Top-Level Root Model (AppConfig)  
# ==================================================================================

class AppConfig(BaseModel):
    """
    Main application configuration model that aggregates all other models.
    
    This is the single source of truth for the application's configuration,
    providing type safety and validation for both YAML-based settings and
    environment variable secrets.
    """
    # Core configuration sections from YAML
    institution: InstitutionModel = Field(..., description="Institution information and contact details")
    application_settings: ApplicationSettingsModel = Field(..., description="Main application settings and behavior rules")
    admin_settings: AdminSettings = Field(default_factory=AdminSettings, description="Administrator configuration settings")
    critical_complaint_config: CriticalComplaintConfigModel = Field(..., description="Critical complaint handling configuration")
    ai_models: AiModelsModel = Field(..., description="AI models and API configuration")
    prompts: PromptsModel = Field(..., description="AI prompts and behavior configuration")
    cache: CacheModel = Field(default_factory=CacheModel, description="Caching configuration")
    logging: LoggingModel = Field(..., description="Logging configuration")
    email_config: EmailConfigModel = Field(..., description="Email configuration with integrated credentials")
    analysis_settings: AnalysisSettingsModel = Field(default_factory=AnalysisSettingsModel, description="Analysis settings configuration")
    
    # Flexible sections for less critical configuration
    database: Dict[str, Any] = Field(default_factory=dict, description="Database configuration")
    security: Dict[str, Any] = Field(default_factory=dict, description="Security configuration")
    monitoring: Dict[str, Any] = Field(default_factory=dict, description="Monitoring and alerts configuration")
    
    # Environment-based secrets
    api_keys: ApiKeys = Field(default_factory=ApiKeys, description="API keys and tokens from environment variables")
    
    class Config:
        """Pydantic configuration for immutability and validation."""
        frozen = False  # The model is subject to change after initialization.
        validate_assignment = True  # Validates assignments to model fields
        extra = 'forbid'  # Forbids extra fields not defined in the model


# ==================================================================================
# Utility Functions (Optional)
# ==================================================================================

def load_config_from_yaml(yaml_file_path: str) -> AppConfig:
    """
    Load and validate configuration from a YAML file.
    
    Args:
        yaml_file_path: Path to the YAML configuration file
        
    Returns:
        Validated AppConfig instance
        
    Raises:
        ValidationError: If the configuration doesn't match the expected schema
        FileNotFoundError: If the YAML file doesn't exist
    """
    import yaml
    
    with open(yaml_file_path, 'r', encoding='utf-8') as file:
        yaml_data = yaml.safe_load(file)
    
    return AppConfig(**yaml_data)


def get_config_schema() -> Dict[str, Any]:
    """
    Get the JSON schema for the configuration model.
    
    Returns:
        JSON schema dictionary that can be used for validation or documentation
    """
    return AppConfig.model_json_schema()