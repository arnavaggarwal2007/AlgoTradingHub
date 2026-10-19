"""
gunicorn_config.py — Production WSGI Server Configuration

Use: gunicorn -c gunicorn_config.py wsgi:app

This configures:
- Worker count (based on CPU cores)
- Timeout thresholds
- Request limits
- Logging
- Performance tuning
"""
import os
import multiprocessing

# ──────────────────────────────────────────────────────────────────

# BIND & NETWORK
bind = f"0.0.0.0:{os.getenv('PORT', 8000)}"
backlog = 2048

# ──────────────────────────────────────────────────────────────────

# WORKER PROCESSES
workers = max(1, int(os.getenv("WORKERS", multiprocessing.cpu_count() * 2 + 1)))
worker_class = "sync"
worker_connections = 1000
max_requests = 1000  # Restart worker after 1k requests (memory leak protection)
max_requests_jitter = 100  # Random jitter (0-100 requests) to prevent thundering herd

# ──────────────────────────────────────────────────────────────────

# TIMEOUTS
timeout = int(os.getenv("WORKER_TIMEOUT", 60))  # 60 seconds for long backtest requests
keepalive = 5  # Connection keep-alive

# ──────────────────────────────────────────────────────────────────

# LOGGING
accesslog = "-"  # Log to stdout (captured by container/systemd)
errorlog = "-"   # Errors to stdout
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# ──────────────────────────────────────────────────────────────────

# PERFORMANCE TUNING
preload_app = False  # Load app before forking (can reduce memory but breaks auto-reload)
daemon = False       # Don't daemonize (let container manager handle it)
pidfile = None       # No pidfile in containers
umask = 0o022        # Standard file permission mask

# ──────────────────────────────────────────────────────────────────

# PRODUCTION SETTINGS
if os.getenv("FLASK_ENV") == "production":
    # Stricter in production
    timeout = 120
    workers = min(workers, 8)  # Cap at 8 to prevent resource exhaustion
    max_requests = 500         # Restart sooner to prevent memory leaks
