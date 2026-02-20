# Quick Start Guide for ARGSMS Telegram Bot

This guide will help you get the bot running in 5 minutes.

## Prerequisites

- Python 3.7 or higher
- A Telegram account
- Access to the SMS management system

## Step 1: Get Your Telegram Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow the prompts to name your bot
4. Copy the bot token (looks like: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

## Step 2: Get Your Telegram User ID

1. Open Telegram and search for [@userinfobot](https://t.me/userinfobot)
2. Start a chat with it
3. It will reply with your user ID (a number like: `123456789`)

## Step 3: Setup the Bot

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env file with your credentials
nano .env  # or use your preferred editor
```

In the `.env` file, set:
```
LOGIN_USERNAME=your_sms_system_username
PASSWORD=your_sms_system_password
API_URL=your_sms_api_login_url
TELEGRAM_BOT_TOKEN=your_bot_token_from_step_1
ADMIN_TELEGRAM_IDS=your_user_id_from_step_2
FORCE_JOIN_CHANNEL_ID=@yourchannel (optional)
```

**Important Configuration Notes:**
- `FORCE_JOIN_CHANNEL_ID` is optional. If set, users must join that channel to use the bot.
- To find a channel ID, go to the channel and look at its username (starts with @).
- Multiple admin IDs can be comma-separated: `123456789,987654321`

## Step 4: Run the Bot

```bash
python bot.py
```

You should see:
```
INFO - Starting ARGSMS Telegram Bot...
```

## Step 5: Use the Bot

1. Open Telegram and search for your bot (the name you created in Step 1)
2. Send `/start` to begin
3. Use the inline menu to navigate

**As a regular user:**
- View SMS ranges and request numbers
- Check your profile for balance and stats
- Request balance recharge
- Search phone numbers for SMS

**As an admin:**
- Use `/admin` to access the admin panel
- Manage users (ban/unban)
- Manage balance with `/addbalance` and `/deductbalance` commands
- Set price ranges with `/setprice` command
- View comprehensive statistics

## Initial Setup for Admins

After starting the bot for the first time:

1. **Set Default Prices**: Use `/setprice default 1.0` to set a default price
2. **Add Specific Prices**: Use `/setprice russia 2.5` for country-specific pricing
3. **Add Initial Balance**: Give yourself some test balance with `/addbalance <your_id> 100`

## Troubleshooting

**Bot doesn't start:**
- Check that `TELEGRAM_BOT_TOKEN` is correct
- Ensure all required fields in `.env` are filled

**Can't access admin panel:**
- Verify your Telegram user ID is in `ADMIN_TELEGRAM_IDS`
- Check for typos in the user ID

**SMS ranges not loading:**
- Check `LOGIN_USERNAME`, `PASSWORD`, and `API_URL` are correct
- Enable `DEBUG_MODE=true` in `.env` to see detailed logs
- Run `python scrapper.py --action sms-ranges` to test the scrapper directly

## Next Steps

- Invite users to your bot
- Add more admin users by adding their IDs to `ADMIN_TELEGRAM_IDS` (comma-separated)
- Monitor bot usage through the admin panel statistics

For more details, see [README.md](README.md).
