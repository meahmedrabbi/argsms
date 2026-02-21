# Deployment Guide

## After Making Code Changes

When you update the bot code (bot.py, database.py, etc.), follow these steps to deploy the changes:

### 1. Clear Python Cache

Python caches compiled bytecode in `__pycache__` directories and `.pyc` files. After code changes, clear the cache:

```bash
# From your bot directory
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
find . -name "*.pyc" -delete
```

### 2. Restart the Systemd Service

If you're running the bot as a systemd service:

```bash
# Restart the service
sudo systemctl restart argsms-bot

# Check the status
sudo systemctl status argsms-bot

# View recent logs
sudo journalctl -u argsms-bot -n 50 --no-pager
```

### 3. Verify the Bot is Running

After restart, check that:
- Service status shows "active (running)"
- No errors in the logs
- Bot responds to /start command in Telegram

### 4. Monitor for Errors

Keep an eye on logs for the first few minutes:

```bash
# Follow logs in real-time
sudo journalctl -u argsms-bot -f
```

## Common Issues

### Bot Still Shows Old Errors

**Problem:** Code updated but bot still has old bugs

**Solution:**
1. Make sure you cleared Python cache (step 1 above)
2. Verify the service actually restarted:
   ```bash
   sudo systemctl status argsms-bot
   # Check "Active" timestamp - should be recent
   ```
3. Check if there are multiple bot processes running:
   ```bash
   ps aux | grep bot.py
   # Kill any duplicate processes
   ```

### Database Migration Not Applied

**Problem:** New database columns/tables not created

**Solution:**
The bot automatically runs migrations on startup. If you see errors about missing columns:

1. Stop the bot
2. Check database.py for the migrate_database() function
3. Restart the bot - migrations run in init_db()
4. Check logs for migration messages

### Service Won't Start

**Problem:** `systemctl start argsms-bot` fails

**Solution:**
1. Check service logs:
   ```bash
   sudo journalctl -u argsms-bot -n 100 --no-pager
   ```
2. Try running bot manually to see full error:
   ```bash
   cd /path/to/bot
   source venv/bin/activate
   python3 bot.py
   ```
3. Common issues:
   - Missing .env file
   - Wrong Python path in service file
   - Missing dependencies (run `pip install -r requirements.txt`)

## Quick Restart Script

Create a script `restart-bot.sh` for quick deployments:

```bash
#!/bin/bash
# Quick restart script for bot updates

echo "Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
find . -name "*.pyc" -delete

echo "Restarting service..."
sudo systemctl restart argsms-bot

echo "Waiting for service to start..."
sleep 2

echo "Service status:"
sudo systemctl status argsms-bot --no-pager -l

echo ""
echo "Recent logs:"
sudo journalctl -u argsms-bot -n 20 --no-pager
```

Make it executable:
```bash
chmod +x restart-bot.sh
```

Then use it after code changes:
```bash
./restart-bot.sh
```

## Development Mode

For testing changes without deploying to production:

1. Stop the production service:
   ```bash
   sudo systemctl stop argsms-bot
   ```

2. Run bot manually with debugging:
   ```bash
   cd /path/to/bot
   source venv/bin/activate
   export DEBUG_MODE=true
   python3 bot.py
   ```

3. Test your changes
4. Press Ctrl+C to stop
5. Restart production service when done

## Rollback

If you need to rollback to a previous version:

```bash
# View commit history
git log --oneline -n 10

# Rollback to specific commit
git checkout <commit-hash>

# Clear cache and restart
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
sudo systemctl restart argsms-bot
```

## Best Practices

1. **Test Locally First**: Always test changes in development before deploying
2. **Check Logs**: Monitor logs for at least 5 minutes after deployment
3. **Backup Database**: Before major changes, backup the SQLite database
4. **Clear Cache**: Always clear Python cache after code changes
5. **Version Control**: Commit all changes to git before deploying
