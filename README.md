# ARGSMS Telegram Bot

A Telegram bot for managing and viewing SMS ranges from the ARGSMS system with advanced user management, balance tracking, and pricing features.

## Architecture

```
┌─────────────────┐
│  Telegram User  │
└────────┬────────┘
         │
         ├── /start → Main Menu (Inline Keyboard)
         │            ├── 📱 View SMS Ranges (with pagination & pricing)
         │            ├── 👤 My Profile (balance, stats)
         │            ├── 💰 Recharge Balance
         │            └── ℹ️ About
         │
         └── /admin → Admin Panel (Admin Only)
                      ├── 👥 List Users
                      ├── 🔑 Manage Admins
                      ├── 🚫 Ban/Unban Users
                      ├── 💰 Manage Balance
                      ├── 💳 Recharge Requests
                      ├── 💵 Set Price Ranges
                      └── 📊 View Stats
                      
┌──────────────────────────────────────────────────┐
│ Bot Components                                   │
├──────────────────────────────────────────────────┤
│ bot.py           → Telegram bot handlers         │
│ database.py      → SQLAlchemy models & functions │
│ scrapper_wrapper → SMS API integration           │
│ scrapper.py      → Web scrapper (existing)       │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│ Data Storage                                     │
├──────────────────────────────────────────────────┤
│ bot.db          → SQLite database                │
│  ├── users      → User info, balance, stats      │
│  ├── access_logs → Activity tracking             │
│  ├── number_holds → Phone number reservations    │
│  ├── price_ranges → SMS pricing configuration    │
│  ├── transactions → Balance history              │
│  └── recharge_requests → Pending recharges       │
└──────────────────────────────────────────────────┘
```

## Features

### User Features
- **Inline Menu Navigation**: Easy-to-use inline keyboard menus
- **User Balance System**: Track and manage account balance
- **User Profile**: View stats including balance, total spent, SMS received
- **Number Holding System**: Reserve SMS numbers temporarily (20 at a time)
- **Recharge Requests**: Request balance recharge from administrators
- **Force Channel Join**: Users must join a specified channel to use the bot

### Admin Features
- **User Management**: View and manage all bot users
- **Ban/Unban Users**: Control user access to the bot
- **Balance Management**: Add or deduct user balance via commands
- **Price Range Configuration**: Set SMS prices based on range patterns
- **Recharge Management**: View and process user recharge requests
- **Advanced Statistics**: Track usage, revenue, and user activity
- **Admin Assignment**: Grant or revoke admin privileges

### Technical Features
- **SMS Number Holding**: Temporary holds that auto-release after 5 minutes
- **Dynamic Pricing**: Pattern-based pricing for different SMS ranges
- **Balance Deduction**: Automatic charge when SMS is successfully received
- **Comprehensive Logging**: Track all user actions and transactions
- **Pagination**: Navigate through multiple pages of SMS ranges

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
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
API_URL=https://your-sms-api-url/login
DEBUG_MODE=false
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ADMIN_TELEGRAM_IDS=123456789,987654321
ADMIN_USERNAME=adminusername
FORCE_JOIN_CHANNEL_ID=@yourchannel
```

**Configuration Details:**
- `LOGIN_USERNAME`: Your SMS system username
- `PASSWORD`: Your SMS system password
- `API_URL`: The login URL for your SMS system
- `DEBUG_MODE`: Enable debug logging (true/false)
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from BotFather
- `ADMIN_TELEGRAM_IDS`: Comma-separated list of Telegram user IDs who should have admin access
- `ADMIN_USERNAME`: Telegram username (without @) for users to contact when requesting balance recharge
- `FORCE_JOIN_CHANNEL_ID`: Channel username (with @) that users must join to use the bot

To get a Telegram bot token:
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` and follow the instructions
3. Copy the token and add it to your `.env` file

To find your Telegram user ID:
1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. It will reply with your user ID
3. Add this ID to `ADMIN_TELEGRAM_IDS` in your `.env` file

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

All other features are accessed through the inline menu interface - no additional commands needed!

### Bot Features

#### For Regular Users:
- **View SMS Ranges**: Browse available SMS ranges as individual buttons with pagination
  - Each range is displayed as a clickable button with pricing information
  - Click any button to view detailed information about that range
  - Request 20 random phone numbers from any range
  - Numbers are temporarily held for you (auto-release after 5 minutes from first retry)
  - Navigate between pages with Previous/Next buttons
- **My Profile**: View your account statistics
  - User ID, username, join date
  - Current balance and total spent
  - Total SMS received count
  - Number of held numbers
- **Recharge Balance**: Request balance recharge from administrators
- **Phone Number Search**: Send any phone number to check for SMS messages
  - Only held numbers can be searched
  - Balance is automatically deducted when SMS is found
  - Numbers with successful SMS are permanently held
- **About**: Learn about the bot and available commands

#### For Administrators:
- **List Users**: View all registered bot users with balance info
- **Manage Admins**: Grant or revoke admin privileges through interactive menu
- **Ban/Unban Users**: Control user access through interactive menu
- **Manage Balance**: Add or deduct balance from user accounts through interactive menu
  - Select user from list
  - Choose add or deduct
  - Enter amount via message
