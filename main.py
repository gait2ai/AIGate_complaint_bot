#!/usr/bin/env python3
"""
AI Gate for Artificial Intelligence Applications

Institution Complaint Management Bot - Main Application Orchestrator

This module serves as the central orchestrator for the Institution Complaint Management Bot.
Its primary responsibilities include:
- Loading configurations from the updated config.yaml structure with Pydantic validation
- Initializing all core service modules (DatabaseManager, CacheManager, PromptBuilder, AIHandler)
- Instantiating the main InstitutionBot logic with comprehensive AppConfig integration
- Registering all Telegram handlers via the centralized handler registration system
- Managing the application's lifecycle, including graceful startup and shutdown procedures

The module follows a clean separation of concerns where main.py orchestrates the setup
and lifecycle management, while the InstitutionBot contains the core application logic.
Handler registration is now centralized through the register_all_handlers function.

REFACTORING CHANGES:
- Integrated Pydantic AppConfig model throughout the initialization process
- Replaced dictionary-style config access with attribute-style access
- Updated initialization functions to pass correct Pydantic sub-models
- Maintained full backward compatibility while improving type safety

Author: Generated for Institution Complaint Management
License: Proprietary
"""

import os
import sys
import asyncio
import logging
import signal
from pathlib import Path
from typing import Optional

import yaml
from yaml.loader import SafeLoader
from telegram.ext import PicklePersistence  # Added for conversation persistence
from dotenv import load_dotenv
import pydantic

# Import Pydantic configuration model
from app.config.config_model import AppConfig

# Import core modules
from app.core.ai_handler import AIHandler
from app.core.cache_manager import CacheManager
from app.core.prompt_builder import PromptBuilder
from app.core.database_manager import DatabaseManager
from app.bot.institution_bot_logic import InstitutionBot

# Import centralized handler registration
from app.bot.handlers import register_all_handlers


# Global variables for cleanup
ai_handler_instance: Optional[AIHandler] = None
cache_manager_instance: Optional[CacheManager] = None
institution_bot_instance: Optional[InstitutionBot] = None
database_manager_instance: Optional[DatabaseManager] = None


def setup_logging(config: AppConfig) -> None:
    """
    Configure logging based on the AppConfig Pydantic model.
    
    Args:
        config: Validated AppConfig object with type-safe attribute access
    """
    # Access logging configuration via Pydantic model attributes
    logging_config = config.logging
    
    # Create logs directory if it doesn't exist
    log_file_path = logging_config.log_file_path
    log_dir = Path(log_file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure logging level using attribute access
    log_level = getattr(logging, logging_config.level.upper())
    
    # Configure logging format using attribute access
    log_format = logging_config.format
    
    # Setup handlers
    handlers = []
    
    # File handler with rotation
    if log_file_path:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=logging_config.max_file_size_mb * 1024 * 1024,
            backupCount=logging_config.backup_count
        )
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    
    # Console handler
    if logging_config.console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(console_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers
    )
    
    # Set specific logger levels for noisy libraries
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)


def load_configuration() -> AppConfig:
    """
    Load and validate the configuration file with robust error handling using Pydantic.
    
    Returns:
        AppConfig instance containing the validated configuration with type-safe access
        
    Raises:
        SystemExit: If configuration loading or validation fails
    """
    try:
        # Load environment variables first
        load_dotenv()
        
        # Define path to configuration file
        APP_ROOT = Path(__file__).parent.absolute()
        config_path = APP_ROOT / "app" / "config" / "config.yaml"
        
        logging.info(f"Loading configuration from: {config_path}")
        
        if not config_path.exists():
            logging.error(f"Configuration file not found at: {config_path}")
            sys.exit(1)
        
        # Load YAML data
        with open(config_path, 'r', encoding='utf-8') as config_file:
            yaml_data = yaml.load(config_file, Loader=SafeLoader)
            
        if not yaml_data:
            logging.error("Configuration file is empty or invalid")
            sys.exit(1)
        
        # Validate configuration with Pydantic
        config_object = AppConfig(**yaml_data)
        
        logging.info("Configuration loaded and validated successfully with Pydantic")
        return config_object
        
    except pydantic.ValidationError as e:
        logging.error(f"Configuration validation error: {e}")
        logging.error("Please check your config.yaml file and ensure all required fields are present and valid")
        sys.exit(1)
    except FileNotFoundError as e:
        logging.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except yaml.YAMLError as e:
        logging.error(f"YAML parsing error in configuration file: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error loading configuration: {e}")
        sys.exit(1)


