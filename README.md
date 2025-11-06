# 🎟️ Support Bot

> Full-featured Telegram bot for ticket management, feedback collection, and customer support automation

![Version](https://img.shields.io/badge/version-2.3.9-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## 📋 Description

**Support Bot** is a scalable ticket management system via Telegram that enables:

✅ Users to quickly create tickets without bureaucracy  
✅ Administrators to manage all tickets from a single interface  
✅ Feedback collection and support quality tracking  
✅ Automation of routine operations  

---

## 🚀 Key Features

### 👤 For Users

| Feature | Description |
|---------|-------------|
| 📨 **Create Tickets** | Quick ticket creation with problem description |
| 💬 **Feedback & Suggestions** | Send service quality feedback |
| ⭐ **Quality Rating** | Rate support (1-3 stars) |
| 🌐 **Multi-language Support** | Russian and English support |
| ⏱️ **Spam Protection** | Cooldown system between tickets |

### 👨‍💼 For Administrators

| Feature | Description |
|---------|-------------|
| 📋 **Admin Panel** | Manage all incoming tickets |
| 💬 **Direct Replies** | Communicate directly with users |
| 🔄 **Status Management** | Transitions: new → in progress → closed |
| 🚫 **User Blocking System** | Block/unblock users |
| 💾 **Automatic Backups** | Data backup and recovery |
| 📊 **Statistics** | View metrics and analytics |
| 📢 **Notifications** | Alerts for new tickets |

---

## 🔧 Tech Stack

- **Language:** Python 3.11+
- **Framework:** python-telegram-bot 21+
- **Database:** JSON (embedded)
- **Containerization:** Docker & Docker Compose
- **Localization:** i18n (Russian/English)

---

## 📦 Requirements

- Docker and Docker Compose
- Python 3.11+ (for local run)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Telegram User ID of administrator

---

## 🚀 Quick Start

### 1️⃣ Clone Repository

git clone https://github.com/JuraZZik/bot_support.git
cd bot_support


### 2️⃣ Configuration

Create `.env` file:

🔴 MANDATORY!
BOT_TOKEN=7123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi
ADMIN_ID=5233603778
DEFAULT_LOCALE=en

📋 RECOMMENDED (for notifications)
ALERT_CHAT_ID=-1003111989559
ALERT_TOPIC_ID=127
START_ALERT=true
SHUTDOWN_ALERT=true
TIMEZONE=UTC


**Where to find:**

| Parameter | Where to find |
|-----------|--------------|
| `BOT_TOKEN` | `@BotFather` → `/newbot` |
| `ADMIN_ID` | Send `/id` to bot, get your ID |
| `ALERT_CHAT_ID` | Group ID (send message in debug) |
| `DEFAULT_LOCALE` | `ru` (Russian) or `en` (English) |



### 3️⃣ Run with Docker

docker compose up -d

### 4️⃣ Local Run

Install dependencies
pip install -r requirements.txt

Run bot
python main.py


---

## 📚 Usage

### For User:

1. Write `/start` to bot
2. Choose needed menu item
3. Create tickets, send feedback, rate quality

### For Administrator:

1. Open **Inbox** – view all tickets
2. Press **Take in progress** – start working with ticket
3. Press **Reply** – send reply to user
4. Press **Close** – finish ticket
5. Check **Statistics** – work analytics

---

## 🗂️ Project Structure

bot_support/
├── main.py # Entry point
├── config.py # Configuration
├── requirements.txt # Dependencies
├── docker-compose.yml # Docker config
├── .env.example # Example .env
├── handlers/ # Command handlers
├── services/ # Services (tickets, feedback, etc.)
├── storage/ # Data management
├── locales/ # Localization (ru, en)
├── utils/ # Helper functions
└── bot_data/ # Data (created automatically)
├── data.json # Main data
├── banned.json # Ban list
├── bot.log # Logs
└── backups/ # Backups


---

## 🛠️ Additional Configuration

### Backups

BACKUP_ENABLED=true
BACKUP_FULL_PROJECT=true
BACKUP_SEND_TO_TELEGRAM=true
BACKUP_MAX_SIZE_MB=100


### Spam Protection

FEEDBACK_COOLDOWN_ENABLED=true
FEEDBACK_COOLDOWN_HOURS=24
ASK_MIN_LENGTH=10


### Error Notifications

ERROR_ALERTS_ENABLED=true
ERROR_ALERT_THROTTLE_SEC=60


### Detailed Documentation

See `.env` file for all available options.

---

## 📊 API Endpoints

Bot works through Telegram Bot API. No public REST endpoints.

---

## 🤝 Contributing

Suggestions, feedback, and bug reports are welcome!

Write to me:
- 🐛 About bugs
- 💡 About ideas
- ✨ About features

---

## 📝 License

MIT License – free for personal and commercial use.

---

## 👨‍💻 Author

**JuraZZik**

- Telegram: [@JuraZZik](https://t.me/JuraZZik)
- Bot: [@JuraZZik_SupportBot](https://t.me/JuraZZik_SupportBot)
- GitHub: [github.com/JuraZZik](https://github.com/JuraZZik)

---

## 📈 Versioning

| Version | Date | Description |
|---------|------|-------------|
| 2.3.9 | 2025-10-29 | ✨ Stable version with multi-language support |
| 2.3.0 | 2025-10 | 🎉 First release |

---

## ⭐ Support

If you like the project – give it a star! ⭐

⭐
⭐⭐
⭐⭐⭐
⭐⭐⭐⭐⭐


---

**Thank you for using Support Bot!** 🎉


