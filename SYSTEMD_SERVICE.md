# Systemd Service Guide for ARGSMS Bot

This guide explains how to set up and manage the ARGSMS Telegram bot as a systemd service on Linux systems.

## Why Use Systemd?

Running the bot as a systemd service provides several benefits:

- **Automatic Startup**: Bot starts automatically when the system boots
- **Auto-Restart**: Bot automatically restarts if it crashes
- **Process Management**: Easy start, stop, and restart operations
- **Logging**: Centralized logging through journalctl
- **Resource Control**: Ability to set resource limits
- **Security**: Run as non-root user with restricted permissions

## Prerequisites

- Linux system with systemd (Ubuntu 16.04+, Debian 8+, CentOS 7+, etc.)
- Root or sudo access
- Bot already installed and configured with `.env` file
- Python 3 and all dependencies installed
- **Virtual environment (venv) recommended** - The installation script will detect and use venv if present

### Setting Up Virtual Environment (Recommended)

Before installing the service, create and activate a virtual environment:

```bash
cd /path/to/argsms
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The installation script will automatically detect the venv and configure the service to use it.

## Quick Installation

### 1. Install the Service

Run the installation script:

```bash
sudo ./install-service.sh
```

The script will prompt you for:
- **Installation Directory**: Where your bot files are located (default: current directory)
- **User**: Which user should run the bot (default: current user)

Example:
```
ARGSMS Bot Systemd Service Installation
==========================================

Installation Directory Configuration
Current script directory: /home/myuser/argsms
Enter bot installation directory (default: /home/myuser/argsms): 

User Configuration
Enter user to run the bot (default: myuser): 

Configuration Summary:
  Installation Directory: /home/myuser/argsms
  Bot User: myuser
  Python Path: /usr/bin/python3
  Service File: /home/myuser/argsms/argsms-bot.service

Proceed with installation? (y/N): y
```

### 2. Start the Service

```bash
sudo systemctl start argsms-bot
```

### 3. Verify It's Running

```bash
sudo systemctl status argsms-bot
```

You should see:
```
● argsms-bot.service - ARGSMS Telegram Bot
   Loaded: loaded (/etc/systemd/system/argsms-bot.service; enabled; vendor preset: enabled)
   Active: active (running) since ...
```

## Service Management Commands

### Basic Operations

```bash
# Start the service
sudo systemctl start argsms-bot

# Stop the service
sudo systemctl stop argsms-bot

# Restart the service
sudo systemctl restart argsms-bot

# Check service status
sudo systemctl status argsms-bot

# Enable service (auto-start on boot)
sudo systemctl enable argsms-bot

# Disable service (don't auto-start on boot)
sudo systemctl disable argsms-bot
```

### Viewing Logs

```bash
# View real-time logs (follow mode)
sudo journalctl -u argsms-bot -f

# View all logs
sudo journalctl -u argsms-bot

# View logs from today
sudo journalctl -u argsms-bot --since today

# View logs from last hour
sudo journalctl -u argsms-bot --since "1 hour ago"

# View last 100 lines
sudo journalctl -u argsms-bot -n 100

# View logs with specific priority (errors only)
sudo journalctl -u argsms-bot -p err
```

### Checking Service Status

```bash
# Detailed status
sudo systemctl status argsms-bot

# Check if service is active
systemctl is-active argsms-bot

# Check if service is enabled
systemctl is-enabled argsms-bot

# View service configuration
systemctl cat argsms-bot
```

## Configuration

### Service File Location

After installation, the service file is located at:
```
/etc/systemd/system/argsms-bot.service
```

### Manual Configuration

If you need to manually edit the service file:

1. Edit the file:
```bash
sudo nano /etc/systemd/system/argsms-bot.service
```

2. Reload systemd:
```bash
sudo systemctl daemon-reload
```

3. Restart the service:
```bash
sudo systemctl restart argsms-bot
```

### Service File Parameters

Key parameters in the service file:

- **User**: User account that runs the bot
- **WorkingDirectory**: Bot installation directory
- **ExecStart**: Command to start the bot
- **Restart=always**: Automatically restart on failure
- **RestartSec=10**: Wait 10 seconds before restarting
- **StandardOutput=journal**: Send logs to systemd journal

## Troubleshooting

### Service Won't Start

1. Check the service status:
```bash
sudo systemctl status argsms-bot
```

2. View recent logs:
```bash
sudo journalctl -u argsms-bot -n 50
```

3. Common issues:
   - **Permission denied**: Check file permissions and user settings
   - **Python not found**: Verify Python path in service file
   - **Module not found**: Ensure all dependencies are installed for the service user
   - **.env file missing**: Verify `.env` file exists in WorkingDirectory
   - **Virtual environment not used**: Service must use venv Python if dependencies are in venv

### Module Not Found / Import Errors

If you see errors like "ModuleNotFoundError" or "No module named 'X'":

**Cause**: The service is using system Python but dependencies are installed in a virtual environment.

**Solution**: Reinstall the service to use the virtual environment:

```bash
# Stop and remove the service
sudo ./uninstall-service.sh

