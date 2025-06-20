# Institution Complaint Management Bot (AIGate)

![Bot Banner](https://user-images.githubusercontent.com/your-username/your-repo/assets/logo_135.png)

An advanced, AI-powered Telegram bot designed to streamline and automate the complaint and feedback management process for institutions. This bot leverages modern Natural Language Processing (NLP) to understand user intent, guide users through structured conversation flows, and provide a seamless experience for both beneficiaries and administrators.

---

## 🌟 Key Features

- **🧠 AI-Powered Intent Analysis**: Automatically understands the user's initial message (complaint, suggestion, greeting) and directs them to the appropriate conversation flow using Large Language Models (LLMs).
- **🗣️ Bilingual Support (Arabic/English)**: Provides a fully localized experience, detecting the user's language preference and responding accordingly.
- **🗂️ Structured Conversation Flows**: Guides users step-by-step through submitting complaints or suggestions, ensuring all necessary information is collected.
- **⚡ Critical Complaint Detection**: AI-driven identification of urgent cases with instant email notifications to relevant personnel.
- **⚙️ Secure & Robust Configuration**: Utilizes Pydantic for strict configuration validation and `python-dotenv` for secure management of secrets, preventing common runtime errors and security vulnerabilities.
- **🔐 Administrator-Only Panel**: A secure `/admin` command provides authorized users with access to:
  - 📊 **Real-time Statistics**: View total complaints, critical case counts, and status breakdowns.
  - 📤 **Data Export**: (Future-proofed) Functionality to export data for external analysis.
- **🗄️ Persistent Conversations**: Remembers the user's conversation state even if the bot restarts, allowing users to seamlessly continue where they left off.
- **📝 Database Integration**: Securely logs all complaints and user profiles into a dedicated SQLite database for record-keeping and analysis.
- **🧩 Modular & Scalable Architecture**: Built with a clean separation of concerns (core services, bot logic, handlers), making it easy to maintain and extend with new features.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.10+
- **Telegram Framework**: `python-telegram-bot`
- **AI Integration**: `OpenRouter` / `Hugging Face` APIs via `aiohttp`
- **Configuration**: `PyYAML`, `Pydantic`, `python-dotenv`
- **Database**: `SQLite` (built-in)
- **Asynchronous Programming**: `asyncio`

---

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.10 or higher
- `git` command-line tool
- A Telegram Bot Token obtained from [@BotFather](https://t.me/BotFather)
- An API key from [OpenRouter.ai](https://openrouter.ai/) for LLM access

### 2. Installation

```bash
git clone https://github.com/gait2ai/AIGate_complaint_bot.git
cd AIGate_complaint_bot
```

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate  # or .\venv\Scripts\activate on Windows
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Configuration

Copy and edit the environment file:

```bash
cp env.example .env
```

Update `.env`:

```env
TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here"
OPENROUTER_API_KEY="your_openrouter_api_key_here"
HF_API_TOKEN="your_huggingface_api_token_here"
SMTP_EMAIL="your-email@example.com"
SMTP_PASSWORD="your_email_password_or_app_password"
```

Edit `app/config/config.yaml`:

```yaml
admin_settings:
  admin_user_ids:
    - 123456789  # Replace with your Telegram ID
```

### 4. Running the Bot

```bash
python main.py
```

---

## 🤖 Usage

**For Users**: Start a chat and follow the bot's guidance. Use `/cancel` to exit, `/help` for help.

**For Admins**: Use `/admin` for stats and tools if your Telegram ID is registered.

---

## 🏗️ Project Structure

```
AIGate_complaint_bot/
├── app/
│   ├── bot/
│   │   ├── handlers/         # All Telegram handlers (commands, conversations)
│   │   ├── __init__.py
│   │   ├── institution_bot_logic.py # Core business logic
│   │   ├── states.py         # Conversation state definitions
│   │   └── utils.py          # Shared utilities (messaging, keyboards)
│   ├── config/               # Configuration files (YAML, prompts, models)
│   ├── core/                 # Core services (AI, DB, Cache)
│   └── database/             # SQLite database file location
├── logs/                     # Log files
├── .env                      # Environment variables (sensitive data)
├── .gitignore
├── config.yaml.txt           # Example configuration
├── main.py                   # Main application entry point
└── README.md
```

---

## 🤝 Contributing

Fork → Branch → Commit → Push → PR

---

## 📄 License

This project is licensed under a dual-license model. Please see the [LICENSE.md](LICENSE.md) file for complete licensing information.
