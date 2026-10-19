# VS Code Integration Guide

Connect VS Code to both your Digital Ocean server AND your WordPress site on Hostinger.

---

## Part 1 — VS Code → Digital Ocean (Remote SSH)

### Install the Extension

1. Open **Extensions** panel (`Ctrl+Shift+X`)
2. Search: `Remote - SSH`
3. Install **Remote - SSH** by Microsoft (publisher: `ms-vscode-remote`)
4. Also install **Remote - SSH: Editing Configuration Files** (installs automatically)

### Connect to Your Droplet

**One-time SSH key setup** (run in your local terminal):
```powershell
# Generate SSH key if you don't have one
ssh-keygen -t ed25519 -C "your-email@example.com"

# Copy your public key to the droplet
# Replace 123.456.789.0 with your actual droplet IP
ssh-copy-id deploy@123.456.789.0

# Test that it works (should NOT ask for password)
ssh deploy@123.456.789.0
```

**Configure VS Code SSH:**
1. Press `Ctrl+Shift+P` → type **Remote-SSH: Open Configuration File** → select your `~/.ssh/config`
2. Add these lines:
```
Host algotrades-do
    HostName 123.456.789.0
    User deploy
    IdentityFile ~/.ssh/id_ed25519
    ForwardAgent yes
    ServerAliveInterval 60
```

3. Press `Ctrl+Shift+P` → **Remote-SSH: Connect to Host** → select `algotrades-do`
4. VS Code opens a **new window connected to your server**

### What You Can Do Once Connected

| Action | How |
|--------|-----|
| Browse server files | File Explorer panel shows server filesystem |
| Edit files | Open any file — saves directly to server |
| Open server terminal | `Ctrl+` ` → runs commands on the DO droplet |
| Install server extensions | Extensions panel → install on SSH target |
| Debug Python on server | Set breakpoints, attach Python debugger |
| Port forwarding | Ports panel → forward 8050 to `localhost:8050` |

### Port Forwarding (view dashboard in browser)

While connected via SSH:
1. Open **Ports** panel (bottom panel, next to Terminal)
2. Click **Forward a Port** → type `8050`
3. Open `http://localhost:8050` in your local browser — you see the live server dashboard!

### Useful Commands in the SSH Terminal

```bash
# View dashboard logs
journalctl -u preswing-app -f

# Restart the dashboard
sudo systemctl restart preswing-app

# View trading algo logs
journalctl -u trading-algo -f

# Deploy new code from git
cd ~/dashboard-prod && git pull origin main && sudo systemctl restart preswing-app

# Check running services
sudo systemctl status preswing-app trading-algo

# Run the auto-blog manually
cd ~/dashboard-prod && .venv/bin/python -m auto_blog.scheduler --dry-run
```

---

## Part 2 — VS Code → WordPress on Hostinger (SFTP)

### Install the Extension

1. Open **Extensions** panel (`Ctrl+Shift+X`)
2. Search: `SFTP`
3. Install **SFTP** by Natizyskunk (most popular, 4M+ downloads, publisher: `natizyskunk`)
   - Extension ID: `natizyskunk.sftp`

> **Alternative**: FTP-Simple by humy2hu — simpler but fewer features

### Get Your Hostinger FTP Credentials

1. Login to **Hostinger hPanel**
2. Go to **Hosting → Manage → Files → FTP Accounts**
3. Note down:
   - **FTP Host**: e.g., `ftp.yourdomain.com` or the server IP shown
   - **FTP Username**: auto-generated (looks like `u123456789`)
   - **FTP Password**: click **Change Password** to set a known one
   - **Port**: 21 (FTP) or 22 (SFTP — preferred)

> **Use SFTP over FTP** — it's encrypted. Hostinger Business plan supports SFTP on port 22.

### Configure SFTP in VS Code

1. In VS Code, open your `dashboard-prod` folder
2. Press `Ctrl+Shift+P` → **SFTP: Config**
3. VS Code creates `.vscode/sftp.json` — fill it in:

```json
{
    "name": "Hostinger WordPress",
    "host": "ftp.yourdomain.com",
    "protocol": "sftp",
    "port": 22,
    "username": "u123456789",
    "remotePath": "/public_html",
    "uploadOnSave": false,
    "useTempFile": false,
    "openSsh": false,
    "ignore": [
        ".vscode",
        ".git",
        ".DS_Store",
        "node_modules",
        "*.pyc"
    ]
}
```

> **Security**: Add your `.vscode/sftp.json` to `.gitignore` — it should never be committed (contains credentials).

4. Press `Ctrl+Shift+P` → **SFTP: List** to browse your WordPress files

### Working with WordPress Files in VS Code

**Browse remote files:**
- `Ctrl+Shift+P` → **SFTP: List** → navigate `public_html/`
- WordPress files are in `public_html/`
- Themes are at `public_html/wp-content/themes/astra/`
- Plugins are at `public_html/wp-content/plugins/`

