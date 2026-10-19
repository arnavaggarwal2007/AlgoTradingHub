"""
auto_blog/wordpress_poster.py — Publish GeneratedPost objects to WordPress via REST API.

WordPress REST API reference: https://developer.wordpress.org/rest-api/reference/posts/

Prerequisites (one-time setup):
    1. WordPress Admin → Users → your user → Application Passwords → Add New
    2. Copy the generated password (shown only once) → WP_APP_PASSWORD env var
    3. Set WP_SITE_URL, WP_USERNAME in your .env
"""
from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Optional

import requests

from auto_blog.blog_generator import GeneratedPost
from auto_blog.config import BlogConfig

log = logging.getLogger(__name__)


@dataclass
class PostResult:
    success: bool
    post_id: Optional[int] = None
    post_url: Optional[str] = None
    error: Optional[str] = None


class WordPressPoster:
    """
    Posts AI-generated trading blog posts to a WordPress site.

    The WordPress REST API requires no plugins — it ships with WordPress 4.7+.
    Authentication uses Application Passwords (WordPress 5.6+).
    """

    def __init__(self, config: BlogConfig):
        self.config = config
        self._base = config.wp_site_url.rstrip("/")
        self._api = f"{self._base}/wp-json/wp/v2"
        self._auth_header = self._build_auth_header()

    # ── Auth ─────────────────────────────────────────────────────────────────

    def _build_auth_header(self) -> str:
        """Build the Basic Authorization header value."""
        credentials = f"{self.config.wp_username}:{self.config.wp_app_password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": self._auth_header,
            "Content-Type": "application/json",
            "User-Agent": "AlgoTradingHub-AutoBlog/1.0",
        }

    # ── Categories & Tags ────────────────────────────────────────────────────

    def _get_or_create_category(self, name: str) -> int:
        """Return an existing category ID or create a new one."""
        resp = requests.get(
            f"{self._api}/categories",
            params={"search": name, "per_page": 5},
            headers=self._headers,
            timeout=10,
        )
        resp.raise_for_status()
        existing = resp.json()
        for cat in existing:
            if cat["name"].lower() == name.lower():
                return cat["id"]

        # Create new
        resp = requests.post(
            f"{self._api}/categories",
            headers=self._headers,
            json={"name": name, "slug": name.lower().replace(" ", "-")},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def _get_or_create_tags(self, tag_names: list[str]) -> list[int]:
        """Return tag IDs, creating missing tags."""
        ids = []
        for name in tag_names[:10]:  # WordPress allows max 10 tags
            resp = requests.get(
                f"{self._api}/tags",
                params={"search": name, "per_page": 3},
                headers=self._headers,
                timeout=10,
            )
            resp.raise_for_status()
            existing = resp.json()
            matched = next((t for t in existing if t["name"].lower() == name.lower()), None)
            if matched:
                ids.append(matched["id"])
            else:
                r = requests.post(
                    f"{self._api}/tags",
                    headers=self._headers,
                    json={"name": name, "slug": name.lower().replace(" ", "-")},
                    timeout=10,
                )
                if r.ok:
                    ids.append(r.json()["id"])
        return ids

    # ── Yoast SEO meta ───────────────────────────────────────────────────────

    def _build_yoast_meta(self, post: GeneratedPost) -> dict:
        """
        Set Yoast SEO fields via the REST API.

        Requires: Yoast SEO plugin (free will do).
        The plugin exposes these fields in the posts endpoint automatically.
        """
        return {
            "yoast_head_json": None,  # read-only, ignore
            "_yoast_wpseo_metadesc": post.meta_description,
            "_yoast_wpseo_focuskw": post.focus_keyword,
        }

    # ── Build post excerpt ───────────────────────────────────────────────────

    @staticmethod
    def _build_excerpt(post: GeneratedPost) -> str:
        """Short excerpt shown in search results and email digests."""
        return (post.meta_description or post.title)[:160]

    # ── Main publish method ──────────────────────────────────────────────────

    def publish(self, post: GeneratedPost) -> PostResult:
        """
        Publish a GeneratedPost to WordPress and return the result.

        Steps:
            1. Resolve/create category
            2. Resolve/create tags
            3. POST to /wp-json/wp/v2/posts with full content + SEO meta
        """
        try:
            cat_id = self._get_or_create_category(post.category)
            tag_ids = self._get_or_create_tags(post.tags)

            yoast = self._build_yoast_meta(post)

            payload = {
                "title":     post.title,
                "content":   post.html_content,
                "excerpt":   self._build_excerpt(post),
                "status":    self.config.wp_status,   # "publish" or "draft"
                "categories": [cat_id, self.config.wp_default_category_id],
                "tags":      tag_ids,
                "author":    self.config.wp_author_id,
                "meta": yoast,
            }

            resp = requests.post(
                f"{self._api}/posts",
                headers=self._headers,
                data=json.dumps(payload),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            log.info("Published post id=%s url=%s", data["id"], data["link"])
            return PostResult(success=True, post_id=data["id"], post_url=data["link"])

        except requests.HTTPError as exc:
            msg = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            log.error("WordPress publish failed: %s", msg)
            return PostResult(success=False, error=msg)
        except Exception as exc:  # noqa: BLE001
            log.exception("Unexpected error during publish")
            return PostResult(success=False, error=str(exc))

    # ── Convenience: publish as draft first ──────────────────────────────────

    def publish_as_draft(self, post: GeneratedPost) -> PostResult:
        """Publish as draft for human review before going live."""
        original_status = self.config.wp_status
        self.config.wp_status = "draft"
        result = self.publish(post)
        self.config.wp_status = original_status
        return result

    # ── Verify connection ────────────────────────────────────────────────────

    def test_connection(self) -> bool:
        """Ping the WP REST API and verify auth works."""
        try:
            resp = requests.get(
                f"{self._api}/users/me",
                headers=self._headers,
                timeout=10,
            )
            if resp.ok:
                user = resp.json()
                log.info("WordPress auth OK — logged in as: %s (id=%s)", user.get("name"), user.get("id"))
                return True
            log.error("WordPress auth FAILED: %s %s", resp.status_code, resp.text[:100])
            return False
        except Exception as exc:  # noqa: BLE001
            log.error("WordPress connection error: %s", exc)
            return False