async def initialize_database_manager(config: AppConfig) -> DatabaseManager:
    """
    Initialize the DatabaseManager with AppConfig model integration.
    
    Args:
        config: Validated AppConfig object with type-safe attribute access
        
    Returns:
        DatabaseManager instance
        
    Raises:
        SystemExit: If DatabaseManager initialization fails
    """
    try:
        # Define database path using Pydantic model attributes
        APP_ROOT = Path(__file__).parent.absolute()
        db_config = config.database
        
        # Use attribute access for database configuration
        # Note: database is defined as a flexible Dict in the config model
        db_dir = APP_ROOT / db_config.get('directory', 'app/database')
        db_path = db_dir / db_config.get('filename', 'ins_data.db')
        
        # Ensure database directory exists
        db_dir.mkdir(parents=True, exist_ok=True)
        
        logging.info(f"Initializing DatabaseManager with path: {db_path}")
        
        database_manager = DatabaseManager(db_path=str(db_path))
        await asyncio.to_thread(database_manager.connect)
        await asyncio.to_thread(database_manager.create_tables)
        
        logging.info("DatabaseManager initialized successfully")
        return database_manager
        
    except Exception as e:
        logging.error(f"Failed to initialize DatabaseManager: {e}")
        sys.exit(1)


async def initialize_cache_manager(config: AppConfig) -> Optional[CacheManager]:
    """
    Initialize the CacheManager with Pydantic CacheModel integration.
    
    Args:
        config: Validated AppConfig object with type-safe attribute access
        
    Returns:
        CacheManager instance or None if caching is disabled
    """
    # Access cache configuration via Pydantic model attributes
    cache_config = config.cache
    
    if not cache_config.enabled:
        logging.info("Caching is disabled in configuration")
        return None
    
    try:
        # Resolve cache directory relative to project root
        APP_ROOT = Path(__file__).parent.absolute()
        
        # IMPORTANT: We resolve the full path and update the Pydantic model object directly
        # before passing it. This ensures CacheManager receives the absolute path.
        # This is permissible as sub-models are not frozen by default.
        cache_config.cache_dir = str(APP_ROOT / cache_config.cache_dir)
        
        logging.info(f"Initializing CacheManager with directory: {cache_config.cache_dir}")
        
        # THE CORE FIX: Instantiate CacheManager by passing only the config model and the loop.
        # The redundant 'cache_dir' keyword argument has been removed.
        cache_manager = CacheManager(
            config=cache_config,
            loop=asyncio.get_event_loop()
        )
        
        logging.info("CacheManager initialized successfully with Pydantic model")
        return cache_manager
        
    except Exception as e:
        # Improved error logging for better diagnostics
        logging.error(f"Failed to initialize CacheManager: {e}", exc_info=True)
        logging.warning("Continuing without caching support")
        return None


async def initialize_prompt_builder(config: AppConfig) -> PromptBuilder:
    """
    Initialize the PromptBuilder with Pydantic sub-models integration.
    
    Args:
        config: Validated AppConfig object with type-safe attribute access
        
    Returns:
        PromptBuilder instance
        
    Raises:
        SystemExit: If PromptBuilder initialization fails
    """
    try:
        # Define config directory
        APP_ROOT = Path(__file__).parent.absolute()
        config_dir = APP_ROOT / "app" / "config"
        
        # Pass Pydantic sub-models directly instead of converting to dict
        institution_config = config.institution
        prompts_config = config.prompts
        
        logging.info(f"Initializing PromptBuilder with config directory: {config_dir}")
        
        # Check if system prompt template exists using attribute access
        template_file = prompts_config.system_template_file
        template_path = config_dir / template_file
        
        if not template_path.exists():
            logging.error(f"System prompt template not found at: {template_path}")
            sys.exit(1)
        
        # Pass Pydantic models directly to PromptBuilder
        prompt_builder = PromptBuilder(
            config_dir=config_dir,
            institution_config=institution_config,  # Pass InstitutionModel
            prompts_config=prompts_config          # Pass PromptsModel
        )
        
        logging.info("PromptBuilder initialized successfully with Pydantic sub-models")
        return prompt_builder
        
    except Exception as e:
        logging.error(f"Failed to initialize PromptBuilder: {e}")
        sys.exit(1)