- **Recharge Requests**: View pending recharge requests
- **Set Price Ranges**: Configure SMS prices based on range patterns through interactive menu
  - Click "Add Price Range"
  - Enter pattern (e.g., "russia")
  - Enter price (e.g., "2.5")
- **View Stats**: See comprehensive bot statistics
  - User counts (total, admins, banned)
  - Financial stats (total balance, total spent)
  - SMS statistics (total received)
  - Number holds (active, permanent)

**All admin operations are done through the inline menu interface!**

### Setting Up Admins

There are two ways to make users admins:

#### Option 1: Configure Admin IDs in Environment (Recommended)

Add admin Telegram user IDs to your `.env` file:
```
ADMIN_TELEGRAM_IDS=123456789,987654321
```

To find your Telegram user ID:
1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. It will reply with your user ID
3. Add this ID to `ADMIN_TELEGRAM_IDS` in your `.env` file

#### Option 2: Grant Admin Status via Database

Use the `make_admin.py` helper script:
```bash
# List all users
python make_admin.py --list

# Make a specific user admin
python make_admin.py <telegram_user_id>
```

Note: Users configured in the environment via `ADMIN_TELEGRAM_IDS` have permanent admin access. Users made admin via the database can have their admin status revoked through the bot's admin panel.

## How the System Works

### Number Holding System

The bot implements a smart number holding mechanism to prevent conflicts:

1. **Requesting Numbers**: When you click "View Numbers" for a range, the bot:
   - Checks if you have sufficient balance
   - Fetches 100 numbers from the API
   - Filters out numbers already held by other users
   - Randomly selects 20 available numbers
   - Creates temporary holds for you

2. **Temporary Holds**: Numbers you request are held temporarily:
   - Other users cannot request the same numbers
   - Holds last indefinitely until you start searching
   - When you search a number for the first time, a 5-minute timer starts
   - After 5 minutes from first search, unsearched numbers are released

3. **Permanent Holds**: When you successfully receive an SMS:
   - The number becomes permanently held by you
   - Balance is deducted based on the range price
   - The number cannot be released or used by others
   - Your `total_sms_received` counter increases

4. **Requesting New Numbers**: When you request new numbers:
   - All your temporary (non-permanent) holds are released
   - This frees them up for other users
   - Your permanent holds remain unchanged

### Pricing System

Administrators can set different prices for different SMS ranges:

1. **Pattern-Based Pricing**: Prices are matched by patterns
   - Example: `/setprice russia 2.5` sets $2.50 for ranges containing "russia"
   - Patterns are case-insensitive
   - Most recently created pattern takes precedence

2. **Default Price**: If no pattern matches, default price is $1.00

3. **Balance Deduction**: 
   - Price is shown when requesting numbers
   - Balance is checked before showing numbers
   - Deduction happens only when SMS is successfully received
   - Transaction is logged in the database

### Channel Join Requirement

If configured, users must join a specified channel to use the bot:
- Set `FORCE_JOIN_CHANNEL_ID` in `.env` (e.g., `@yourchannel`)
- Users who haven't joined see a join prompt
- After joining, they can access all features
- Admins bypass this requirement

## Database Schema

### Users Table
- `id`: Primary key
- `telegram_id`: Unique Telegram user ID
- `username`: Telegram username (optional)
- `is_admin`: Boolean flag for admin status
- `is_banned`: Boolean flag for banned status
- `balance`: User account balance (Float)
- `total_spent`: Total amount spent on SMS (Float)
- `total_sms_received`: Count of successfully received SMS (Integer)
- `created_at`: Timestamp of user registration

### Access Logs Table
- `id`: Primary key
- `user_id`: Foreign key to users table
- `timestamp`: Action timestamp
- `action`: Description of the action performed

### Number Holds Table
- `id`: Primary key
- `user_id`: Foreign key to users table
- `phone_number`: Held phone number
- `range_id`: SMS range identifier
- `hold_start_time`: When the hold was created
- `first_retry_time`: When user first searched for SMS (starts 5-min timer)
- `is_permanent`: Whether hold is permanent (SMS received)

### Price Ranges Table
- `id`: Primary key
- `range_pattern`: Pattern to match range names (e.g., "russia", "usa")
- `price`: Price per SMS for matching ranges
- `created_by`: Admin user ID who created the price
- `created_at`: Creation timestamp

### Transactions Table
- `id`: Primary key
- `user_id`: Foreign key to users table
- `amount`: Transaction amount (positive for credit, negative for debit)
- `transaction_type`: Type of transaction (recharge, sms_charge, admin_add, admin_deduct)
- `description`: Transaction description
- `created_at`: Transaction timestamp

### Recharge Requests Table
- `id`: Primary key
- `user_id`: Foreign key to users table
- `amount`: Requested recharge amount
- `status`: Request status (pending, approved, rejected)
- `admin_note`: Optional note from admin
- `created_at`: Request creation timestamp
- `processed_at`: When request was processed
- `processed_by`: Admin user ID who processed the request

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
