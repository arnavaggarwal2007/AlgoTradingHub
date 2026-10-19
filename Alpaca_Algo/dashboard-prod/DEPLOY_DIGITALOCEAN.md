# Deploy to Digital Ocean — Complete Production Guide

**Cost:** $5-12/month | **Setup Time:** 30 minutes | **Uptime:** 99.99%

> This is Part 1 of the Hybrid Architecture.
> Part 2 (Hostinger WordPress site) → see DEPLOY_HOSTINGER_WORDPRESS.md

---

## Architecture Overview

```
yourdomain.com               →  Hostinger WordPress (marketing)
app.yourdomain.com           →  Digital Ocean (Dash dashboard)
api.yourdomain.com           →  Digital Ocean (JSON API)
blog.yourdomain.com          →  Hostinger WordPress blog
```

---

## Step 1: Create Digital Ocean Account + Droplet

1. Go to **[digitalocean.com](https://digitalocean.com)** and create an account
2. In the top-right: **Create** → **Droplets**
3. Choose settings:

| Setting | Value |
|---------|-------|
| Image | Ubuntu 22.04 LTS |
| Plan | **Basic — Regular / 2GB RAM / 50GB SSD** ($12/mo) |
| Datacenter | Choose closest to your users (NYC, SFO, London, etc.) |
| Authentication | **SSH Key** (more secure) or Password |
| Hostname | `preswing-dashboard` |

4. Click **Create Droplet**
5. Note your Droplet IP: `xxx.xxx.xxx.xxx`

---

## Step 2: Connect VS Code to Your Droplet (Remote SSH)

**Install the extension:**
1. Open VS Code → Extensions (Ctrl+Shift+X)
2. Search: **Remote - SSH** by Microsoft
3. Install

**Connect:**
1. Press `Ctrl+Shift+P` → type: **Remote-SSH: Connect to Host**
2. Enter: `root@xxx.xxx.xxx.xxx` (your Droplet IP)
3. First time: Accept SSH fingerprint
4. VS Code now **runs on your Droplet** — you can edit files directly!

From this point you can open your project folder on the server in VS Code exactly like a local folder.

---

## Step 3: Initial Server Setup

Once connected via SSH (either VS Code Terminal or PuTTY):

```bash
# Update system
apt-get update -y && apt-get upgrade -y

# Install Python 3.13 and tools
add-apt-repository ppa:deadsnakes/ppa -y
apt-get update -y
apt-get install -y python3.13 python3.13-venv python3-pip \
    git nginx certbot python3-certbot-nginx \
    postgresql postgresql-contrib redis-server \
    supervisor htop curl wget ufw

# Create non-root deploy user (security best practice)
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy

# Set up firewall
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
```

---

## Step 4: Configure PostgreSQL Database

```bash
service postgresql start
systemctl enable postgresql

sudo -u postgres psql << 'EOF'
CREATE DATABASE preswing_prod;
CREATE USER preswing_user WITH PASSWORD 'CHANGE_THIS_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE preswing_prod TO preswing_user;
ALTER DATABASE preswing_prod OWNER TO preswing_user;
\q
EOF
```

---

## Step 5: Deploy the Dash Application

```bash
# Switch to deploy user
su - deploy

# Clone from GitHub
git clone https://github.com/arnavaggarwal2007/AlgoTradingHub.git
cd AlgoTradingHub/dashboard-prod

# Create Python virtual environment
python3.13 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Set up environment
cp .env.example .env
nano .env
```

**Minimum .env values:**
```
FLASK_ENV=production
DEBUG=False
SECRET_KEY=GENERATE_WITH: openssl rand -hex 32
DATABASE_URL=postgresql://preswing_user:YOUR_PASSWORD@localhost:5432/preswing_prod
PORT=8000
DOMAIN=app.yourdomain.com
```

---

## Step 6: Configure Nginx (Reverse Proxy)

```bash
# Exit deploy user back to root
exit

# Create Nginx config
cat > /etc/nginx/sites-available/preswing-app << 'NGINX'
server {
    listen 80;
    server_name app.yourdomain.com api.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name app.yourdomain.com api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/app.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Allow requests from your WordPress domain
    add_header Access-Control-Allow-Origin "https://yourdomain.com" always;
    add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=app:10m rate=20r/s;
    limit_req zone=app burst=50 nodelay;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 120s;
    }

    # Serve static assets directly (faster)
    location /_dash-component-suites/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_cache_valid 200 30d;
        add_header Cache-Control "public, max-age=2592000, immutable";
    }

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript;
}
NGINX

ln -s /etc/nginx/sites-available/preswing-app /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx
```

---

## Step 7: SSL Certificate

```bash
certbot certonly --nginx \
    -d app.yourdomain.com \
    -d api.yourdomain.com \
    --non-interactive --agree-tos \
    --email your@email.com

# Auto-renew
systemctl enable certbot.timer
```

---

## Step 8: Create Systemd Service

```bash
cat > /etc/systemd/system/preswing-app.service << 'SERVICE'
[Unit]
Description=Pre-Swing Trade Dashboard (Gunicorn)
After=network.target postgresql.service redis.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/AlgoTradingHub/dashboard-prod
ExecStart=/home/deploy/AlgoTradingHub/dashboard-prod/venv/bin/gunicorn \
    -c gunicorn_config.py \
    wsgi:app
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
EnvironmentFile=/home/deploy/AlgoTradingHub/dashboard-prod/.env

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable preswing-app.service
systemctl start preswing-app.service
systemctl status preswing-app.service
```

---

## Step 9: Also Run Your Trading Algo 24/7

```bash
cat > /etc/systemd/system/trading-algo.service << 'SERVICE'
[Unit]
Description=Alpaca Trading Algorithm (rajat_alpha_v67_single)
After=network.target

[Service]
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/AlgoTradingHub/Single_Buy
ExecStart=/home/deploy/AlgoTradingHub/dashboard-prod/venv/bin/python \
    rajat_alpha_v67_single.py
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal
EnvironmentFile=/home/deploy/AlgoTradingHub/dashboard-prod/.env

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable trading-algo.service
# Start only during market hours (use cron instead):
# 0 9 * * 1-5 systemctl start trading-algo.service
# 0 16 * * 1-5 systemctl stop trading-algo.service
```

---

## Step 10: Verify Everything Works

```bash
# Check services
systemctl status preswing-app
systemctl status nginx
systemctl status postgresql

# Test the app endpoint
curl -I https://app.yourdomain.com
# Expected: HTTP/2 200

# Test API endpoint
curl https://api.yourdomain.com/api/v1/signals
# Expected: JSON response

# View logs
journalctl -u preswing-app -f
```

---

## Auto-Deploy on Git Push (CD Pipeline)

Create `/home/deploy/deploy.sh`:

```bash
#!/bin/bash
set -e
echo "Deploying to production..."
cd /home/deploy/AlgoTradingHub
git pull origin main
source dashboard-prod/venv/bin/activate
pip install -r dashboard-prod/requirements.txt -q
systemctl restart preswing-app
echo "Deploy complete!"
```

```bash
chmod +x /home/deploy/deploy.sh

# GitHub Actions can SSH in and run this:
# ssh deploy@YOUR_DO_IP '/home/deploy/deploy.sh'
```

---

## Resource Monitoring

```bash
# Install monitoring stack
apt-get install -y prometheus node-exporter

# Or use Netdata (beautiful real-time monitoring)
bash <(curl -Ss https://my-netdata.io/kickstart.sh)
# Access at: http://YOUR_DO_IP:19999
```

---

## Backups (Automated)

```bash
cat > /root/backup.sh << 'BACKUP'
#!/bin/bash
BACKUP_DIR="/root/backups/$(date +%Y-%m-%d)"
mkdir -p "$BACKUP_DIR"

# Database backup
PGPASSWORD="YOUR_DB_PASSWORD" pg_dump \
    -h localhost -U preswing_user preswing_prod \
    > "$BACKUP_DIR/database.sql"

# Application files backup
tar -czf "$BACKUP_DIR/app.tar.gz" \
    /home/deploy/AlgoTradingHub/dashboard-prod/.env \
    /home/deploy/AlgoTradingHub/Single_Buy/config/

# Clean up backups older than 30 days
find /root/backups -type d -mtime +30 -exec rm -rf {} + 2>/dev/null || true

echo "Backup complete: $BACKUP_DIR"
BACKUP

chmod +x /root/backup.sh
# Run daily at 2 AM
(crontab -l 2>/dev/null; echo "0 2 * * * /root/backup.sh >> /root/backup.log 2>&1") | crontab -
```