**Download a file to edit:**
1. In SFTP panel (sidebar), navigate to the file
2. Right-click → **Download**
3. Edit locally
4. Right-click → **Upload** (or set `uploadOnSave: true`)

**Edit theme CSS:**
```
Remote path: /public_html/wp-content/themes/astra/style.css
```

**Edit child theme** (recommended — won't be overwritten by theme updates):
```
Remote path: /public_html/wp-content/themes/astra-child/style.css
Remote path: /public_html/wp-content/themes/astra-child/functions.php
```

### Recommended Folder Structure for Theme Work

Create a local `wordpress/` folder in your workspace:
```
dashboard-prod/
├── wordpress/
│   ├── themes/
│   │   └── astra-child/        ← sync this to server
│   │       ├── style.css
│   │       └── functions.php
│   ├── plugins/
│   │   └── custom-algoblog/    ← your custom plugin if needed
│   └── .vscode/
│       └── sftp.json           ← gitignored
```

---

## Part 3 — Recommended VS Code Extensions for This Project

Install all of these for the best development experience:

### Required
| Extension | ID | Purpose |
|----------|-----|---------|
| Remote - SSH | `ms-vscode-remote.remote-ssh` | Edit code on Digital Ocean |
| SFTP | `natizyskunk.sftp` | Edit WordPress files on Hostinger |
| Python | `ms-python.python` | Python syntax, debugging |
| Pylance | `ms-python.vscode-pylance` | Python IntelliSense |

### Highly Recommended
| Extension | ID | Purpose |
|----------|-----|---------|
| GitLens | `eamodio.gitlens` | Advanced git history + blame |
| GitHub Copilot | `github.copilot` | AI code completion |
| Python Debugger | `ms-python.debugpy` | Debug trading algo |
| Bracket Pair Colorizer | built-in | Easier to read nested code |
| Thunder Client | `rangav.vscode-thunder-client` | Test WordPress REST API in VS Code |
| .env files | `dotenv.dotenv-vscode` | Syntax highlighting for .env files |
| Markdown All in One | `yzhang.markdown-all-in-one` | Edit .md documentation |

### WordPress Specific
| Extension | ID | Purpose |
|----------|-----|---------|
| PHP Intelephense | `bmewburn.vscode-intelephense-client` | PHP syntax for theme editing |
| WordPress Snippets | `tungvn.wordpress-snippet` | WP function autocomplete |

---

## Part 4 — Test the WordPress REST API with Thunder Client

Once you have Thunder Client installed:

1. Open Thunder Client (lightning bolt icon in sidebar)
2. Click **New Request**
3. Test WordPress connection:

**GET — List recent posts:**
```
GET https://yourdomain.com/wp-json/wp/v2/posts?per_page=5
```
(No auth required for public posts)

**POST — Create a test draft post:**
```
Method: POST
URL: https://yourdomain.com/wp-json/wp/v2/posts
Auth tab: Basic Auth
  Username: your_wp_admin_username
  Password: xxxx xxxx xxxx xxxx xxxx xxxx   ← Application Password

Body (JSON):
{
  "title": "Test Post from VS Code",
  "content": "<p>This is a test post created via the REST API.</p>",
  "status": "draft"
}
```

If you get a 201 response with a post ID — your auto_blog system will work!

---

## Part 5 — Setting Up Launch Configurations

Create `.vscode/launch.json` in your `dashboard-prod` folder:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Run Dash Dashboard",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/app.py",
            "console": "integratedTerminal",
            "env": {
                "FLASK_ENV": "development"
            }
        },
        {
            "name": "Auto Blog — Dry Run",
            "type": "debugpy",
            "request": "launch",
            "module": "auto_blog.scheduler",
            "args": ["--dry-run"],
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}"
        },
        {
            "name": "Auto Blog — Publish Now",
            "type": "debugpy",
            "request": "launch",
            "module": "auto_blog.scheduler",
            "args": [],
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}"
        },
        {
            "name": "Test WordPress Connection",
            "type": "debugpy",
            "request": "launch",
            "module": "auto_blog.scheduler",
            "args": ["--test-wp"],
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}"
        }
    ]
}
```

After adding this, press `F5` and choose which configuration to run from the dropdown.

---

## Quick Reference

| Task | Action |
|------|--------|
| Connect to DO server | `Ctrl+Shift+P` → Remote-SSH: Connect to Host → `algotrades-do` |
| Browse WordPress files | SFTP Explorer sidebar → click remote folder |
| Upload edited file | Right-click file in Explorer → SFTP: Upload |
| Test WordPress API | Thunder Client → create request to `wp-json/wp/v2/` |
| Run trading algo | SSH terminal: `sudo systemctl start trading-algo` |
| View live logs | SSH terminal: `journalctl -u preswing-app -f` |
| Deploy new code | SSH terminal: `cd ~/dashboard-prod && git pull && sudo systemctl restart preswing-app` |
