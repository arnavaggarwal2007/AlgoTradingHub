#!/bin/bash
# =============================================================================
# setup_digitalocean.sh  — Bootstrap a fresh Digital Ocean Ubuntu 22.04 droplet
#
# Usage:
#   scp scripts/setup_digitalocean.sh deploy@YOUR_DROPLET_IP:~/
#   ssh deploy@YOUR_DROPLET_IP "chmod +x setup_digitalocean.sh && ./setup_digitalocean.sh"
#
# Or run the one-liner from any machine with curl:
#   curl -sSL https://raw.githubusercontent.com/YOUR_REPO/main/scripts/setup_digitalocean.sh | bash
#
# What this script does:
#   1. Updates the system
#   2. Installs Python 3.11, Nginx, PostgreSQL, Redis, certbot
#   3. Creates a 'deploy' user with SSH key support
#   4. Clones your repo and installs Python dependencies
#   5. Creates systemd services for the Dash app and trading algo
#   6. Configures Nginx reverse proxy
#   7. Starts all services
# =============================================================================

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
REPO_URL="https://github.com/arnavaggarwal2007/AlgoTradingHub.git"
APP_DIR="/home/deploy/dashboard-prod"
APP_USER="deploy"
APP_PORT=8050
DOMAIN=""   # Set this to your domain, e.g. "app.yourdomain.com"

# ── Colors ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

# ── Must run as root (or with sudo) ───────────────────────────────────────────
[[ $EUID -ne 0 ]] && err "Run as root: sudo bash setup_digitalocean.sh"

# ── Prompt for domain if not set ──────────────────────────────────────────────
if [[ -z "$DOMAIN" ]]; then
    read -rp "Enter your app domain (e.g. app.yourdomain.com): " DOMAIN
fi

log "Starting Digital Ocean setup for domain: $DOMAIN"

# =============================================================================
# 1. System Update
# =============================================================================
log "Updating system packages…"
apt-get update -qq && apt-get upgrade -y -qq
apt-get install -y -qq \
    curl wget git vim htop \
    python3.11 python3.11-venv python3.11-dev \
    python3-pip \
    nginx \
    postgresql postgresql-contrib \
    redis-server \
    certbot python3-certbot-nginx \
    ufw \
    supervisor \
    build-essential libpq-dev

# =============================================================================
# 2. Firewall
# =============================================================================
log "Configuring UFW firewall…"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
log "Firewall enabled. Allowed: SSH + HTTP/HTTPS"

# =============================================================================
# 3. Create deploy user
# =============================================================================
if ! id "$APP_USER" &>/dev/null; then
    log "Creating user: $APP_USER"
    useradd -m -s /bin/bash "$APP_USER"
    usermod -aG sudo "$APP_USER"
    # Allow sudo without password for service management only
    echo "$APP_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart preswing-app, /bin/systemctl restart trading-algo" \
        > /etc/sudoers.d/$APP_USER
else
    warn "User $APP_USER already exists — skipping creation"
fi

# Copy root's authorized_keys to deploy user (if exists)
if [[ -f /root/.ssh/authorized_keys ]]; then
    mkdir -p /home/$APP_USER/.ssh
    cp /root/.ssh/authorized_keys /home/$APP_USER/.ssh/
    chown -R $APP_USER:$APP_USER /home/$APP_USER/.ssh
    chmod 700 /home/$APP_USER/.ssh
    chmod 600 /home/$APP_USER/.ssh/authorized_keys
    log "SSH keys copied to $APP_USER"
fi

# =============================================================================
# 4. PostgreSQL setup
# =============================================================================
log "Setting up PostgreSQL…"
systemctl enable --now postgresql

sudo -u postgres psql -c "CREATE USER dashapp WITH PASSWORD 'changeme_strong_password';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE dashappdb OWNER dashapp;" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE dashappdb TO dashapp;" 2>/dev/null || true
log "PostgreSQL: database 'dashappdb' ready"

# =============================================================================
# 5. Redis
# =============================================================================
log "Enabling Redis…"
systemctl enable --now redis-server

# =============================================================================
# 6. Clone repo + create .venv
# =============================================================================
log "Cloning repository as $APP_USER…"
sudo -u $APP_USER bash << EOF
set -e
mkdir -p ~/dashboard-prod
cd ~/dashboard-prod

# If already cloned, just pull
if [[ -d .git ]]; then
    git pull origin main
else
    git clone "$REPO_URL" .
fi

# Create Python virtual environment
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -r requirements.txt --quiet
echo "Python environment ready"
EOF

# =============================================================================
# 7. Create .env on server (skeleton — user must fill in secrets)
# =============================================================================
ENV_FILE="/home/$APP_USER/dashboard-prod/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    log "Creating .env skeleton at $ENV_FILE"
    cat > "$ENV_FILE" << 'ENVEOF'
# ── App ──────────────────────────────────────────────────────
FLASK_ENV=production
SECRET_KEY=CHANGE_THIS_TO_A_RANDOM_64_CHAR_STRING
DASHBOARD_URL=https://app.yourdomain.com