# Verify virtual environment exists and has dependencies
ls -la venv/bin/python
source venv/bin/activate
pip list | grep telegram  # Verify dependencies are installed

# Reinstall the service (it will detect the venv)
sudo ./install-service.sh

# Start the service
sudo systemctl start argsms-bot
```

Alternatively, manually edit the service file to use venv Python:

```bash
sudo nano /etc/systemd/system/argsms-bot.service

# Change ExecStart line to:
ExecStart=/path/to/argsms/venv/bin/python /path/to/argsms/bot.py

# Change Environment PATH to include venv:
Environment="PATH=/path/to/argsms/venv/bin:/usr/local/bin:/usr/bin:/bin"

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart argsms-bot
```

### Logs Not Showing

If logs don't appear in journalctl:

```bash
# Check if journal is running
sudo systemctl status systemd-journald

# Verify log storage
sudo journalctl --disk-usage
```

### Service Keeps Restarting

1. Check for errors in logs:
```bash
sudo journalctl -u argsms-bot -f
```

2. Test bot manually:
```bash
cd /path/to/bot
python3 bot.py
```

3. Check .env configuration

### Permission Issues

If running as non-root user, ensure the user has:
- Read access to bot files
- Write access to database directory
- Execute permission on Python scripts

Fix permissions:
```bash
sudo chown -R username:username /path/to/bot
sudo chmod +x /path/to/bot/bot.py
```

## Advanced Configuration

### Environment Variables

Add environment variables in the service file:

```ini
[Service]
Environment="DEBUG_MODE=true"
Environment="CUSTOM_VAR=value"
```

Or use an environment file:

```ini
[Service]
EnvironmentFile=/path/to/bot/.env
```

### Resource Limits

Limit CPU and memory usage:

```ini
[Service]
CPUQuota=50%
MemoryLimit=512M
```

### Running as Specific User

Always recommended for security:

```ini
[Service]
User=botuser
Group=botuser
```

### Notifications

Get notified on service failures:

```ini
[Service]
OnFailure=status-email@%n.service
```

## Uninstallation

To remove the service:

```bash
sudo ./uninstall-service.sh
```

This will:
1. Stop the service
2. Disable the service
3. Remove the service file
4. Reload systemd

Your bot files and data remain unchanged.

## Manual Uninstallation

If the script doesn't work:

```bash
# Stop the service
sudo systemctl stop argsms-bot

# Disable the service
sudo systemctl disable argsms-bot

# Remove service file
sudo rm /etc/systemd/system/argsms-bot.service

# Reload systemd
sudo systemctl daemon-reload
sudo systemctl reset-failed
```

## Best Practices

1. **Security**:
   - Run as non-root user
   - Use restrictive file permissions
   - Keep .env file readable only by service user

2. **Monitoring**:
   - Regularly check service status
   - Monitor logs for errors
   - Set up log rotation if needed

3. **Updates**:
   - Stop service before updating bot files
   - Test changes manually before restarting service
   - Keep backups of working configurations

4. **Maintenance**:
   - Review logs periodically
   - Clean old journal logs: `sudo journalctl --vacuum-time=7d`
   - Update Python dependencies regularly

## Integration with Other Tools

### Systemd Timer (Cron Alternative)

For scheduled tasks, create a timer unit instead of using cron.

### Monitoring with Nagios/Zabbix

Monitor service status:
```bash
systemctl is-active argsms-bot
```

### Docker Alternative

If using Docker, consider the systemd approach for native installations.

## Support

If you encounter issues:

1. Check logs: `sudo journalctl -u argsms-bot -n 100`
2. Verify configuration: `systemctl cat argsms-bot`
3. Test manually: `python3 /path/to/bot/bot.py`
4. Check file permissions and user access
5. Review the README.md for bot-specific issues

## Additional Resources

- [systemd Documentation](https://www.freedesktop.org/software/systemd/man/)
- [journalctl Manual](https://www.freedesktop.org/software/systemd/man/journalctl.html)
- [systemd Service Units](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
