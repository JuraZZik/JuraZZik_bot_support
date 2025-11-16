# 🎟️ Support Bot

> Full-featured Telegram bot for ticket management, feedback collection, and customer support automation

![Version](https://img.shields.io/badge/version-2.5.9-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

---

# Support Bot Project Overview

This is a **Telegram bot for managing support tickets** with a complete ticket processing system, feedback collection, and admin panel. The project is written in Python and containerized through Docker.

## 🎯 Core Functionality

### For Users

- Create tickets with problem descriptions without unnecessary bureaucracy
- Send feedback and suggestions
- Rate support quality (1-3 stars)
- Russian and English language support
- Spam protection through cooldown system
- Automatic notifications about ticket closure

### For Administrator

- Manage all incoming tickets through a single interface
- Direct message exchange with users
- Status management: new → in progress → closed
- Block/unblock users
- Automatic data backup
- View statistics and metrics
- Automatic closure of inactive tickets

## 🛠️ Tech Stack

| Component | Details |
|-----------|---------|
| **Language** | Python 3.11+ |
| **Framework** | python-telegram-bot 21+ |
| **Data Storage** | JSON (embedded database) |
| **Containerization** | Docker & Docker Compose |
| **Localization** | i18n (Russian/English) |
| **Scheduler** | Asynchronous job scheduler |

## 📁 Project Structure

```
bot_support/
├── main.py                    # Entry point
├── config.py                  # Configuration
├── requirements.txt           # Dependencies
├── docker-compose.yml         # Docker config
├── .env.example              # Example .env file
├── handlers/                 # Command handlers
├── services/                 # Services
│   ├── tickets.py           # Ticket management
│   ├── ticket_auto_close.py # Auto-close logic
│   ├── feedback.py          # Feedback system
│   ├── scheduler.py         # Job scheduler
│   └── alerts.py            # Notifications
├── storage/                 # Data management
├── locales/                 # Localization (ru, en)
├── utils/                   # Helper functions
└── bot_data/               # Data (created automatically)
    ├── data.json           # Main data
    ├── banned.json         # Blocked users list
    ├── bot.log            # Logs
    └── backups/           # Backups
```

## 🔑 Key Features

### Automatic Ticket Closure (v2.5.1+)

- Closes ticket if user doesn't respond within 24 hours (configurable)
- Sends localized notifications to admin and user
- Tracks who wrote last — won't close if user is waiting for admin reply

**Usage Scenarios:**

- **Scenario 1 (closes):** user creates ticket (12:00) → admin replies (12:30) → after 24 hours without user response → auto-closure
- **Scenario 2 (stays open):** user creates ticket → admin replies → user replies → ticket stays open

## 📋 Configuration

### Required Parameters

- `BOT_TOKEN` — from @BotFather
- `ADMIN_ID` — administrator ID (send `/id` to bot)
- `DEFAULT_LOCALE` — `ru` (Russian) or `en` (English)

### Recommended

- `ALERT_CHAT_ID` — group ID for notifications
- `TIMEZONE` — timezone
- `AUTO_CLOSE_AFTER_HOURS` — hours before auto-closure (default: 24)

### Additional Features

- Data backup and recovery
- Spam protection with configurable cooldown
- Error notifications
- Minimum message length requirements

## 🚀 Deployment

### With Docker Compose (recommended)

```bash
docker compose up -d
```

### Locally

```bash
pip install -r requirements.txt
python main.py
```

## 📊 Version History

## 📈 Versioning

## 📈 Versioning

|Version|Date|Description|
|--|--|--|
|2.5.9|2025-11-16|⭐ Rating notifications improvements - username & clickable ticket ID|
|2.5.8|2025-11-11|Latest update|
|2.5.1|2025-11-08|⏰ Complete auto-close tickets implementation🆕|
|2.5.0|2025-11-07|🔧 Fixed localization and feedback system|
|2.4.1|2025-11-06|✨ Stable version with multi-language support|
|2.3.9|2025-10-29|🎉 First release|


## 💡 User Workflow

1. Send `/start` to bot
2. Choose menu item
3. Create tickets, send feedback, rate quality
4. Reply to support messages to keep ticket active

## 🎓 Administrator Workflow

1. Open **Inbox** — view all incoming tickets
2. Click **Take in progress** — start working on ticket
3. Click **Reply** — send response to user
4. Click **Close** — complete ticket
5. Check **Statistics** — work analytics
6. Receive notifications about auto-closed tickets

---

This is a fully functional customer support system via Telegram with minimal infrastructure requirements.

# .env Configuration Guide - Support Bot

Complete explanation of all environment variables with examples and descriptions.

---

## 🔴 MANDATORY SETTINGS (REQUIRED)

### BOT_TOKEN
- **What it is:** Your Telegram bot token
- **Where to get it:** 
  1. Open Telegram and find [@BotFather](https://t.me/botfather)
  2. Send `/newbot` command
  3. Follow instructions and get your token
- **Format:** String of numbers and characters
- **Example:** `BOT_TOKEN=123456789:ABCDefGHIjklMNOpqrsTUVwxyz`
- **Required:** YES - bot won't work without it

### ADMIN_ID
- **What it is:** Your Telegram user ID (admin who manages the bot)
- **Where to get it:**
  1. Start the bot you created
  2. Send `/id` command to bot
  3. Bot replies with your ID
- **Format:** Integer (numbers only)
- **Example:** `ADMIN_ID=123456789`
- **Required:** YES - admin features won't work without it
- **Note:** Only this ID will have access to admin panel

### DEFAULT_LOCALE
- **What it is:** Default language for bot interface
- **Options:** 
  - `ru` - Russian (Русский)
  - `en` - English
- **Example:** `DEFAULT_LOCALE=ru`
- **Required:** YES
- **Note:** Users can still change language in bot menu

---

## 📋 RECOMMENDED SETTINGS (NOTIFICATIONS)

### ALERT_CHAT_ID
- **What it is:** Chat ID where bot will send notifications
- **When it's used:** 
  - Bot startup/shutdown alerts
  - Error notifications
  - Important events
- **Where to get it:**
  1. Create a group or supergroup
  2. Add your bot to the group
  3. Send any message in the group
  4. Check bot logs to find the chat ID
  5. Or use debugging tools
- **Format:** Negative integer for groups, positive for users
- **Example:** `ALERT_CHAT_ID=-1001234567890`
- **Required:** NO (but recommended)
- **Note:** Leave empty if you don't want notifications

### ALERT_TOPIC_ID
- **What it is:** Topic/thread ID in a supergroup (for organized notifications)
- **When it's used:** When using Telegram topics feature
- **Format:** Integer
- **Example:** `ALERT_TOPIC_ID=123`
- **Required:** NO
- **Note:** Only works if ALERT_CHAT_ID is set and is a supergroup with topics

### START_ALERT
- **What it is:** Message sent when bot starts
- **When it's used:** On bot startup
- **Example:** `START_ALERT=Bot started successfully ✅`
- **Required:** NO
- **Default:** Bot sends default startup message
- **Tip:** Use emojis to make it more readable

### SHUTDOWN_ALERT
- **What it is:** Message sent when bot shuts down
- **When it's used:** On bot shutdown/restart
- **Example:** `SHUTDOWN_ALERT=Bot stopped for maintenance 🔧`
- **Required:** NO
- **Default:** Bot sends default shutdown message

### TIMEZONE
- **What it is:** Your timezone for scheduling and timestamps
- **Format:** IANA timezone format
- **Common examples:**
  - `Europe/Moscow` - Moscow time
  - `Europe/London` - London time
  - `America/New_York` - New York time
  - `Asia/Tokyo` - Tokyo time
- **Example:** `TIMEZONE=Europe/Moscow`
- **Required:** NO
- **Default:** UTC if not set
- **Tip:** Use this to get correct time in logs and alerts

---

## ⏰ AUTO-CLOSE SETTINGS (Automatic Ticket Closure)

### AUTO_CLOSE_AFTER_HOURS
- **What it is:** Hours to wait before automatically closing inactive tickets
- **When it's used:**
  - Admin sends reply to user
  - User doesn't respond within this time
  - Bot automatically closes ticket
- **Format:** Integer (number of hours)
- **Example:** `AUTO_CLOSE_AFTER_HOURS=24`
- **Default:** 24 hours (if not set)
- **Range:** Any positive number
- **Common values:**
  - `AUTO_CLOSE_AFTER_HOURS=24` - Close after 1 day (default)
  - `AUTO_CLOSE_AFTER_HOURS=48` - Close after 2 days
  - `AUTO_CLOSE_AFTER_HOURS=72` - Close after 3 days
- **How it works:**
  1. User creates ticket
  2. Admin replies (timer starts)
  3. After X hours without user response
  4. Ticket closes automatically
  5. Both admin and user get notification
- **Note:** Only closes if admin sent the last message

---

## 💾 BACKUP SETTINGS (Data Protection)

### BACKUP_ENABLED
- **What it is:** Enable/disable automatic backups
- **Format:** `true` or `false`
- **Example:** `BACKUP_ENABLED=true`
- **Default:** false
- **Purpose:** Protect your data from loss
- **Recommended:** true (always enable backups!)

### BACKUP_FULL_PROJECT
- **What it is:** Whether to backup entire project or just data
- **Format:** `true` or `false`
- **Example:** `BACKUP_FULL_PROJECT=false`
- **Options:**
  - `false` - Backup only bot_data/ folder (data.json, banned.json)
  - `true` - Backup entire project including code
- **Recommended:** false (saves space, only data matters)

### BACKUP_SEND_TO_TELEGRAM
- **What it is:** Send backup files to Telegram for safety
- **Format:** `true` or `false`
- **Example:** `BACKUP_SEND_TO_TELEGRAM=true`
- **Purpose:** 
  - Cloud backup in case server fails
  - Easy download from Telegram
- **How it works:**
  1. Creates backup file
  2. Sends it to ALERT_CHAT_ID
  3. You can download anytime
- **Recommended:** true (extra safety)
- **Requires:** ALERT_CHAT_ID to be set

### BACKUP_MAX_SIZE_MB
- **What it is:** Maximum backup file size in megabytes
- **Format:** Integer
- **Example:** `BACKUP_MAX_SIZE_MB=50`
- **Default:** 50 MB
- **Purpose:** Limit file size (especially for Telegram upload)
- **Note:** Telegram has 2GB limit, but 50MB is practical

---

## 🚨 SPAM PROTECTION SETTINGS (Prevent Abuse)

### FEEDBACK_COOLDOWN_ENABLED
- **What it is:** Enable/disable cooldown between feedback submissions
- **Format:** `true` or `false`
- **Example:** `FEEDBACK_COOLDOWN_ENABLED=true`
- **Purpose:** Prevent users from spamming feedback
- **Recommended:** true

### FEEDBACK_COOLDOWN_HOURS
- **What it is:** Hours users must wait between feedback submissions
- **Format:** Integer (number of hours)
- **Example:** `FEEDBACK_COOLDOWN_HOURS=24`
- **Default:** 24 hours
- **Common values:**
  - `1` - 1 hour cooldown
  - `6` - 6 hours cooldown
  - `24` - 24 hours (1 day)
- **Purpose:** One user can send feedback only once per X hours
- **Requires:** FEEDBACK_COOLDOWN_ENABLED=true

### ASK_MIN_LENGTH
- **What it is:** Minimum characters in ticket/feedback message
- **Format:** Integer (number of characters)
- **Example:** `ASK_MIN_LENGTH=10`
- **Default:** 10 characters
- **Purpose:** Prevent low-quality, empty, or spam messages
- **Common values:**
  - `5` - Very permissive
  - `10` - Balanced (recommended)
  - `20` - Strict
- **How it works:** User message rejected if shorter than this

---

## 🔔 ERROR NOTIFICATION SETTINGS (Monitor Problems)

### ERROR_ALERTS_ENABLED
- **What it is:** Enable/disable error notifications to admin
- **Format:** `true` or `false`
- **Example:** `ERROR_ALERTS_ENABLED=true`
- **Purpose:** Get notified when bot encounters errors
- **Recommended:** true (helps with debugging)
- **Requires:** ALERT_CHAT_ID to be set

### ERROR_ALERT_THROTTLE_SEC
- **What it is:** Prevent error spam (seconds between error alerts)
- **Format:** Integer (seconds)
- **Example:** `ERROR_ALERT_THROTTLE_SEC=300`
- **Default:** 300 seconds (5 minutes)
- **Purpose:** 
  - If same error happens 100 times, notify only once per 5 min
  - Prevents Telegram spam
- **Common values:**
  - `60` - Notify every minute
  - `300` - Notify every 5 minutes (recommended)
  - `3600` - Notify every hour

---

## 📝 COMPLETE EXAMPLE .env FILE

```bash
# ============================================
# MANDATORY - Bot Connection
# ============================================
BOT_TOKEN=123456789:ABCDefGHIjklMNOpqrsTUVwxyz
ADMIN_ID=987654321
DEFAULT_LOCALE=ru

# ============================================
# Notifications & Alerts
# ============================================
ALERT_CHAT_ID=-1001234567890
ALERT_TOPIC_ID=123
START_ALERT=🤖 Bot started successfully
SHUTDOWN_ALERT=🛑 Bot stopped
TIMEZONE=Europe/Moscow

# ============================================
# Auto-Close Tickets
# ============================================
AUTO_CLOSE_AFTER_HOURS=24

# ============================================
# Backup Settings
# ============================================
BACKUP_ENABLED=true
BACKUP_FULL_PROJECT=false
BACKUP_SEND_TO_TELEGRAM=true
BACKUP_MAX_SIZE_MB=50

# ============================================
# Spam Protection
# ============================================
FEEDBACK_COOLDOWN_ENABLED=true
FEEDBACK_COOLDOWN_HOURS=24
ASK_MIN_LENGTH=10

# ============================================
# Error Monitoring
# ============================================
ERROR_ALERTS_ENABLED=true
ERROR_ALERT_THROTTLE_SEC=300
```

---

## 🚀 QUICK START CHECKLIST

- [ ] Get BOT_TOKEN from @BotFather
- [ ] Get ADMIN_ID by sending `/id` to your bot
- [ ] Set DEFAULT_LOCALE (ru or en)
- [ ] Set ALERT_CHAT_ID (create group and get ID)
- [ ] Set TIMEZONE to your timezone
- [ ] Enable BACKUP_ENABLED=true
- [ ] Enable ERROR_ALERTS_ENABLED=true
- [ ] Start bot: `docker compose up -d`

---

## 💡 RECOMMENDATIONS FOR BEGINNERS

**Minimal setup (just to run):**
```bash
BOT_TOKEN=your_token_here
ADMIN_ID=your_id_here
DEFAULT_LOCALE=ru
```

**Recommended setup (with monitoring):**
```bash
BOT_TOKEN=your_token_here
ADMIN_ID=your_id_here
DEFAULT_LOCALE=ru
ALERT_CHAT_ID=your_group_id
TIMEZONE=...
AUTO_CLOSE_AFTER_HOURS=24
BACKUP_ENABLED=true
FEEDBACK_COOLDOWN_ENABLED=true
ERROR_ALERTS_ENABLED=true
```

**Production setup (full features):**
```bash
# All settings enabled with optimized values
BOT_TOKEN=your_token_here
ADMIN_ID=your_id_here
DEFAULT_LOCALE=ru
ALERT_CHAT_ID=your_group_id
ALERT_TOPIC_ID=123
START_ALERT=🤖 Bot started
SHUTDOWN_ALERT=🛑 Bot stopped
TIMEZONE=Europe/Moscow
AUTO_CLOSE_AFTER_HOURS=24
BACKUP_ENABLED=true
BACKUP_FULL_PROJECT=false
BACKUP_SEND_TO_TELEGRAM=true
BACKUP_MAX_SIZE_MB=50
FEEDBACK_COOLDOWN_ENABLED=true
FEEDBACK_COOLDOWN_HOURS=24
ASK_MIN_LENGTH=10
ERROR_ALERTS_ENABLED=true
ERROR_ALERT_THROTTLE_SEC=300
```

---

## ❓ COMMON QUESTIONS

**Q: What happens if I don't set ALERT_CHAT_ID?**
A: Bot still works, but you won't get notifications. You won't know when it starts, stops, or has errors.

**Q: Can I change these values without restarting bot?**
A: No. You need to restart bot after changing .env file for changes to take effect.

**Q: What if AUTO_CLOSE_AFTER_HOURS is too short?**
A: Users might get frustrated if tickets close before they see admin reply. Recommend at least 24 hours.

**Q: Should I enable all backups?**
A: Yes! Backups are cheap insurance. If data corrupts, you lose everything. Always backup.

**Q: What timezone should I use?**
A: Use your local timezone. This affects when auto-close checks run and log timestamps.

---

## 🔗 USEFUL RESOURCES

- Telegram timezone list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
- Telegram Bot API docs: https://core.telegram.org/bots/api
- Your bot's bot page: https://t.me/BotFather (send `/help`)
