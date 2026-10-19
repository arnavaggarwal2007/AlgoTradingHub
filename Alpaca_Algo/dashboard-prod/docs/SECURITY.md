# Security & Compliance Guide

---

## 🔐 SSL/HTTPS (Required)

### Render.com / Railway
✅ **Automatic** — Let's Encrypt certificate, auto-renews

### Hostinger VPS
Follow [DEPLOY_HOSTINGER.md](../DEPLOY_HOSTINGER.md) — uses `certbot` from Let's Encrypt (free)

### Test
```bash
curl -I https://yourdomain.com
# Should see: HTTP/2 200
```

---

## 🔑 User Authentication

### Simple Password (SQLite)
Built-in with `flask-login`:
```python
# user.py
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin):
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
```

### OAuth (Auth0)
Recommended for larger deployments:
1. Sign up at [Auth0.com](https://auth0.com) (free tier: 7k users/month)
2. Add credentials to `.env`
3. Implement login callback

### 2FA (Two-Factor Authentication)
Use `pyotp` library:
```bash
pip install pyotp qrcode
```

---

## 🛡️ Rate Limiting

Prevent abuse and DoS attacks:

```python
# In app.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

@app.route('/api/signals')
@limiter.limit("100 per hour")
def get_signals():
    return jsonify(signals)
```

---

## 🔒 Secrets Management

**Never** commit `.env` to GitHub:
1. Add to `.gitignore`: `✓ Done`
2. Use `.env.example` as template
3. Each developer creates their own `.env`

### Secrets Rotation
```bash
# Generate new SECRET_KEY weekly
openssl rand -hex 32

# In .env:
SECRET_KEY=new-key-here
```

---

## 📊 Data Protection

### User Privacy
- Use PostgreSQL (not SQLite) in production
- Enable SSL for DB connections:
  ```
  DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require
  ```

### GDPR / CCPA Compliance
- ✅ User data export (right to data portability)
- ✅ Account deletion (right to be forgotten)
- ✅ Privacy policy visible at `/privacy`
- ✅ Terms of Service at `/terms`

```python
@app.route('/api/export-data', methods=['GET'])
@login_required
def export_data():
    """GDPR right to data portability"""
    user = current_user
    data = {
        'user': {'email': user.email, 'created': user.created_at},
        'signals': [s.to_dict() for s in user.signals],
        'trades': [t.to_dict() for t in user.trades],
    }
    return jsonify(data)

@app.route('/api/delete-account', methods=['POST'])
@login_required
def delete_account():
    """GDPR right to be forgotten"""
    user = current_user
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'Account deleted'})
```

---

## 🚨 Error Handling

Use Sentry for production error tracking:

```python
# In wsgi.py
import sentry_sdk
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    traces_sample_rate=0.1,
    environment=os.getenv("FLASK_ENV")
)
```

---

## 🔍 Security Checklist

- [ ] SSL/HTTPS enabled
- [ ] `.env` in `.gitignore`
- [ ] Secret key rotated (openssl rand -hex 32)
- [ ] User authentication implemented
- [ ] Rate limiting configured
- [ ] HTTPS redirect enabled
- [ ] HSTS headers set (Nginx example in DEPLOY_HOSTINGER.md)
- [ ] CORS properly configured (only allow your domain)
- [ ] SQL injection protection (use ORM, parameters)
- [ ] XSS protection (Dash handles this)
- [ ] CSRF protection enabled
- [ ] Admin panel password set
- [ ] Database backups automated
- [ ] Error logs monitored (Sentry)
- [ ] Dependency versions pinned (requirements.txt)

---

## 📝 Compliance Documents

Required before monetization:

### 1. Terms of Service
Example (customize for your use case):
```
TERMS OF SERVICE

1. DISCLAIMER
   This platform is provided "as-is" for educational purposes only.
   It does not constitute investment advice or recommendations.
   
2. RISK ACKNOWLEDGMENT
   Past performance does not guarantee future results.
   You may lose money trading. Consult a licensed advisor.

3. LIABILITY
   We are not liable for direct, indirect, or consequential losses
   resulting from your use of this platform.

4. USER RESPONSIBILITIES
   - You are 18+ years old
   - You acknowledge all trading risks
   - You will not use this for illegal purposes

5. INTELLECTUAL PROPERTY
   All code, content, algorithms are owned by [Your Company]
   
6. GOVERNING LAW
   These terms governed by laws of [Your Country/State]
```

### 2. Privacy Policy
Example sections:
```
PRIVACY POLICY

1. DATA COLLECTION
   - Email address (for login)
   - Watchlist/portfolio data (for personalization)
   - Usage analytics (how you use the platform)

2. DATA USE
   - Improve platform performance
   - Send transactional emails (subscription updates)
   - Send marketing emails (opt-in only)

3. DATA STORAGE
   - Encrypted in PostgreSQL
   - Regular backups
   - 3-year retention after account deletion

4. DATA SHARING
   - NOT shared with third parties (except payment processor)
   - Payment data handled by Stripe (PCI compliant)
   - NO data sold

5. YOUR RIGHTS
   - Export your data
   - Delete your account
   - Unsubscribe from emails

6. CONTACT
   privacy@yourdomain.com
```

### 3. Risk Disclaimer
```
RISK DISCLAIMER

Trading stocks involves substantial risk of loss.
Past performance does not guarantee future results.

This platform:
- Does NOT provide investment advice
- Does NOT guarantee any returns
- Does NOT endorse any specific trades

You use this platform at your own risk.
```

---

## 🔗 External Links

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security](https://flask-sqlalchemy.palletsprojects.com/security/)
- [Let's Encrypt](https://letsencrypt.org/)
- [Stripe PCI Compliance](https://stripe.com/docs/compliance)

---

## 🆘 Questions?

Contact your hosting provider for platform-specific security questions:
- Render: https://render.com/support
- Hostinger: https://support.hostinger.com
- Railway: https://docs.railway.app
