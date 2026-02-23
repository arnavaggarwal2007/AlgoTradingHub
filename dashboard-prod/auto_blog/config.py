"""
auto_blog/config.py — Blog automation configuration.

All sensitive values come from environment variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the dashboard-prod root
_ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_FILE)


@dataclass
class BlogConfig:
    # ── OpenAI ─────────────────────────────────────────────────────────────────
    openai_api_key: str         = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    # ── WordPress ──────────────────────────────────────────────────────────────
    wp_site_url: str            = field(default_factory=lambda: os.getenv("WP_SITE_URL", "https://yourdomain.com"))
    wp_username: str            = field(default_factory=lambda: os.getenv("WP_USERNAME", ""))
    wp_app_password: str        = field(default_factory=lambda: os.getenv("WP_APP_PASSWORD", ""))
    wp_author_id: int           = field(default_factory=lambda: int(os.getenv("WP_AUTHOR_ID", "1")))
    wp_status: str              = field(default_factory=lambda: os.getenv("WP_POST_STATUS", "publish"))
    wp_default_category_id: int = field(default_factory=lambda: int(os.getenv("WP_DEFAULT_CATEGORY_ID", "1")))

    # ── Dashboard + Affiliate ──────────────────────────────────────────────────
    dashboard_url: str          = field(default_factory=lambda: os.getenv("DASHBOARD_URL", "https://app.yourdomain.com"))
    primary_affiliate_name: str = field(default_factory=lambda: os.getenv("AFFILIATE_NAME", "Interactive Brokers"))
    primary_affiliate_url: str  = field(default_factory=lambda: os.getenv("AFFILIATE_URL", "https://ibkr.com"))

    # ── Scheduler ─────────────────────────────────────────────────────────────
    post_days: list[str]        = field(default_factory=lambda: ["Tuesday", "Friday"])

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str              = field(default_factory=lambda: os.getenv("BLOG_LOG_LEVEL", "INFO"))
    log_file: str               = field(default_factory=lambda: os.getenv("BLOG_LOG_FILE", "/tmp/auto_blog.log"))

    def validate(self) -> list[str]:
        """Return a list of error messages for missing config."""
        errors = []
        if not self.wp_site_url or "yourdomain" in self.wp_site_url:
            errors.append("WP_SITE_URL not configured")
        if not self.wp_username:
            errors.append("WP_USERNAME not configured")
        if not self.wp_app_password:
            errors.append("WP_APP_PASSWORD not configured (see WordPress → User → Application Passwords)")
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY not set — will use template fallback (lower quality)")
        return errors