async def initialize_ai_handler(config: AppConfig, cache_manager: Optional[CacheManager]) -> AIHandler:
    """
    Initialize the AIHandler with AiModelsModel integration.
    
    Args:
        config: Validated AppConfig object with type-safe attribute access
        cache_manager: CacheManager instance or None
        
    Returns:
        AIHandler instance
        
    Raises:
        SystemExit: If AIHandler initialization fails
    """
    try:
        # Pass the AiModelsModel directly instead of converting to dict
        ai_models_config = config.ai_models
        
        logging.info("Initializing AIHandler with Pydantic AiModelsModel")
        
        # Pass Pydantic model directly to AIHandler
        ai_handler = AIHandler(
            config=ai_models_config,  # Pass AiModelsModel directly
            cache_manager=cache_manager
        )
        
        # Ensure the HTTP session is ready
        await ai_handler._ensure_session()
        
        logging.info("AIHandler initialized successfully with Pydantic model")
        return ai_handler
        
    except Exception as e:
        logging.error(f"Failed to initialize AIHandler: {e}")
        sys.exit(1)


async def initialize_institution_bot(
    config: AppConfig,
    ai_handler: AIHandler,
    cache_manager: Optional[CacheManager],
    prompt_builder: PromptBuilder,
    database_manager: DatabaseManager
) -> InstitutionBot:
    """
    Initialize the InstitutionBot with comprehensive AppConfig integration.
    
    Args:
        config: Validated AppConfig object with type-safe attribute access
        ai_handler: AIHandler instance
        cache_manager: CacheManager instance or None
        prompt_builder: PromptBuilder instance
        database_manager: DatabaseManager instance
        
    Returns:
        InstitutionBot instance
        
    Raises:
        SystemExit: If InstitutionBot initialization fails
    """
    try:
        # Get Telegram bot token from validated AppConfig using attribute access
        telegram_token = config.api_keys.telegram_bot_token
        
        logging.info("Initializing InstitutionBot with comprehensive AppConfig integration")
        
        # Create persistence file path and ensure directory exists
        persistence_file = Path(__file__).parent / "app_cache" / "conversation_persistence.pickle"
        persistence_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize persistence object
        persistence = PicklePersistence(
            filepath=str(persistence_file),
            store_user_data=True,       # Persist user_data for conversation continuity
            store_chat_data=False,      # We don't use chat_data
            store_bot_data=False        # We re-initialize bot_data on each start
        )
        
        # Pass the AppConfig object directly instead of converting to dict
        # This enables InstitutionBot to use attribute-style access throughout
        institution_bot = InstitutionBot(
            config=config,                 # Pass AppConfig directly (no .model_dump())
            ai_handler=ai_handler,
            cache_manager=cache_manager,
            prompt_builder=prompt_builder,
            telegram_token=telegram_token,
            database_manager=database_manager,
            persistence=persistence        # Pass persistence object to bot
        )
        
        logging.info("InstitutionBot initialized successfully with AppConfig integration")
        return institution_bot
        
    except Exception as e:
        logging.error(f"Failed to initialize InstitutionBot: {e}")
        sys.exit(1)


async def cleanup_resources():
    """
    Gracefully clean up all resources in proper order.
    """
    global ai_handler_instance, cache_manager_instance, institution_bot_instance, database_manager_instance
    
    logging.info("Starting resource cleanup...")
    
    # Cleanup AIHandler
    if ai_handler_instance:
        try:
            await ai_handler_instance.cleanup()
            logging.info("AIHandler cleanup completed")
        except Exception as e:
            logging.error(f"Error during AIHandler cleanup: {e}")
    
    # Cleanup CacheManager
    if cache_manager_instance:
        try:
            await cache_manager_instance.cleanup()
            logging.info("CacheManager cleanup completed")
        except Exception as e:
            logging.error(f"Error during CacheManager cleanup: {e}")
    
    # Cleanup DatabaseManager
    if database_manager_instance:
        try:
            await asyncio.to_thread(database_manager_instance.close)
            logging.info("DatabaseManager cleanup completed (connection closed)")
        except Exception as e:
            logging.error(f"Error during DatabaseManager cleanup: {e}")
    
    # Note: InstitutionBot cleanup is handled by the telegram library
    # when the application shuts down
    
    logging.info("Resource cleanup completed")


