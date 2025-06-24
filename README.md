# Institution Complaint Management Bot (AIGate)

![AIGate Logo](https://user-images.githubusercontent.com/your-username/your-repo/assets/logo_135.png)

An advanced, AI-powered Telegram bot designed to streamline and automate the complaint and feedback management process for institutions.

---

## 🌟 Key Features

- **🧠 AI-Powered Intent Analysis**: Automatically understands user intent (complaint, suggestion, greeting) and triggers the appropriate flow using LLMs.
- **🗣️ Bilingual Support (Arabic/English)**: Detects user language and responds accordingly.
- **🗂️ Dynamic & Configurable Flows**: Form fields customizable via `config.yaml`.
- **⚡ Critical Complaint Detection**: Urgent messages trigger email alerts to staff.
- **⚙️ Type-Safe & Robust Configuration**: Uses Pydantic for YAML validation and python-dotenv for secrets.
- **🔐 Admin Panel**: Access via `/admin` command for:
  - 📊 Real-time stats
  - 📤 (Future) data export
- **🗄️ Persistent Conversations**: Keeps conversation state via `PicklePersistence`.
- **📝 Database Integration**: Logs data into SQLite database securely.
- **🧩 Modular & Scalable Architecture**: Clean separation of AI, database, and bot logic.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+
- **Bot Framework**: python-telegram-bot
- **AI Integration**: OpenRouter / Hugging Face (via aiohttp)
- **Config**: PyYAML, Pydantic, python-dotenv
- **DB**: SQLite
- **Async**: asyncio

---

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.10+
- `git`
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- OpenRouter API key from [OpenRouter.ai](https://openrouter.ai/)
- Email credentials (e.g. Gmail) for SMTP notifications

### 2. Installation

```bash
# Clone repo
git clone https://github.com/gait2ai/AIGate_complaint_bot.git
cd AIGate_complaint_bot

# Virtual environment
python3 -m venv venv
source venv/bin/activate  # or .\venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

```bash
cp .env.example .env
```

Edit `.env`:

```env
TELEGRAM_BOT_TOKEN="your_telegram_token"
OPENROUTER_API_KEY="your_openrouter_key"
HF_API_TOKEN="your_huggingface_token"
SMTP_EMAIL="your-email@example.com"
SMTP_PASSWORD="your-password"
```

```bash
cp app/config/config.yaml.txt app/config/config.yaml
```

Customize `config.yaml`:

```yaml
admin_settings:
  admin_user_ids:
    - 123456789

application_settings:
  data_collection_fields:
    email: false
    department: false
```

### 4. Run the Bot

```bash
python main.py
```

---

## 🤖 Usage

- **Users**: Type your complaint directly or use `/start`.
- **Admins**: Use `/admin` for dashboard access.

---

## 🏗️ Project Structure

```
AIGate_complaint_bot/
├── app/
│   ├── bot/
│   │   ├── handlers/
│   │   │   ├── admin_handlers.py
│   │   │   ├── complaint_flow_handlers.py
│   │   │   └── ...
│   │   ├── institution_bot_logic.py
│   │   └── states.py
│   ├── config/
│   │   └── config.yaml
│   ├── core/
│   │   ├── ai_handler.py
│   │   ├── database_manager.py
│   │   └── email_service.py
│   └── database/
├── logs/
├── .env
├── main.py
└── README.md
```

---

## 🤝 Contributing

Fork → Branch → Commit → Push → Pull Request

---

## 📄 License

MIT License - see `LICENSE.md`.