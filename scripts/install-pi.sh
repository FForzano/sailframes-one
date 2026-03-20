#!/bin/bash
#
# SailFrames Pi Installation Script
# Installs sync scripts and configures automatic uploads
#
# Usage:
#   sudo ./install-pi.sh
#

set -e

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo $0"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing SailFrames sync components..."

# Create directories
mkdir -p /var/log/sailframes
mkdir -p /var/lib/sailframes
mkdir -p /etc/sailframes

# Install sync script
echo "Installing sync script..."
cp "$SCRIPT_DIR/sailframes-sync.sh" /usr/local/bin/
chmod +x /usr/local/bin/sailframes-sync.sh

# Install systemd units
echo "Installing systemd units..."
cp "$SCRIPT_DIR/sailframes-sync.service" /etc/systemd/system/
cp "$SCRIPT_DIR/sailframes-sync.timer" /etc/systemd/system/

# Install NetworkManager hook
echo "Installing NetworkManager hook..."
if [ -d /etc/NetworkManager/dispatcher.d ]; then
    cp "$SCRIPT_DIR/99-sailframes-sync" /etc/NetworkManager/dispatcher.d/
    chmod +x /etc/NetworkManager/dispatcher.d/99-sailframes-sync
fi

# Reload systemd
systemctl daemon-reload

# Enable timer
echo "Enabling sync timer..."
systemctl enable sailframes-sync.timer
systemctl start sailframes-sync.timer

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Configure AWS credentials:"
echo "   aws configure"
echo ""
echo "2. Test sync manually:"
echo "   /usr/local/bin/sailframes-sync.sh"
echo ""
echo "3. Check timer status:"
echo "   systemctl status sailframes-sync.timer"
echo ""
