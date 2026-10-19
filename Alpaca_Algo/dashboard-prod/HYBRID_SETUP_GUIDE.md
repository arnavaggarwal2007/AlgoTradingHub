# Complete Setup Guide — Hostinger WordPress + Digital Ocean Hybrid

> **From zero to a live, monetized, SEO-optimized trading platform.**
> Estimated completion: 4-6 hours (mostly waiting on DNS propagation)

---

## Architecture Overview

```
Internet Users
      │
      ├── yourdomain.com ──────────────► Hostinger WordPress
      │   (Marketing, Blog, SEO)           - Astra theme
      │   ↕ Affiliate links                - Yoast SEO
      │   ↕ "Launch Dashboard" button      - Auto-published blog posts
      │
      └── app.yourdomain.com ──────────► Digital Ocean Droplet ($12/mo)
          (Python Dash App)                - Gunicorn + Nginx
          ↕ Live trade signals             - Trading algo (market hours)
          ↕ Portfolio analytics            - PostgreSQL database
          ↕ Backtesting engine             - Redis cache
                                           - Auto-blog cron (Tue/Fri)
```

**Monthly cost: ~$19-22/mo | Potential income: $130-2,200/mo**

---

## Phase 1 — Digital Ocean Server (Day 1)

### 1.1 Create Droplet

