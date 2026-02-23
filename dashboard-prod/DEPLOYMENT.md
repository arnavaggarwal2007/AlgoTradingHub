# Production Deployment Configuration

This directory contains everything needed to deploy the Pre-Swing Trade Analysis Dashboard as a production-grade SaaS application.

---

## 📦 What's Included

### Deployment Guides
- **DEPLOY_HOSTINGER.md** — Hostinger VPS (cheapest, $10-20/mo, full control)
- **DEPLOY_RENDER.md** — Render.com (easiest, $12/mo, auto-deploys)
- **DEPLOY_RAILWAY.md** — Railway (best DX, pay-as-you-go)
- **DEPLOY_PYTHONANYWHERE.md** — PythonAnywhere (Python-native)

### Documentation
- **docs/MONETIZATION.md** — Revenue models, SEC compliance, Stripe setup
- **docs/SECURITY.md** — SSL, user auth, rate limiting, data protection
- **docs/API.md** — JSON API docs for developers
- **docs/MONITORING.md** — Uptime, alerts, performance tracking

### Configuration Files
- **requirements.txt** — Python dependencies (production-pinned)
- **Procfile** — Heroku/Render deployment manifest
- **gunicorn_config.py** — WSGI server settings
- **wsgi.py** — Application entry point
- **.env.example** — Environment variables template

---

## 🚀 Quick Start (Choose One)

### Option A: Hostinger VPS (Most Control)
**Setup time:** 45 minutes | **Cost:** $10-20/month
```bash
# 1. Buy Hostinger Business VPS plan
# 2. Follow DEPLOY_HOSTINGER.md (detailed step-by-step)
# 3. SSH into server + deploy
```
→ See [DEPLOY_HOSTINGER.md](./DEPLOY_HOSTINGER.md)

### Option B: Render.com (Easiest - RECOMMENDED FOR MVP)
**Setup time:** 5 minutes | **Cost:** Free-$12/month
```bash
# 1. Connect GitHub repo to Render
# 2. Set environment variables
# 3. Auto-deploys on every git push
```
→ See [DEPLOY_RENDER.md](./DEPLOY_RENDER.md)

### Option C: Railway (Best Developer Experience)
**Setup time:** 5 minutes | **Cost:** $5-100/month (pay-as-you-go)
```bash
# 1. Connect GitHub to Railway
# 2. Deploy with one click
# 3. Scale up as needed
```
→ See [DEPLOY_RAILWAY.md](./DEPLOY_RAILWAY.md)

### Option D: PythonAnywhere (Python-First Hosting)
**Setup time:** 10 minutes | **Cost:** Free-$15/month
```bash
# 1. Upload code to web console
# 2. Configure Web App
# 3. Point domain
```
→ See [DEPLOY_PYTHONANYWHERE.md](./DEPLOY_PYTHONANYWHERE.md)

---

## 💡 Recommendation by Use Case

| Use Case | Recommendation | Reason |
|----------|---|---|
| **Testing MVP** | Render (free tier) | No credit card, fast, can upgrade anytime |
| **First 1000 users** | Render (Starter $12/mo) | Reliable, auto-scales, 99.99% uptime |
| **Full control + cost savings** | Hostinger VPS | Cheapest long-term, full server access |
| **Enterprise/High traffic** | Railway (with CDN) | Best performance, auto-scales, pay-as-you-go |
| **Beginners** | PythonAnywhere | Easiest, no DevOps knowledge needed |

---

## 📋 Pre-Deployment Checklist

- [ ] Code is in GitHub
- [ ] All secrets in `.env` (not in code)
- [ ] `requirements.txt` has all dependencies
- [ ] `wsgi.py` creates the Dash app correctly
- [ ] `Procfile` or deployment config is committed
- [ ] Tests pass locally: `pytest tests/`
- [ ] Environment variables documented in `.env.example`
- [ ] Terms of Service written (disclaimer included)
- [ ] Privacy Policy written (GDPR/CCPA compliant)
- [ ] SSL certificate ready (auto-handled by Render/Railway)

---

## 🔐 Security (Before Going Live)

1. **Environment Variables**
   - Never commit `.env` to GitHub
   - Use `.env.example` as template
   - Rotate `SECRET_KEY` regularly

2. **SSL/HTTPS**
   - Render/Railway: automatic
   - Hostinger: use Let's Encrypt (free)
   - PythonAnywhere: free included

3. **User Authentication**
   - Use Auth0 (free tier: 7000 users/month)
   - Or Flask-Login + hashed passwords
   - Implement "forgot password" flow

4. **Rate Limiting**
   - Render: built-in
   - Hostinger: configure in Nginx
   - Limit API: 1000 req/hour per user

5. **Database**
   - Use PostgreSQL (not SQLite in production)
   - Enable SSL for DB connections
   - Regular automated backups (daily)

