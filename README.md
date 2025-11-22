# 🎟️ Support Bot
`
> Full-featured Telegram bot for ticket management, feedback collection, and customer support automation

![Version](https://img.shields.io/badge/version-2.8.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-orange)
[![Donate](https://img.shields.io/badge/Donate-Telegram%20Tribute-brightgreen)](https://t.me/tribute/app?startapp=dAi3)
---

# Support Bot Project Overview

This is a **Telegram bot for managing support tickets** with a complete ticket processing system, feedback collection, and admin panel. The project is written in Python and containerized through Docker.

## 🎯 Core Functionality

### For Users

- Create tickets with problem descriptions without unnecessary bureaucracy  
- Send feedback and suggestions  
- Rate support quality (1–3 stars)  
- Russian and English language support  
- Spam protection through cooldown system  
- Automatic notifications about ticket closure  

### For Administrator

- Manage all incoming tickets through a single interface  
- Direct message exchange with users  
- Status management: new → in progress → closed  
- Block/unblock users  
- Automatic data backup  
- View statistics and metrics (total users/tickets, active/closed, rating stats)  
- Automatic closure of inactive tickets  
- Info & Debug screens in settings (configuration and diagnostics)  

## 🆕 What’s New in 2.6.0

- Inline message after admin reply now shows **ticket ID** (text + media replies).  
- Improved **statistics block**: tickets waiting for auto-close and recent 30-day metrics.  
- **Auto-close UX**: user gets a button “Ask Question” in auto-close notification to quickly open a new ticket.  
- **Admin UX**:
  - ticket card shows whose turn it is (user/support) and ETA to auto-close;  
  - inbox list shows turn indicator;  
  - inbox sorting prioritizes tickets where user is waiting for support reply.  

---

## 🛠️ Tech Stack

| Component      | Details                 |
|---------------|-------------------------|
| **Language**  | Python 3.11+            |
| **Framework** | python-telegram-bot 21+ |
| **Data Storage** | JSON (embedded database) |
| **Containerization** | Docker & Docker Compose |
| **Localization** | i18n (Russian/English) |
| **Scheduler** | Asynchronous job scheduler |

## 📁 Project Structure

```text

bot_support/
├── main.py                # Entry point: Telegram bot application
├── config.py              # Configuration: token, ADMIN_ID, paths, intervals, versions
├── requirements.txt       # Python dependencies
├── docker-compose.yml     # Docker orchestration (bot + volume for bot_data)
├── .env.example           # Example .env file with main environment variables
├── handlers/              # Telegram update handlers
│   ├── start.py           # /start, user and admin menu
│   ├── user.py            # User messages, ticket creation
│   ├── admin.py           # Inbox, ticket cards, admin text, bans
│   ├── callbacks.py       # Inline buttons: rating, search, settings, help
│   ├── commands.py        # Other commands (if any)
│   └── errors.py          # Error catching and logging
├── services/              # Services / business logic
│   ├── tickets.py         # Ticket management (CRUD, statuses, rating)
│   ├── ticket_auto_close.py  # Auto-close ticket logic based on inactivity timer
│   ├── feedback.py        # Collecting reviews and suggestions, cooldowns
│   ├── scheduler.py       # Job scheduler (auto-close, backup, cleanup)
│   ├── alerts.py          # Notifications to admin/tech chat (startup, errors, backups)
│   ├── backup.py          # Creating and sending backups
│   └── bans.py            # Working with banned users
├── storage/               # Data layer
│   ├── data_manager.py    # Loading/saving data.json, statistics
│   ├── models.py          # Models for tickets/users/feedback
│   └── instruction_store.py # Storage for instruction/help texts (if used)
├── locales/               # UI localization
│   ├── ru.json            # Russian texts
│   └── en.json            # English texts
├── utils/                 # Helper modules
│   ├── keyboards.py       # Inline keyboards (menus, settings, rating, help)
│   ├── admin_help.py      # “❓ Admin help” text
│   ├── admin_screen.py    # Unified admin screen rendering (edit/send + logging)
│   ├── formatters.py      # Pretty formatting for ticket cards and statistics
│   ├── locale_helper.py   # Getting/setting user/admin language
│   ├── states.py          # State constants (FSM for admin and user)
│   └── validators.py      # Input validation (IDs, lengths, etc.)
└── bot_data/              # Runtime data (created automatically)
    ├── data.json          # Main storage: users, tickets, feedback
    ├── banned.json        # Banned users list
    ├── bot.log            # Current bot log (with rotation)
    └── backups/           # Project/data.json backup archives



## 🔑 Key Features

### Automatic Ticket Closure (v2.5.1+)

- Closes ticket if user doesn't respond within N hours after admin reply (configurable).  
- Sends localized notifications to admin and user.  
- Tracks who wrote last — **won’t close** if user is waiting for admin reply.  

**Usage Scenarios:**

- **Scenario 1 (closes):** user creates ticket (12:00) → admin replies (12:30) → after 24 hours without user response → auto-closure.  
- **Scenario 2 (stays open):** user creates ticket → admin replies → user replies → ticket stays open.  

---

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

---

## 🚀 Deployment

### With Docker Compose (recommended)

docker compose up -d


### Locally


pip install -r requirements.txt
python main.py


---

## 📊 Version History

