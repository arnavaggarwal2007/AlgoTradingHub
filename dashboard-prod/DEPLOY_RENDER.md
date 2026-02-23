# Deploy to Render.com — 5-Minute Setup

**Cost:** Free tier → $12/month | **Setup Time:** 5 minutes | **Uptime:** 99.99%

---

## Why Render?

✅ **Free tier available** (perfect for MVP testing)
✅ **Automatic HTTPS** with Let's Encrypt
✅ **Auto-deploys** from GitHub
✅ **Built-in database** (PostgreSQL)
✅ **99.99% uptime SLA**
✅ **Zero configuration** for Python apps

---

## Step 1: Prepare Your Repository

Ensure your GitHub repo has:

```
dashboard-prod/
├── requirements.txt
├── Procfile            # NEW
├── gunicorn_config.py
└── wsgi.py
```

**Create `Procfile`:**
```
web: gunicorn -c gunicorn_config.py wsgi:app
```

**Create `gunicorn_config.py`:**
```python
import os
bind = f"0.0.0.0:{os.getenv('PORT', 8000)}"
workers = 4
worker_class = "sync"
timeout = 60
```

**Create `.env.example`** (for reference):
```
FLASK_ENV=production
DEBUG=False
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

Commit and push to GitHub:
```bash
git add .
git commit -m "Add Render deployment files"
git push origin main
```

---

## Step 2: Create Render Account

1. Go to [Render.com](https://render.com)
2. Click **Sign Up** → **GitHub** (authenticate)
3. Authorize Render to access your GitHub repos

---

## Step 3: Create Web Service

1. Click **+ New** → **Web Service**
2. Select your `dashboard-prod` repository
3. Fill in:
   - **Name:** `pre-swing-dashboard`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn -c gunicorn_config.py wsgi:app`
   - **Plan:** `Free` (for testing) or `Starter` ($12/mo)

4. Click **Create Web Service**

---

## Step 4: Set Environment Variables

In the Render dashboard:

1. Go to **Environment** tab
2. Add variables:
   ```
   FLASK_ENV = production
   DEBUG = False
   SECRET_KEY = [generate with: openssl rand -hex 32]
   DATA_PERIOD = 2y
   FETCH_TIMEOUT_SECONDS = 20
   MAX_FETCH_WORKERS = 12
   ```

3. Click **Save**

---

## Step 5: Add PostgreSQL Database (Optional)

1. Click **+ New** → **PostgreSQL**
2. Name: `dashboard-db`
3. Plan: `Free` (0.5GB) or `Starter Plus` ($12/mo for 2GB)
4. Create

Copy the connection string:
```
postgresql://user:password@host:5432/dbname
```

Add to web service environment:
```
DATABASE_URL = [paste connection string]
```

---

## Step 6: Connect Custom Domain

1. In web service dashboard, click **Settings** → **Custom Domain**
2. Enter: `yourdomain.com`
3. Add DNS record to your registrar:
   ```
   Type: CNAME
   Name: yourdomain.com
   Value: [shown by Render]
   ```
4. Wait 5-10 minutes for DNS propagation
5. HTTPS is **automatic**

---

## Step 7: Verify Deployment

1. Render automatically builds and deploys on every git push
2. Check **Logs** tab for deployment status
3. Visit `https://yourdomain.com`
4. Should see your dashboard (HTTP 200)

---

## Troubleshooting

### Build Fails
- Check **Logs** tab
- Common: Missing dependency → add to `requirements.txt`
- Restart: **Redeploy** in dashboard

### Runtime Error
- Check **Logs** → **Runtime logs**
- Common: Missing `.env` variable → add in **Environment**

### Slow Loading
- Free tier has limited resources
- Upgrade to **Starter** ($12/mo) for better performance

---

## Performance on Free Tier

- ✅ 1-2k requests/day
- ✅ 5-10 concurrent users
- ❌ Goes to sleep after 15 min inactivity (cold start: 30s)

**Upgrade to Starter** for always-on service.

---

## Cost Breakdown

| Component | Free | Starter |
|---|---|---|
| Web Service | $0 | $12/mo |
| PostgreSQL | $0 (0.5GB) | $12/mo (2GB) |
| **Total** | **$0** | **$24/mo** |

For production, recommend **Starter** ($12-24/mo total).

---

## Next: Set Up Payments & Analytics

See [MONETIZATION.md](./docs/MONETIZATION.md) for Stripe integration.

**Deployment complete!** 🎉
