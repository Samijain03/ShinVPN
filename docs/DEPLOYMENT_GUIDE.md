# 🚀 ShinVPN Deployment Guide
*Delusional Club Industries Production & VPS Guide*

---

## 1. Automated VPS Setup (Ubuntu / Debian)

On any fresh Linux VPS:
```bash
git clone https://github.com/DelusionalClub/ShinVPN.git
cd ShinVPN
sudo bash scripts/deploy-vps.sh
```

The script will automatically configure kernel IP forwarding, set up iptables NAT, configure a systemd service, and generate `client.json`.

---

## 2. Docker Compose Deployment

If you prefer containerized deployment:
```bash
cd ShinVPN/docker
docker compose up -d --build
```

---

## 3. Manual Server Configuration

### Enable IP Forwarding:
```bash
sudo sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
```

### Configure IPTables NAT:
```bash
# Replace eth0 with your public network interface
sudo iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -o eth0 -j MASQUERADE
sudo iptables -A FORWARD -s 10.8.0.0/24 -j ACCEPT
sudo iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
```

### Run ShinVPN Server:
```bash
python -m shinvpn.cli.main server --config server.json
```

---

## 4. Connecting from Windows Client

1. Copy `client.json` from the server to your local machine (or enter the server's public key into the GUI).
2. Launch the Cyberpunk Desktop GUI:
   ```cmd
   scripts\run-gui.bat
   ```
3. Click the glowing center **CONNECT** button!