| Version | Date      | Description                                                                  |
|--------|------------|------------------------------------------------------------------------------|
| 2.8.0  | 2025-11-22 | 📨 Admin reply confirmation with Send/Edit/Cancel buttons                    |
| 2.7.0  | 2025-11-18 | ❓ New detailed admin help screen, donate button, minor callbacks cleanup    |
| 2.6.0  | 2025-11-18 | ⏰ UX for auto-close, “whose turn” indicator, improved inbox & statistics    |
| 2.5.10 | 2025-11-18 | 📊 Rating stats in admin panel, Info/Debug screens in settings               |
| 2.5.9  | 2025-11-16 | ⭐ Rating notifications improvements – username & clickable ticket ID        |
| 2.5.8  | 2025-11-11 | Latest update                                                                |
| 2.5.1  | 2025-11-08 | ⏰ Complete auto-close tickets implementation 🆕                             |
| 2.5.0  | 2025-11-07 | 🔧 Fixed localization and feedback system                                    |
| 2.4.1  | 2025-11-06 | ✨ Stable version with multi-language support                                |
| 2.3.9  | 2025-10-29 | 🎉 First release                                                             |


---

## 💡 User Workflow

1. Send `/start` to bot.  
2. Choose menu item.  
3. Create tickets, send feedback, rate quality.  
4. Reply to support messages to keep ticket active.  

## 🎓 Administrator Workflow

1. Open **Inbox** — view all incoming tickets.  
2. Click **Take in progress** — start working on ticket.  
3. Click **Reply** — send response to user.  
4. Click **Close** — complete ticket.  
5. Check **Statistics** — work analytics.  
6. Receive notifications about auto-closed tickets.  

---

This is a fully functional customer support system via Telegram with minimal infrastructure requirements.

---

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
  - `Europe/Moscow`  
  - `Europe/London`  
  - `America/New_York`  
  - `Asia/Tokyo`  
- **Example:** `TIMEZONE=Europe/Moscow`  
- **Required:** NO  
- **Default:** UTC if not set  

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

---

## 💾 BACKUP SETTINGS (Data Protection)

### BACKUP_ENABLED

- **What it is:** Enable/disable automatic backups  
- **Format:** `true` or `false`  
- **Example:** `BACKUP_ENABLED=true`  
- **Default:** false  

### BACKUP_FULL_PROJECT

- **What it is:** Whether to backup entire project or just data  
- **Format:** `true` or `false`  
- **Example:** `BACKUP_FULL_PROJECT=false`  

### BACKUP_SEND_TO_TELEGRAM

- **What it is:** Send backup files to Telegram for safety  
- **Format:** `true` or `false`  
- **Example:** `BACKUP_SEND_TO_TELEGRAM=true`  

### BACKUP_MAX_SIZE_MB

- **What it is:** Maximum backup file size in megabytes  
- **Format:** Integer  
- **Example:** `BACKUP_MAX_SIZE_MB=50`  

---

## 🚨 SPAM PROTECTION SETTINGS (Prevent Abuse)

### FEEDBACK_COOLDOWN_ENABLED

- **What it is:** Enable/disable cooldown between feedback submissions  
- **Format:** `true` or `false`  
- **Example:** `FEEDBACK_COOLDOWN_ENABLED=true`  

### FEEDBACK_COOLDOWN_HOURS

- **What it is:** Hours users must wait between feedback submissions  
- **Format:** Integer  
- **Example:** `FEEDBACK_COOLDOWN_HOURS=24`  

### ASK_MIN_LENGTH

- **What it is:** Minimum characters in ticket/feedback message  
- **Format:** Integer  
- **Example:** `ASK_MIN_LENGTH=10`  

---

## 🔔 ERROR NOTIFICATION SETTINGS (Monitor Problems)

### ERROR_ALERTS_ENABLED

- **What it is:** Enable/disable error notifications to admin  
- **Format:** `true` or `false`  
- **Example:** `ERROR_ALERTS_ENABLED=true`  

### ERROR_ALERT_THROTTLE_SEC

- **What it is:** Prevent error spam (seconds between error alerts)  
- **Format:** Integer  
- **Example:** `ERROR_ALERT_THROTTLE_SEC=300`  

---

## 📝 COMPLETE EXAMPLE .env FILE

MANDATORY - Bot Connection
BOT_TOKEN=123456789:ABCDefGHIjklMNOpqrsTUVwxyz
ADMIN_ID=987654321
DEFAULT_LOCALE=ru

Notifications & Alerts
ALERT_CHAT_ID=-1001234567890
ALERT_TOPIC_ID=123
START_ALERT=🤖 Bot started successfully
SHUTDOWN_ALERT=🛑 Bot stopped
TIMEZONE=Europe/Moscow

Auto-Close Tickets
AUTO_CLOSE_AFTER_HOURS=24

Backup Settings
BACKUP_ENABLED=true
BACKUP_FULL_PROJECT=false
BACKUP_SEND_TO_TELEGRAM=true
BACKUP_MAX_SIZE_MB=50

Spam Protection
FEEDBACK_COOLDOWN_ENABLED=true
FEEDBACK_COOLDOWN_HOURS=24
ASK_MIN_LENGTH=10

Error Monitoring
ERROR_ALERTS_ENABLED=true
ERROR_ALERT_THROTTLE_SEC=300


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

