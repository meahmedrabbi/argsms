#!/bin/bash
# Installation script for ARGSMS Bot systemd service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}ARGSMS Bot Systemd Service Installation${NC}"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo "Please run: sudo ./install-service.sh"
    exit 1
fi

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SERVICE_FILE="$SCRIPT_DIR/argsms-bot.service"
SYSTEMD_DIR="/etc/systemd/system"

# Check if service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo -e "${RED}Error: Service file not found at $SERVICE_FILE${NC}"
    exit 1
fi

# Prompt for installation directory (default to current directory)
echo -e "${YELLOW}Installation Directory Configuration${NC}"
echo "Current script directory: $SCRIPT_DIR"
read -p "Enter bot installation directory (default: $SCRIPT_DIR): " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-$SCRIPT_DIR}

# Validate installation directory
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}Error: Directory $INSTALL_DIR does not exist${NC}"
    exit 1
fi

if [ ! -f "$INSTALL_DIR/bot.py" ]; then
    echo -e "${RED}Error: bot.py not found in $INSTALL_DIR${NC}"
    exit 1
fi

# Prompt for user (default to current user or root)
CURRENT_USER=${SUDO_USER:-$USER}
echo ""
echo -e "${YELLOW}User Configuration${NC}"
read -p "Enter user to run the bot (default: $CURRENT_USER): " BOT_USER
BOT_USER=${BOT_USER:-$CURRENT_USER}

# Check if user exists
if ! id "$BOT_USER" &>/dev/null; then
    echo -e "${RED}Error: User $BOT_USER does not exist${NC}"
    exit 1
fi

# Check for Python 3
PYTHON_PATH=$(which python3 2>/dev/null || echo "")
if [ -z "$PYTHON_PATH" ]; then
    echo -e "${RED}Error: python3 not found in PATH${NC}"
    exit 1
fi

# Check for virtual environment
VENV_PYTHON=""
if [ -f "$INSTALL_DIR/venv/bin/python" ]; then
    VENV_PYTHON="$INSTALL_DIR/venv/bin/python"
    echo -e "${GREEN}✓ Found virtual environment at $INSTALL_DIR/venv${NC}"
elif [ -f "$INSTALL_DIR/venv/bin/python3" ]; then
    VENV_PYTHON="$INSTALL_DIR/venv/bin/python3"
    echo -e "${GREEN}✓ Found virtual environment at $INSTALL_DIR/venv${NC}"
else
    echo -e "${YELLOW}⚠ Warning: No virtual environment found at $INSTALL_DIR/venv${NC}"
    echo "The service will use system Python, which may fail if dependencies are installed in a venv."
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        echo ""
        echo "To create a virtual environment:"
        echo "  cd $INSTALL_DIR"
        echo "  python3 -m venv venv"
        echo "  source venv/bin/activate"
        echo "  pip install -r requirements.txt"
        exit 0
    fi
fi

# Use venv Python if available, otherwise system Python
FINAL_PYTHON="${VENV_PYTHON:-$PYTHON_PATH}"
VENV_PATH_PREFIX=""
if [ -n "$VENV_PYTHON" ]; then
    VENV_PATH_PREFIX="$INSTALL_DIR/venv/bin:"
fi

echo ""
echo -e "${GREEN}Configuration Summary:${NC}"
echo "  Installation Directory: $INSTALL_DIR"
echo "  Bot User: $BOT_USER"
echo "  Python Path: $FINAL_PYTHON"
if [ -n "$VENV_PYTHON" ]; then
    echo "  Virtual Environment: Yes ($INSTALL_DIR/venv)"
else
    echo "  Virtual Environment: No (using system Python)"
fi
echo "  Service File: $SERVICE_FILE"
echo ""

read -p "Proceed with installation? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled."
    exit 0
fi

# Create temporary service file with updated paths
TEMP_SERVICE="/tmp/argsms-bot.service.tmp"
cat "$SERVICE_FILE" | \
    sed "s|User=.*|User=$BOT_USER|" | \
    sed "s|WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|" | \
    sed "s|Environment=\"PATH=.*|Environment=\"PATH=${VENV_PATH_PREFIX}/usr/local/bin:/usr/bin:/bin\"|" | \
    sed "s|ExecStart=.*|ExecStart=$FINAL_PYTHON $INSTALL_DIR/bot.py|" \
    > "$TEMP_SERVICE"

# Copy service file to systemd directory
echo ""
echo "Installing service file..."
cp "$TEMP_SERVICE" "$SYSTEMD_DIR/argsms-bot.service"
rm "$TEMP_SERVICE"

# Set proper permissions
chmod 644 "$SYSTEMD_DIR/argsms-bot.service"

# Reload systemd daemon
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable service
echo "Enabling service..."
systemctl enable argsms-bot.service

echo ""
echo -e "${GREEN}✓ Installation complete!${NC}"
echo ""
echo "Service Management Commands:"
echo "  Start service:   sudo systemctl start argsms-bot"
echo "  Stop service:    sudo systemctl stop argsms-bot"
echo "  Restart service: sudo systemctl restart argsms-bot"
echo "  Check status:    sudo systemctl status argsms-bot"
echo "  View logs:       sudo journalctl -u argsms-bot -f"
echo ""
echo "To start the service now, run:"
echo "  sudo systemctl start argsms-bot"
echo ""