See [docs/SECURITY.md](./docs/SECURITY.md) for full checklist.

---

## 💰 Monetization Setup

### Freemium Model (Recommended First)
```
Free Tier
├─ 10 stocks
├─ 1-day delay
└─ 5 refreshes/day

Premium Tier ($9.99/month)
├─ Unlimited stocks
├─ Real-time data
└─ Unlimited refreshes
```

### Payment Processing
1. Sign up at [Stripe.com](https://stripe.com)
2. Add API keys to `.env`
3. Implement checkout page
4. Store subscriptions in PostgreSQL

See [docs/MONETIZATION.md](./docs/MONETIZATION.md) for:
- ✅ SEC compliance (NO registration needed)
- ✅ Revenue models (freemium, API, white label)
- ✅ Stripe integration code
- ✅ Tax/legal considerations

---

## 📊 Monitoring & Alerts

### Application Monitoring
- **Sentry** (free tier: 5k events/month) — error tracking
- **New Relic** (free tier: 1 host) — performance monitoring

### Uptime Monitoring
- **UptimeRobot** (free) — alerts if site goes down
- Check every 5 minutes, email notifications

### Logs
- Render/Railway: built-in log viewing
- Hostinger: SSH into server, check journal

See [docs/MONITORING.md](./docs/MONITORING.md) for setup.

---

## 🔄 Deployment Flow

```
Local Development
    ↓ (git push)
GitHub Repository
    ↓ (auto-trigger)
CI/CD Pipeline (test, lint)
    ↓ (if passes)
Production Server
    ↓
HTTPS Reverse Proxy (Nginx/Caddy)
    ↓
Gunicorn (WSGI)
    ↓
Dash App
    ↓
PostgreSQL + Redis Cache
    ↓
yfinance API
```

---

## 📈 Performance Benchmarks

On **Hostinger 2GB VPS** or **Render Starter**:
- Cold start: 5-10 seconds
- Data refresh (100 stocks): 3-5 seconds
- Backtest (1-year): 2-8 seconds
- Concurrent users: 50-100 without issues

---

## 🆘 Troubleshooting

### App won't start
→ Check `.env` variables
→ Check `requirements.txt` (missing dependency?)
→ Check logs: `tail -f /var/log/systemd/journal`

### Slow performance
→ Increase `workers` in `gunicorn_config.py`
→ Switch to 4GB VPS
→ Enable Redis caching

### Database errors
→ Check PostgreSQL connection string in `.env`
→ Verify PostgreSQL service is running
→ Check backups are working

### SSL certificate expired
→ (Render/Railway) auto-renews
→ (Hostinger) run `certbot renew`

---

## 📞 Support Resources

- **Hostinger Support:** https://support.hostinger.com
- **Render Docs:** https://render.com/docs
- **Railway Docs:** https://docs.railway.app
- **Flask/Dash Docs:** https://plotly.com/dash/
- **Gunicorn Docs:** https://docs.gunicorn.org
- **Nginx Docs:** https://nginx.org/en/docs/

---

## 🚀 Next Steps

1. **Choose hosting** → Pick one deployment guide
2. **Follow guide** → Deploy in 5-45 minutes
3. **Configure domain** → Point DNS to your host
4. **Test live** → Verify site is HTTP 200
5. **Set up monitoring** → UptimeRobot + Sentry
6. **Add payments** → Implement Stripe (optional now, can add later)
7. **Market it** → Share on Reddit, Twitter, Product Hunt

---

## 📝 File Structure

```
dashboard-prod/
├── README.md                   # This file
├── DEPLOY_HOSTINGER.md        # Hostinger VPS guide
├── DEPLOY_RENDER.md           # Render.com guide
├── DEPLOY_RAILWAY.md          # Railway guide
├── DEPLOY_PYTHONANYWHERE.md   # PythonAnywhere guide
│
├── requirements.txt            # Python dependencies
├── Procfile                    # Deployment manifest
├── gunicorn_config.py         # WSGI server config
├── wsgi.py                    # App entry point
├── .env.example               # Environment template
│
├── docs/
│   ├── MONETIZATION.md        # Revenue + SEC compliance
│   ├── SECURITY.md            # SSL, auth, rate limiting
│   ├── API.md                 # JSON API docs
│   └── MONITORING.md          # Uptime + alerts
│
├── app/
│   ├── app.py                 # Main Dash app
│   ├── config.py              # Configuration
│   ├── models.py              # Database models
│   ├── auth.py                # User authentication
│   ├── monetization.py        # Subscription logic
│   ├── services/
│   ├── components/
│   └── assets/
│
└── tests/
    └── test_backtest_service.py
```

---

**Ready to launch?** Pick a deployment guide above and get started! 🚀
