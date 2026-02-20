# ARGSMS Telegram Bot

A Telegram bot for managing and viewing SMS ranges from the ARGSMS system.

## Features

- **Inline Menu Navigation**: Easy-to-use inline keyboard menus
- **User Management**: SQLite database with SQLAlchemy ORM
- **Admin Panel**: Special `/admin` command for administrators
- **Access Control**: Regular users can only access available SMS ranges
- **Pagination**: Navigate through multiple pages of SMS ranges
- **Access Logging**: Track user actions and statistics

## Installation

1. Clone the repository:
```bash
git clone https://github.com/meahmedrabbi/argsms.git
cd argsms
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
```

Edit `.env` and add your credentials:
```
LOGIN_USERNAME=your_username
PASSWORD=your_password
API_URL=http://217.182.195.194/ints/login
DEBUG_MODE=false
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```

To get a Telegram bot token:
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` and follow the instructions
3. Copy the token and add it to your `.env` file

## Usage

### Starting the Bot

Run the bot with:
```bash
python bot.py
```

The bot will:
- Initialize the SQLite database (`bot.db`)
- Connect to Telegram
- Start listening for commands

### User Commands

- `/start` - Show the main menu with available options
- `/admin` - Access admin panel (admin users only)

### Bot Features

#### For Regular Users:
- **View SMS Ranges**: Browse available SMS ranges with pagination
- **About**: Learn about the bot and available commands

#### For Administrators:
- **List Users**: View all registered bot users
- **Manage Admins**: Grant or revoke admin privileges
- **View Stats**: See bot usage statistics

### Making the First Admin

When the bot starts, the first user needs to be made an admin manually:

1. Start the bot and send `/start` to register yourself
2. Note your Telegram user ID from the bot logs
3. Access the database directly:

```bash
python -c "from database import init_db, User; db = init_db(); user = db.query(User).filter_by(telegram_id=YOUR_TELEGRAM_ID).first(); user.is_admin = True; db.commit(); print('Admin status granted')"
```

Replace `YOUR_TELEGRAM_ID` with your actual Telegram user ID.

Alternatively, you can use a database browser like DB Browser for SQLite to modify the `users` table.

## Database Schema

### Users Table
- `id`: Primary key
- `telegram_id`: Unique Telegram user ID
- `username`: Telegram username (optional)
- `is_admin`: Boolean flag for admin status
- `created_at`: Timestamp of user registration

### Access Logs Table
- `id`: Primary key
- `user_id`: Foreign key to users table
- `timestamp`: Action timestamp
- `action`: Description of the action performed

## Project Structure

```
argsms/
├── bot.py                 # Main Telegram bot application
├── database.py            # SQLAlchemy models and database functions
├── scrapper.py            # Original web scrapper
├── scrapper_wrapper.py    # Wrapper for scrapper to use in bot
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
└── README.md             # This file
```

## Development

### Testing the Scrapper

You can test the web scrapper independently:

```bash
# View dashboard
python scrapper.py

# Get SMS ranges (formatted)
python scrapper.py --action sms-ranges

# Get SMS ranges (raw JSON)
python scrapper.py --action sms-ranges --json

# Get specific page
python scrapper.py --action sms-ranges --page 2 --max-results 50
```

## Security Notes

- The `.env` file contains sensitive credentials and should never be committed to version control
- Cookie files (`.cookies.pkl`) are stored with secure permissions (600)
- Admin privileges should be granted carefully
- The bot database (`bot.db`) is excluded from version control

## License

This project is provided as-is for educational and authorized use only.