# ── Database ─────────────────────────────────────────────────
DATABASE_URL=postgresql://dashapp:changeme_strong_password@localhost/dashappdb

# ── Alpaca API ───────────────────────────────────────────────
APCA_API_KEY_ID=YOUR_ALPACA_KEY
APCA_API_SECRET_KEY=YOUR_ALPACA_SECRET

# ── OpenAI (for blog generation) ─────────────────────────────
OPENAI_API_KEY=sk-...

# ── WordPress ────────────────────────────────────────────────
WP_SITE_URL=https://yourdomain.com
WP_USERNAME=your_wp_username
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
WP_AUTHOR_ID=1
WP_POST_STATUS=publish

# ── Affiliate ────────────────────────────────────────────────
AFFILIATE_NAME=Interactive Brokers
AFFILIATE_URL=https://yourdomain.com/go/ibkr
ENVEOF
    chown $APP_USER:$APP_USER "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    warn "IMPORTANT: Edit $ENV_FILE and fill in your actual credentials!"
else
    warn ".env already exists — not overwriting"
fi

# =============================================================================
# 8. Nginx configuration
# =============================================================================
log "Configuring Nginx…"
cat > /etc/nginx/sites-available/preswing-app << NGINXEOF
server {
    listen 80;
    server_name $DOMAIN;

    # Redirect HTTP to HTTPS (certbot fills this in after SSL setup)
    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # WebSocket support (Dash uses long-polling)
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;

        # CORS for WordPress integration
        add_header Access-Control-Allow-Origin "https://yourdomain.com" always;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    }

    # Static files served directly by Nginx (faster)
    location /assets/ {
        proxy_pass http://127.0.0.1:$APP_PORT;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }
}
NGINXEOF

ln -sf /etc/nginx/sites-available/preswing-app /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default   # remove default site
nginx -t && systemctl reload nginx
log "Nginx configured"

# =============================================================================
# 9. Systemd service — Dash App
# =============================================================================
log "Creating systemd service: preswing-app…"
cat > /etc/systemd/system/preswing-app.service << SVCEOF
[Unit]
Description=Pre-Swing Trade Analysis Dashboard (Gunicorn)
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/gunicorn \
    --bind 127.0.0.1:$APP_PORT \
    --workers 2 \
    --timeout 120 \
    --keep-alive 5 \
    --log-level info \
    --access-logfile /var/log/preswing-access.log \
    --error-logfile /var/log/preswing-error.log \
    wsgi:server
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=preswing-app

[Install]
WantedBy=multi-user.target
SVCEOF

# =============================================================================
# 10. Systemd service — Trading Algo (market hours only via cron)
# =============================================================================
log "Creating systemd service: trading-algo…"
cat > /etc/systemd/system/trading-algo.service << SVCEOF
[Unit]
Description=Alpaca Trading Algorithm
After=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/python rajat_alpha_v67_single.py
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=trading-algo

[Install]
WantedBy=multi-user.target
SVCEOF

# =============================================================================
# 11. Cron jobs — auto-blog + market hours control
# =============================================================================
log "Setting up cron jobs…"
(crontab -u $APP_USER -l 2>/dev/null; cat << CRONEOF
# Auto-blog: publish on Tuesday (2) and Friday (5) at 9:00 AM EST (14:00 UTC)
0 14 * * 2,5 $APP_DIR/.venv/bin/python -m auto_blog.scheduler >> /var/log/auto_blog.log 2>&1

# Trading algo: start at 9:25 AM EST (14:25 UTC), stop at 4:05 PM EST (21:05 UTC) — weekdays only
25 14 * * 1-5 /bin/systemctl start trading-algo
5 21 * * 1-5 /bin/systemctl stop trading-algo
CRONEOF
) | crontab -u $APP_USER -
log "Cron jobs configured"

# =============================================================================
# 12. Enable and start services
# =============================================================================
log "Enabling services…"
systemctl daemon-reload
systemctl enable preswing-app
systemctl start preswing-app
log "preswing-app started"

# Note: trading-algo starts/stops via cron — don't start it now

# =============================================================================
# 13. SSL certificate (requires domain DNS to be pointing here)
# =============================================================================
warn "Skipping SSL setup — run manually after DNS propagation:"
warn "  sudo certbot --nginx -d $DOMAIN"
warn "  (DNS must point to this IP first. Takes up to 24 hours to propagate)"

# =============================================================================
# Done
# =============================================================================
echo ""
echo "============================================================"
log "Digital Ocean setup COMPLETE!"
echo "============================================================"
echo ""
echo "  Dashboard URL  : http://$DOMAIN (HTTP only until SSL setup)"
echo "  App directory  : $APP_DIR"
echo "  Dash service   : sudo systemctl status preswing-app"
echo "  View logs      : journalctl -u preswing-app -f"
echo ""
warn "Next steps:"
echo "  1. Edit $ENV_FILE with your real credentials"
echo "  2. Point DNS A record ($DOMAIN) to this IP: $(curl -s ipinfo.io/ip)"
echo "  3. Wait for DNS propagation, then run: sudo certbot --nginx -d $DOMAIN"
echo "  4. Test deployment: curl https://$DOMAIN"
echo ""