def setup_signal_handlers():
    """
    Setup signal handlers for graceful shutdown.
    """
    def signal_handler(signum, frame):
        logging.info(f"Received signal {signum}, initiating graceful shutdown...")
        # The cleanup will be handled in the finally block of run_application
        raise KeyboardInterrupt()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def run_application():
    """
    Main application runner that orchestrates all components with full Pydantic AppConfig integration.
    
    REFACTORING HIGHLIGHTS:
    - All initialization functions now receive and use Pydantic models directly
    - Eliminated .model_dump() calls to maintain type safety
    - Enhanced attribute-style configuration access throughout
    - Improved error handling and logging with type-safe operations
    
    Execution flow:
    1. Config Loading (with Pydantic validation)
    2. Logging Setup (using config.logging attributes)
    3. Database Initialization (using config.database)
    4. Cache Initialization (using config.cache model)
    5. PromptBuilder Initialization (using config.institution & config.prompts)
    6. AIHandler Initialization (using config.ai_models)
    7. InstitutionBot Initialization (using full AppConfig)
    8. Application Setup (Telegram Application object creation)
    9. Handler Registration (centralized)
    10. Polling Start
    """
    global ai_handler_instance, cache_manager_instance, institution_bot_instance, database_manager_instance
    
    config = None
    application = None
    
    try:
        # Step 1: Load configuration with Pydantic validation
        logging.info("=" * 80)
        logging.info("INSTITUTION COMPLAINT MANAGEMENT BOT - STARTUP SEQUENCE")
        logging.info("Pydantic AppConfig Integration - Type-Safe Configuration Access")
        logging.info("=" * 80)
        
        config = load_configuration()
        
        # Step 2: Setup logging with AppConfig model
        setup_logging(config)
        
        logging.info("Step 1/8: Configuration loaded and logging configured with Pydantic AppConfig")
        
        # Step 3: Initialize DatabaseManager with attribute access
        logging.info("Step 2/8: Initializing DatabaseManager with AppConfig integration...")
        database_manager_instance = await initialize_database_manager(config)
        
        # Step 4: Initialize CacheManager with CacheModel
        logging.info("Step 3/8: Initializing CacheManager with Pydantic CacheModel...")
        cache_manager_instance = await initialize_cache_manager(config)
        
        # Step 5: Initialize PromptBuilder with sub-models
        logging.info("Step 4/8: Initializing PromptBuilder with Pydantic sub-models...")
        prompt_builder = await initialize_prompt_builder(config)
        
        # Step 6: Initialize AIHandler with AiModelsModel
        logging.info("Step 5/8: Initializing AIHandler with Pydantic AiModelsModel...")
        ai_handler_instance = await initialize_ai_handler(config, cache_manager_instance)
        
        # Step 7: Initialize InstitutionBot with full AppConfig
        logging.info("Step 6/8: Initializing InstitutionBot with complete AppConfig...")
        institution_bot_instance = await initialize_institution_bot(
            config,
            ai_handler_instance,
            cache_manager_instance,
            prompt_builder,
            database_manager_instance
        )
        
        # Step 8: Setup Telegram Application
        logging.info("Step 7/8: Setting up Telegram Application...")
        application = await institution_bot_instance.setup_application()
        
        # Step 9: Register all handlers using centralized system
        logging.info("Step 8/8: Registering handlers via centralized system...")
        register_all_handlers(application, institution_bot_instance)
        
        logging.info("=" * 80)
        logging.info("ALL COMPONENTS INITIALIZED SUCCESSFULLY WITH PYDANTIC INTEGRATION!")
        logging.info("Starting Institution Telegram Bot with type-safe configuration access...")
        logging.info("Bot is now ready to handle user interactions with enhanced reliability.")
        logging.info("=" * 80)
        
        # Step 10: Start polling
        await application.run_polling(
            allowed_updates=['message', 'callback_query', 'inline_query'],
            drop_pending_updates=True
        )
        
    except KeyboardInterrupt:
        logging.info("Received interrupt signal, shutting down gracefully...")
        
    except Exception as e:
        logging.error(f"Unhandled exception in main application: {e}", exc_info=True)
        
    finally:
        # Ensure cleanup is always performed
        if application:
            try:
                await application.stop()
                await application.shutdown()
            except Exception as e:
                logging.error(f"Error during application shutdown: {e}")
        
        await cleanup_resources()
        logging.info("Institution Bot shutdown completed")


def main():
    """
    Main entry point for the application with Pydantic AppConfig integration.
    """
    # Setup basic logging before configuration is loaded
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup signal handlers
    setup_signal_handlers()
    
    try:
        # Run the main application
        asyncio.run(run_application())
        
    except KeyboardInterrupt:
        logging.info("Application terminated by user")
        
    except Exception as e:
        logging.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()