#!/bin/bash
# Uninstallation script for ARGSMS Bot systemd service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}ARGSMS Bot Systemd Service Uninstallation${NC}"
echo "============================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo "Please run: sudo ./uninstall-service.sh"
    exit 1
fi

SERVICE_NAME="argsms-bot.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"

# Check if service exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo -e "${YELLOW}Warning: Service file not found at $SERVICE_FILE${NC}"
    echo "Service may already be uninstalled."
    exit 0
fi

echo "This will:"
echo "  1. Stop the service if running"
echo "  2. Disable the service"
echo "  3. Remove the service file"
echo ""

read -p "Proceed with uninstallation? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

# Stop the service if it's running
echo ""
echo "Stopping service..."
if systemctl is-active --quiet argsms-bot; then
    systemctl stop argsms-bot
    echo "Service stopped."
else
    echo "Service was not running."
fi

# Disable the service
echo "Disabling service..."
if systemctl is-enabled --quiet argsms-bot 2>/dev/null; then
    systemctl disable argsms-bot
    echo "Service disabled."
else
    echo "Service was not enabled."
fi

# Remove service file
echo "Removing service file..."
rm -f "$SERVICE_FILE"

# Reload systemd daemon
echo "Reloading systemd daemon..."
systemctl daemon-reload
systemctl reset-failed 2>/dev/null || true

echo ""
echo -e "${GREEN}✓ Uninstallation complete!${NC}"
echo ""
echo "The service has been removed from your system."
echo "Your bot files and data remain unchanged."
echo ""
