# Institution Complaint Management Bot

![AI Gate Logo](./assets/logo_135.png)

The **Institution Complaint Management Bot** is a Telegram-based application designed to help organizations efficiently manage and process beneficiary/client complaints and suggestions using AI. This project is developed by **AI Gate for Artificial Intelligence Applications**.

## Overview

This application provides a robust and customizable platform for:
- Automated collection and intelligent classification of complaints and suggestions.
- Identification and escalation of critical or urgent cases.
- Secure local data management for beneficiary information and complaints.
- Multilingual support, configurable for various languages (primarily Arabic and English out-of-the-box).
- Local data storage using **SQLite**, removing dependency on external spreadsheet services.
- Optional email notifications for critical cases (can be re-enabled if needed).

## Features

- **Telegram Bot Interface**: Intuitive and easy-to-use interface for users to submit complaints or suggestions.
- **AI-Powered Processing**: Leverages advanced AI models (configurable via OpenRouter, Hugging Face, etc.) for:
  - Complaint/suggestion classification.
  - Criticality assessment.
  - Intent determination.
  - Summarization and translation (if required).
- **SQLite Database Integration**: All application data (beneficiary profiles, complaints, classification keys) is stored securely in a local SQLite database, offering greater control and privacy.
- **Configurable Critical Case Handling**: Defines how critical cases are identified and can be configured to trigger notifications.
- **Beneficiary Data Management**: Maintains beneficiary information for context and follow-up, respecting privacy.
- **Dynamic Multilingual Support**: User-facing messages can be customized per institution and language via configuration files.
- **Modular Design**: Core components like AI handling, caching, prompt building, and database management are separated for better maintainability and scalability.

## Technical Details

### System Architecture (Updated)
```
institution_complaint_bot/
├── app/
│   ├── bot/
│   │   ├── institution_bot_logic.py         # Core bot logic
│   │   └── bot_telegram_handlers.py         # Telegram interaction handlers
│   ├── core/
│   │   ├── ai_handler.py                    # Manages AI model interactions
│   │   ├── cache_manager.py                 # Caching for performance
│   │   ├── database_manager.py              # Handles SQLite database operations
│   │   └── prompt_builder.py                # Constructs AI prompts
│   ├── config/
│   │   ├── config.yaml                      # Main application configuration
│   │   ├── institution_system_prompt.txt    # System prompt for AI
│   │   ├── gmail_credentials.json           # Optional: For Gmail API
│   │   └── token.json                       # Optional: Gmail token
│   └── database/
│       └── ins_data.db                      # SQLite database file (auto-generated)
├── assets/
│   └── logo_135.png                         # Example logo file
├── .env                                     # For environment variables
├── .gitignore                               # Specifies intentionally untracked files
├── requirements.txt                         # Python dependencies
└── main.py                                  # Main application entry point
```

### Core Components
1. **`main.py`**: Orchestrates application startup, initialization of all modules, and lifecycle management.
2. **`DatabaseManager` (`app/core/database_manager.py`)**: Manages all interactions with the SQLite database, including table creation and CRUD operations.
3. **`InstitutionBot` (`app/bot/institution_bot_logic.py`)**: Contains the central application logic, processing flows, and integration of other core components.
4. **`Telegram Handlers` (`app/bot/bot_telegram_handlers.py`)**: Manages all user interactions via Telegram, conversation flows, and command handling.
5. **`AIHandler` (`app/core/ai_handler.py`)**: Interfaces with various AI model providers for tasks like classification and natural language understanding.
6. **`PromptBuilder` (`app/core/prompt_builder.py`)**: Dynamically constructs tailored prompts for AI models based on task and institutional context.
7. **`CacheManager` (`app/core/cache_manager.py`)**: Provides intelligent caching mechanisms to optimize performance and reduce redundant operations.
8. **Configuration Files (`app/config/`)**:
   - `config.yaml`: Central configuration for the bot, AI models, cache, logging, and institution-specific settings.
   - `institution_system_prompt.txt`: The main system prompt guiding the AI's behavior and responses.

## Installation

### Prerequisites
- Python 3.9+
- Telegram Bot Token
- API keys for desired AI model providers (e.g., OpenRouter, Hugging Face API)
- (Optional) Gmail API credentials if email notification for critical cases is re-enabled.

### Setup

1. **Clone the repository:**
```bash
git clone https://github.com/your-repo/institution-complaint-bot.git
cd institution-complaint-bot
```

2. **Create and activate a virtual environment (recommended):**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure the application:**
- Navigate to `app/config/`.
- Rename or create `config.yaml`.
- Customize the following:
  - Institution details.
  - Custom bot messages.
  - AI model configuration.
  - Email credentials (optional).
- Create a `.env` file with the following content:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
HF_API_TOKEN=your_huggingface_api_token_here
```

5. **Run the application:**
```bash
python main.py
```

The bot will start and initialize the SQLite database if it does not exist.

## Configuration

The main configuration file is `app/config/config.yaml`. It allows customization of:
- Institution-specific details
- Bot behavior and settings
- AI models and parameters
- Caching and logging settings
- Prompt templates

## Usage

Users can interact with the bot on Telegram using commands like:
- `/start`
- `/complaint`
- `/suggestion`
- `/contact`
- `/help`
- `/cancel`

The bot guides users through a conversation to collect information efficiently.

## Monitoring

Logging is configured via `config.yaml` and typically logs to `logs/institution_bot.log`. Log rotation and retention are configurable.

## License

This application is developed by AI Gate for Artificial Intelligence Applications. Licensing terms to be defined by AI Gate.

## Credits

**Produced by:** AI Gate for Artificial Intelligence Applications  
**Contact:** [abuamr.dubai@gmail.com](mailto:abuamr.dubai@gmail.com)

---
For support or contributions, please contact AI Gate directly.
