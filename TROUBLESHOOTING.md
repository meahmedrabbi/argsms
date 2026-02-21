# Troubleshooting Guide

This guide helps diagnose and fix common issues with the ARGSMS Telegram Bot.

## "Failed to retrieve SMS ranges" Error

### Symptoms
Users see the error message:
```
❌ Failed to retrieve SMS ranges.

This could be due to:
• API server is temporarily down
• Network connection issue
• Authentication failure

Please try again in a few moments. If the problem persists, contact the administrator.
```

### Diagnosis Steps

#### 1. Check Bot Logs
View the systemd service logs to see detailed error information:
```bash
# View recent logs
sudo journalctl -u argsms-bot -n 100

# Follow logs in real-time
sudo journalctl -u argsms-bot -f

# View logs for specific time period
sudo journalctl -u argsms-bot --since "10 minutes ago"
```

Look for specific error messages:
- `Authentication failed`: Credentials are invalid
- `Timeout`: Network or API server not responding
- `HTTP Status: 401/403`: Authentication/authorization issue
- `HTTP Status: 500/502/503`: API server error
- `Network error`: Connection problem

#### 2. Test API Connectivity
Test if the API server is reachable:
```bash
# Test basic connectivity
curl -I http://217.182.195.194/ints/login

# Should return HTTP 200 or redirect
```

#### 3. Verify Credentials
Check your `.env` file has correct credentials:
```bash
cd /path/to/argsms
cat .env | grep -E "LOGIN_USERNAME|PASSWORD|API_URL"
```

#### 4. Test Authentication Manually
Use the scrapper script to test authentication:
```bash
cd /path/to/argsms
python3 scrapper.py --action login
```

If login succeeds, test fetching ranges:
```bash
python3 scrapper.py --action sms-ranges --max-results 5
```

### Common Causes and Solutions

#### Cause 1: Invalid Credentials
**Symptoms:** Logs show "Authentication failed" or "Login failed"

**Solution:**
1. Verify credentials are correct in `.env` file
2. Try logging in manually via browser to confirm credentials work
3. Update `.env` with correct credentials
4. Restart the bot: `sudo systemctl restart argsms-bot`
5. Delete saved cookies: `rm .cookies.pkl`

#### Cause 2: API Server Down
**Symptoms:** 
- Logs show "Timeout" or "Network error"
- Cannot access API URL via curl/browser

**Solution:**
1. Wait for API server to come back online
2. Monitor API server status
3. The bot will automatically retry on next user request

#### Cause 3: Expired Session Cookies
**Symptoms:** Bot worked before but now fails, logs may show authentication issues

**Solution:**
1. Delete the cookies file: `rm .cookies.pkl`
2. Restart the bot: `sudo systemctl restart argsms-bot`
3. Bot will re-authenticate on next request

#### Cause 4: Network Issues
**Symptoms:** 
- Logs show "Request timed out after 15 seconds"
- Intermittent failures

**Solution:**
1. Check internet connectivity: `ping 217.182.195.194`
2. Check firewall rules allow outbound HTTP/HTTPS
3. If using proxy, configure it in the bot
4. Increase timeout values if network is slow (edit `scrapper.py`)

#### Cause 5: API Endpoint Changed
**Symptoms:** HTTP 404 errors in logs

**Solution:**
1. Verify API_URL in `.env` is correct
2. Check if API structure changed
3. Update endpoint URLs in `scrapper.py` if needed

### Prevention

#### Enable Debug Mode
Add detailed logging by setting DEBUG_MODE in `.env`:
```bash
DEBUG_MODE=true
```
Then restart: `sudo systemctl restart argsms-bot`

This will show:
- All API requests and responses
- Cookie details
- Form parsing details
- Detailed error messages

#### Monitor Bot Health
Set up monitoring to alert on failures:
```bash
# Check if bot is running
sudo systemctl status argsms-bot

# Set up alert on service failure (example with email)
sudo systemctl edit argsms-bot
```

Add to the override file:
```ini
[Unit]
OnFailure=status-email@%n.service
```

## Other Common Issues

### Bot Not Starting

#### Check Service Status
```bash
sudo systemctl status argsms-bot
```

#### View Startup Errors
```bash
sudo journalctl -u argsms-bot --since "5 minutes ago"
```

#### Common Causes:
1. Missing dependencies: `pip install -r requirements.txt`
2. Invalid .env file: Check syntax
3. Database migration issues: Delete `sms_bot.db` and restart
4. Port conflicts: Check if another process is using resources

### Database Errors

#### "no such column" Error
**Solution:** Database schema is outdated
```bash
# Backup old database
cp sms_bot.db sms_bot.db.backup

# Delete and let bot recreate
rm sms_bot.db

# Restart bot
sudo systemctl restart argsms-bot
```

The bot will automatically migrate old databases on startup.

### Permission Errors

#### "Permission denied" when accessing files
**Solution:**
```bash
# Fix ownership (replace 'botuser' with your user)
sudo chown -R botuser:botuser /path/to/argsms

# Fix permissions
chmod 644 /path/to/argsms/*.py
chmod 600 /path/to/argsms/.env
chmod 600 /path/to/argsms/.cookies.pkl
```

## Getting Help

If problems persist:

1. **Collect Information:**
   - Service status: `sudo systemctl status argsms-bot`
   - Recent logs: `sudo journalctl -u argsms-bot -n 200 > bot_logs.txt`
   - Configuration: `cat .env.example` (don't share actual .env!)

2. **Check Prerequisites:**
   - Python 3.7+ installed
   - All dependencies installed
   - Valid credentials
   - Network connectivity

3. **Report Issue:**
   - Include error messages from logs
   - Describe what you were trying to do
   - Include bot version/commit hash
   - Don't include sensitive credentials

## Quick Reference

### Useful Commands
```bash
# Restart bot
sudo systemctl restart argsms-bot

# View logs
sudo journalctl -u argsms-bot -f

# Check status
sudo systemctl status argsms-bot

# Test scrapper
cd /path/to/argsms && python3 scrapper.py --action sms-ranges

# Delete cookies
rm .cookies.pkl

# Enable debug mode
echo "DEBUG_MODE=true" >> .env
```

### Log File Locations
- **Systemd logs:** `sudo journalctl -u argsms-bot`
- **Cookie file:** `.cookies.pkl`
- **Database:** `sms_bot.db`
- **Config:** `.env`
