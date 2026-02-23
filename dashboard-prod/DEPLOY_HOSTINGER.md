# Deploy to Hostinger VPS — Step-by-Step Guide

**Cost:** $10-20/month | **Setup Time:** 30-45 minutes | **Uptime:** 99.9%

---

## Prerequisites

1. **Hostinger Business VPS** plan (or higher) — at least 2GB RAM
2. **Domain name** — registered with Hostinger or any registrar
3. **SSH client** — PuTTY (Windows) or Terminal (Mac/Linux)
4. **Git** — installed on your local machine

---

## Step 1: Set Up Your Hostinger VPS

### 1.1 Log into Hostinger
1. Go to [Hostinger.com](https://hostinger.com) → My Accounts
2. Click **Hosting** → Select your Business VPS plan
3. Click **Manage** → **Advanced** → **SSH Access**

### 1.2 Enable SSH Access
1. Click **Change SSH Password**
2. Copy your **SSH Username**, **SSH Host**, and **SSH Port** (usually 22)
3. Note them down:
   ```
   SSH Host: abc123.hostinger.com
   SSH Port: 22
   SSH User: root (or hpanel-xxxxxxx)
   SSH Password: [your password]
   ```

### 1.3 Connect via SSH
**On Windows (PuTTY):**
- Download [PuTTY](https://www.putty.org/)
- Host: `abc123.hostinger.com`, Port: `22`
- Username: `root`, Password: [your SSH password]
- Click **Open**

**On Mac/Linux:**
```bash
ssh root@abc123.hostinger.com -p 22
```

---

## Step 2: Install System Dependencies

Once connected via SSH, run:

```bash
# Update package manager
apt-get update -y
apt-get upgrade -y

# Install Python 3.13, pip, virtualenv
apt-get install -y python3.13 python3-pip python3-venv

# Install system libraries for technical analysis
apt-get install -y git curl wget nginx supervisor postgresql postgresql-contrib

# Verify Python
python3.13 --version
# Output: Python 3.13.12 (or similar)
```

---

## Step 3: Clone Your Dashboard Repository

```bash
# Navigate to web root
cd /home/yourusername/public_html  # or /var/www/html

# Clone the dashboard repo
git clone https://github.com/yourusername/dashboard-prod.git
cd dashboard-prod

# Create virtual environment
python3.13 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
pip install -r requirements.txt
```

---

## Step 4: Configure Environment Variables

Create a `.env` file in the `dashboard-prod` directory:

```bash
cat > .env << 'EOF'
# Application
FLASK_ENV=production
SECRET_KEY=your-secret-key-generate-with-openssl
DEBUG=False

# Database
DATABASE_URL=sqlite:///./app.db
# Or PostgreSQL (recommended for production):
# DATABASE_URL=postgresql://user:password@localhost:5432/dashboard_db

# Data
DATA_PERIOD=2y
FETCH_TIMEOUT_SECONDS=20
MAX_FETCH_WORKERS=12

# Monetization (add these later after Stripe setup)
STRIPE_API_KEY=sk_live_xxxxxx
STRIPE_PUBLISHABLE_KEY=pk_live_xxxxxx

# Domain (replace with your domain)
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
EOF

chmod 600 .env  # Restrict permissions
```

Generate a secure secret key:
```bash
openssl rand -hex 32
```

---

## Step 5: Set Up PostgreSQL Database (Optional but Recommended)

```bash
# Start PostgreSQL
service postgresql start

# Create database and user
sudo -u postgres psql << 'EOF'
CREATE DATABASE dashboard_prod;
CREATE USER dashboard_user WITH PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE dashboard_prod TO dashboard_user;
\q
EOF

# Update .env with:
# DATABASE_URL=postgresql://dashboard_user:secure_password_here@localhost:5432/dashboard_prod
```

---

## Step 6: Configure Nginx as Reverse Proxy

Create an Nginx config file:

```bash
sudo cat > /etc/nginx/sites-available/dashboard << 'EOF'
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificates (setup with Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
    limit_req zone=general burst=20 nodelay;

    location / {
        # Proxy to Gunicorn (running on localhost:8000)
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts for long-running backtest requests
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Static files (CSS, JS, images)
    location /static/ {
        alias /home/yourusername/public_html/dashboard-prod/app/assets/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
}
EOF

# Enable the site
sudo ln -s /etc/nginx/sites-available/dashboard /etc/nginx/sites-enabled/
sudo nginx -t  # Test config
sudo systemctl restart nginx
```

---

## Step 7: Install SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
apt-get install -y certbot python3-certbot-nginx

# Generate free SSL certificate
certbot certonly --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renew
systemctl enable certbot.timer
systemctl start certbot.timer
```

---

## Step 8: Set Up Gunicorn WSGI Server

Create `gunicorn_config.py`:

```python
import multiprocessing

bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1  # 3-9 workers depending on VPS
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 60
keepalive = 5
```

Create a Systemd service file:

```bash
sudo cat > /etc/systemd/system/dashboard.service << 'EOF'
[Unit]
Description=Pre-Swing Dashboard Gunicorn Service
After=network.target postgresql.service

[Service]
User=yourusername
WorkingDirectory=/home/yourusername/public_html/dashboard-prod
ExecStart=/home/yourusername/public_html/dashboard-prod/venv/bin/gunicorn \
    -c gunicorn_config.py \
    -b 127.0.0.1:8000 \
    wsgi:app

Restart=always
RestartSec=10

# Environment
EnvironmentFile=/home/yourusername/public_html/dashboard-prod/.env

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable dashboard.service
sudo systemctl start dashboard.service
sudo systemctl status dashboard.service
```

---

## Step 9: Monitor Logs

```bash
# Check application logs
sudo journalctl -u dashboard.service -f

# Check Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Check system resources
htop  # Install: apt-get install htop
```

---

## Step 10: Point Domain to Your VPS

1. Log into **Hostinger Domain Manager**
2. Go to **DNS** settings
3. Point your domain's **A record** to your VPS IP address (found in Hostinger control panel)
4. **Name servers** should already be set to Hostinger's
5. Wait 5-10 minutes for DNS propagation

After propagation:
```bash
# Test your domain
curl https://yourdomain.com
# Should return the Dash app HTML (200 OK)
```

---

## Step 11: Set Up Monitoring & Alerts

### Email Alerts (UptimeRobot)

1. Go to [UptimeRobot.com](https://uptimerobot.com) (free tier available)
2. Add monitor: `https://yourdomain.com`
3. Check every 5 minutes
4. Alert if down for >5 minutes
5. Get email notifications

### Application Monitoring (Sentry)

```bash
# Install Sentry client
pip install sentry-sdk

# Add to app.py before creating Dash app:
import sentry_sdk
sentry_sdk.init(
    dsn="your-sentry-dsn-here",
    traces_sample_rate=0.1,
    environment="production"
)
```

Sign up at [Sentry.io](https://sentry.io) (free tier: 5K events/month).

---

## Step 12: Set Up Automated Backups

```bash
# Create backup script
cat > /home/yourusername/backup_dashboard.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/yourusername/backups"
mkdir -p $BACKUP_DIR

# Backup database
pg_dump dashboard_prod > $BACKUP_DIR/db_$(date +%Y%m%d_%H%M%S).sql

# Backup application directory
tar -czf $BACKUP_DIR/app_$(date +%Y%m%d_%H%M%S).tar.gz \
    /home/yourusername/public_html/dashboard-prod

# Keep last 7 days only
find $BACKUP_DIR -type f -mtime +7 -delete
EOF

chmod +x /home/yourusername/backup_dashboard.sh

# Schedule daily at 2 AM
(crontab -l 2>/dev/null; echo "0 2 * * * /home/yourusername/backup_dashboard.sh") | crontab -
```

---

## Troubleshooting

### Port 8000 Already in Use
```bash
lsof -i :8000  # Find process
kill -9 <PID>
```

### Gunicorn Not Starting
```bash
# Run manually to see errors:
source venv/bin/activate
gunicorn -c gunicorn_config.py wsgi:app
```

### Nginx 502 Bad Gateway
- Check if Gunicorn is running: `systemctl status dashboard.service`
- Check Gunicorn logs: `journalctl -u dashboard.service -n 50`
- Verify proxy_pass in Nginx config is `127.0.0.1:8000`

### Slow Performance
- Increase worker count in `gunicorn_config.py`
- Enable Redis caching (upgrade Hostinger VPS if needed)
- Optimize yfinance data fetching (see `config.py`)

---

## Performance Benchmarks

On **Hostinger 2GB VPS**:
- ✅ Cold start: 8-12 seconds
- ✅ Data refresh: 3-5 seconds (100 stocks)
- ✅ Backtest: 2-8 seconds (1-year data)
- ✅ Concurrent users: 50-100 without issues

If you need better performance, upgrade to **4GB/8GB VPS** ($15-30/month).

---

## Next Steps

1. ✅ Deploy app on VPS
2. 📊 Set up analytics (Google Analytics, Mixpanel)
3. 💳 Integrate Stripe for payments (see [MONETIZATION.md](./docs/MONETIZATION.md))
4. 🔐 Set up user authentication (see [SECURITY.md](./docs/SECURITY.md))
5. 📈 Monitor uptime and performance

**Estimated monthly cost:** $15-25/month (VPS + domain + optional CDN)

---

For issues, check:
- [Hostinger Support](https://support.hostinger.com)
- [Nginx Docs](https://nginx.org/en/docs/)
- [Gunicorn Docs](https://docs.gunicorn.org)