1. Sign up at [digitalocean.com](https://digitalocean.com)
2. **Create → Droplets**:
   - Image: **Ubuntu 22.04 LTS (x64)**
   - Size: **Basic — Regular — $12/mo** (2GB RAM, 1 vCPU, 50GB SSD)
   - Region: Choose closest to your users (NYC or SFO for US)
   - Authentication: **SSH Keys** — paste your public key (`~/.ssh/id_ed25519.pub`)
   - Hostname: `algotrades-prod`
3. Click **Create Droplet** — takes ~60 seconds
4. Note the **Droplet IP address** (shown in dashboard)

### 1.2 Connect VS Code to Droplet

```
Ctrl+Shift+P → Remote-SSH: Open Configuration File
```

Add to `~/.ssh/config`:
```
Host algotrades-do
    HostName YOUR_DROPLET_IP
    User root
    IdentityFile ~/.ssh/id_ed25519
```

Then: `Ctrl+Shift+P → Remote-SSH: Connect to Host → algotrades-do`

VS Code now runs directly on your server. Open a terminal (`Ctrl+` "`").

### 1.3 Run the Bootstrap Script

```bash
# Upload the setup script to the server
# (From your LOCAL terminal, not SSH terminal)
scp C:\Alpaca_Algo\dashboard-prod\scripts\setup_digitalocean.sh root@YOUR_DROPLET_IP:~/

# Then in the SSH terminal:
chmod +x ~/setup_digitalocean.sh
./setup_digitalocean.sh
```

The script will:
- Install Python 3.11, Nginx, PostgreSQL, Redis
- Create a `deploy` user
- Clone your GitHub repo
- Set up systemd services
- Configure Nginx
- Set up cron for auto-blog and trading algo

### 1.4 Fill in Server Credentials

```bash
# Still in SSH terminal:
nano /home/deploy/dashboard-prod/.env
```

Fill in ALL values:
```env
SECRET_KEY=<run: openssl rand -hex 32>
APCA_API_KEY_ID=<your Alpaca key>
APCA_API_SECRET_KEY=<your Alpaca secret>
OPENAI_API_KEY=sk-proj-...
WP_SITE_URL=https://yourdomain.com
WP_USERNAME=your_wp_user
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

Then restart the app:
```bash
sudo systemctl restart preswing-app
sudo systemctl status preswing-app   # should show "Active: active (running)"
```

**Test it:** `curl http://YOUR_DROPLET_IP` — should return HTML

---

## Phase 2 — Hostinger WordPress (Day 1-2)

### 2.1 Buy Hosting + Domain

1. Go to [hostinger.com](https://hostinger.com)
2. Choose **Business Web Hosting** (~$3.99-6.99/mo)
3. Register domain during checkout (free for first year)

### 2.2 Install WordPress

1. Hostinger hPanel → Websites → Add Website → WordPress
2. Choose your domain
3. Admin credentials:
   - Username: something_other_than_admin (security!)
   - Password: 20+ characters — save this!
4. Click Install

### 2.3 Install Plugins

Go to **WP Admin → Plugins → Add New**, install these:

**Round 1 (SEO & Performance):**
- Yoast SEO ← search "yoast"
- LiteSpeed Cache (or WP Super Cache)
- ShortPixel Image Optimizer

**Round 2 (Monetization):**
- Pretty Links ← for affiliate URLs
- Ad Inserter
- WPForms Lite
- Newsletter

**Round 3 (Analytics & Security):**
- MonsterInsights (free)
- Wordfence Security

### 2.4 Install Astra Theme

WP Admin → Appearance → Themes → Add New → search "Astra" → Install → Activate

Customize: Appearance → Customize
- Colors: Primary `#1a73e8`, Accent `#0d47a1`
- Typography: Body font "Inter" or "Roboto"

### 2.5 Create These Pages

| Page | Key Content |
|------|-------------|
| **Home** | Hero CTA → app.yourdomain.com |
| **About** | Your trading story + credentials |
| **Blog** | Auto-populated by WP blog system |
| **Disclaimer** | Required — financial advice disclaimer |
| **Affiliate Disclosure** | Required by FTC |

**Home page hero HTML (paste in Custom HTML block):**
```html
<div style="text-align:center; padding:40px 20px; background:linear-gradient(135deg,#0d47a1,#1565c0); border-radius:12px; color:white;">
  <h1 style="font-size:2.5em; margin-bottom:16px;">AI-Powered Swing Trade Signals</h1>
  <p style="font-size:1.2em; margin-bottom:32px; opacity:0.9;">
    Real-time technical analysis · 1-year backtest · Portfolio tracking
  </p>
  <a href="https://app.yourdomain.com" 
     target="_blank" 
     rel="noopener"
     style="background:#4caf50; color:white; padding:16px 40px; border-radius:8px;
            font-size:1.1em; font-weight:bold; text-decoration:none; display:inline-block;">
    Launch Free Dashboard →
  </a>
</div>
```

### 2.6 Configure DNS (link WordPress to Digital Ocean)

In Hostinger hPanel → Domains → DNS Zone:

| Type | Host | Value | TTL |
|------|------|-------|-----|
| A | `@` | Hostinger auto-filled | 3600 |
| A | `www` | Hostinger auto-filled | 3600 |
| **A** | **`app`** | **YOUR_DO_DROPLET_IP** | **300** |

> DNS propagation takes 15 minutes to 24 hours.

**Verify propagation:** `ping app.yourdomain.com` — should return your Droplet IP

### 2.7 Enable SSL on Digital Ocean (after DNS propagates)

```bash
# In SSH terminal on the Droplet:
sudo certbot --nginx -d app.yourdomain.com
# Follow prompts — choose "Redirect HTTP to HTTPS"
```

Your dashboard is now live at `https://app.yourdomain.com`!

### 2.8 Get WordPress Application Password

WP Admin → Users → All Users → click your username → scroll to bottom

**Application Passwords** section:
- Name: `AutoBlog Bot`
- Click: **Add New Application Password**
- **Copy immediately!** It shows only once.

Add to server `.env`:
```
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

---

## Phase 3 — Auto-Blog Setup (Day 2-3)

### 3.1 Test WordPress Connection from Server

```bash
# SSH into server:
cd /home/deploy/dashboard-prod
sudo -u deploy .venv/bin/python -m auto_blog.scheduler --test-wp
```

Should print: `WordPress auth OK — logged in as: your_name (id=1)`

### 3.2 Test Blog Generation (dry run — no publishing)

```bash
sudo -u deploy .venv/bin/python -m auto_blog.scheduler --dry-run
```

This generates a full blog post and prints it to the terminal WITHOUT publishing.

### 3.3 Publish Your First Post Manually

```bash
sudo -u deploy .venv/bin/python -m auto_blog.scheduler
```

Check your WordPress admin — you should see a new blog post published!

### 3.4 Set Up Automatic Cron Schedule

Already configured by the setup script. Verify:

```bash
sudo -u deploy crontab -l
```

Should show:
```
0 14 * * 2,5 .../python -m auto_blog.scheduler >> /var/log/auto_blog.log 2>&1
```

This runs at **9 AM EST every Tuesday and Friday**.

### 3.5 Monitor the Blog

```bash
# View auto-blog logs
tail -f /var/log/auto_blog.log

# View last 20 lines
tail -50 /var/log/auto_blog.log
```

---

## Phase 4 — Affiliate Links (Day 2)

### 4.1 Join Affiliate Programs

Apply to these (all free to join):

| Program | Where to Apply | Commission |
|---------|---------------|-----------|
| Interactive Brokers | ibkr.com → Partners | $200/account |
| TradingView | tradingview.com → Partners | 30% recurring |
| Alpaca Markets | alpaca.markets | Credits per referral |
| Tastytrade | tastytrade.com → referrals | $100/account |

### 4.2 Set Up Pretty Links

In WP Admin → Pretty Links → Add New:

| Short URL | Affiliate Destination |
|----------|-----------------------|
| `/go/ibkr` | Your IBKR affiliate URL |
| `/go/tradingview` | Your TradingView affiliate URL |
| `/go/alpaca` | Your Alpaca affiliate URL |

### 4.3 Configure Affiliate Links in Auto-Blog

Edit your server `.env`:
```env
AFFILIATE_NAME=Interactive Brokers
AFFILIATE_URL=https://yourdomain.com/go/ibkr
```

The blog generator automatically injects these links into generated posts with `rel="nofollow sponsored"` tags (legally required and SEO compliant).

---

## Phase 5 — VS Code Integration (Ongoing)

### Connect VS Code to Digital Ocean
See [VSCODE_INTEGRATION.md](VSCODE_INTEGRATION.md) — Part 1

### Connect VS Code to WordPress (Hostinger)
See [VSCODE_INTEGRATION.md](VSCODE_INTEGRATION.md) — Part 2

**Quick summary:**
- **Digital Ocean**: `Remote - SSH` extension → direct server access
- **WordPress**: `SFTP` extension → edit theme/plugin files via FTP

---

## Phase 6 — SEO (Ongoing — Month 1-3)

### Week 1
- [ ] Submit sitemap to Google Search Console
- [ ] Submit to Bing Webmaster Tools
- [ ] Set up Google Analytics 4 via MonsterInsights
- [ ] Enable schema markup in Yoast

### Month 1
- [ ] Target ONE primary keyword per published post
- [ ] Ensure every post has: H1, 3+ H2s, 300+ words, internal link to homepage
- [ ] Build 5 backlinks (post on Reddit r/algotrading, r/stocks, r/investing)
- [ ] Set up Google Search Console → monitor clicks + impressions

### Month 2-3
- [ ] Expect 50-200 organic visitors/month if targeting low-competition keywords
- [ ] Monetize: Add affiliate CTAs in top 3 posts
- [ ] Consider adding email list capture (free Mailchimp plan)

---

## Monitoring & Maintenance

### Daily Checks (< 5 min)
```bash
# Server health
ssh algotrades-do 'sudo systemctl status preswing-app trading-algo'

# Dashboard responding
curl -s -o /dev/null -w "%{http_code}" https://app.yourdomain.com
```

### Weekly Checks
```bash
# Auto-blog ran?
cat /var/log/auto_blog.log | tail -20

# Disk usage
ssh algotrades-do 'df -h /'

# DB backup
ssh algotrades-do 'pg_dump dashappdb | gzip > ~/backups/db_$(date +%F).sql.gz'
```

---

## File Reference

| File | Purpose |
|------|---------|
| [DEPLOY_DIGITALOCEAN.md](DEPLOY_DIGITALOCEAN.md) | Manual DO setup guide |
| [DEPLOY_HOSTINGER_WORDPRESS.md](DEPLOY_HOSTINGER_WORDPRESS.md) | WordPress SEO setup |
| [VSCODE_INTEGRATION.md](VSCODE_INTEGRATION.md) | VS Code → DO + WordPress |
| [scripts/setup_digitalocean.sh](scripts/setup_digitalocean.sh) | One-command server bootstrap |
| [auto_blog/scheduler.py](auto_blog/scheduler.py) | Blog automation entry point |
| [auto_blog/blog_generator.py](auto_blog/blog_generator.py) | AI content generation |
| [auto_blog/wordpress_poster.py](auto_blog/wordpress_poster.py) | WordPress REST API publisher |
| [auto_blog/topics.py](auto_blog/topics.py) | 17 curated topic bank |
| [auto_blog/config.py](auto_blog/config.py) | Config from .env |
| [.env.example](.env.example) | All environment variable templates |
| [requirements.txt](requirements.txt) | Python dependencies |

---

## Quick Commands Reference

```bash
# ── From LOCAL machine ────────────────────────────────────────────
ssh algotrades-do                              # Connect to server
scp .env deploy@YOUR_IP:~/dashboard-prod/.env # Upload env file

# ── On server (via SSH) ───────────────────────────────────────────
sudo systemctl restart preswing-app            # Restart dashboard
sudo systemctl status preswing-app             # Check status
journalctl -u preswing-app -f                  # Live logs
cd ~/dashboard-prod && git pull && sudo systemctl restart preswing-app  # Deploy

# ── Auto-blog ─────────────────────────────────────────────────────
python -m auto_blog.scheduler --test-wp       # Test WP connection
python -m auto_blog.scheduler --dry-run       # Test without publishing
python -m auto_blog.scheduler                 # Publish a post now
python -m auto_blog.scheduler --topic 5       # Force topic #5

# ── Database ─────────────────────────────────────────────────────
sudo -u postgres psql dashappdb               # PostgreSQL shell
pg_dump dashappdb > backup.sql                # Backup database

# ── Nginx ─────────────────────────────────────────────────────────
sudo nginx -t                                 # Test config
sudo systemctl reload nginx                   # Reload config
sudo certbot renew                            # Renew SSL cert
```
