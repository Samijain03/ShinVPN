#!/usr/bin/env bash
# ==============================================================================
# ShinVPN 1-Click Linux VPS Installer & Deployer
# Delusional Club Industries
# ==============================================================================

set -e

CYAN='\033[0;36m'
PURPLE='\033[0;35m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${PURPLE}"
echo "============================================================"
echo "    SHINVPN SERVER INSTALLER — DELUSIONAL CLUB INDUSTRIES   "
echo "============================================================"
echo -e "${NC}"

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Error: Please run this script as root (sudo ./deploy-vps.sh)${NC}"
  exit 1
fi

# Detect Public IP
PUBLIC_IP=$(curl -s -4 https://ifconfig.me || curl -s -4 https://api.ipify.org || echo "YOUR_SERVER_IP")
DEFAULT_IFACE=$(ip route show default | awk '{print $5}' | head -n1)

echo -e "${CYAN}[1/5] Detected Public IP: ${PUBLIC_IP} (Interface: ${DEFAULT_IFACE})${NC}"

# Update & Install dependencies
echo -e "${CYAN}[2/5] Installing system packages (python3, pip, iptables, iproute2)...${NC}"
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv iptables iproute2 curl git

# Enable IPv4 Forwarding
echo -e "${CYAN}[3/5] Enabling IPv4 Kernel Packet Forwarding...${NC}"
sysctl -w net.ipv4.ip_forward=1
if ! grep -q "^net.ipv4.ip_forward=1" /etc/sysctl.conf; then
  echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
fi

# Configure NAT Forwarding
echo -e "${CYAN}[4/5] Setting up iptables NAT Masquerade...${NC}"
iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -o "$DEFAULT_IFACE" -j MASQUERADE
iptables -A FORWARD -s 10.8.0.0/24 -j ACCEPT
iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT

# Save iptables rules
if command -v iptables-save >/dev/null; then
  mkdir -p /etc/iptables
  iptables-save > /etc/iptables/rules.v4
fi

# Install ShinVPN
INSTALL_DIR="/opt/shinvpn"
echo -e "${CYAN}[5/5] Deploying ShinVPN into ${INSTALL_DIR}...${NC}"
mkdir -p "$INSTALL_DIR"

if [ -d "./shinvpn" ]; then
  cp -r . "$INSTALL_DIR/"
else
  git clone https://github.com/DelusionalClub/ShinVPN.git "$INSTALL_DIR" || true
fi

cd "$INSTALL_DIR"
python3 -m venv venv
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q
venv/bin/pip install -e . -q

# Generate Profiles
venv/bin/shinvpn init-profiles

# Setup Systemd Service
cat <<EOF > /etc/systemd/system/shinvpn-server.service
[Unit]
Description=ShinVPN Server Daemon by Delusional Club Industries
After=network.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/shinvpn server --config ${INSTALL_DIR}/server.json
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable shinvpn-server
systemctl restart shinvpn-server

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}✔ ShinVPN Server successfully deployed and active!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "Server Public IP: ${YELLOW}${PUBLIC_IP}${NC}"
echo -e "UDP Port:        ${YELLOW}51820${NC}"
echo -e "Stealth Port:    ${YELLOW}8443${NC}"
echo ""
echo -e "${CYAN}Client Profile created at:${NC} ${INSTALL_DIR}/client.json"
echo -e "${PURPLE}To view server logs:${NC} journalctl -u shinvpn-server -f"
echo ""
