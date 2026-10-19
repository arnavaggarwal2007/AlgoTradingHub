"""
auto_blog/scheduler.py — Main entry point for the twice-weekly blog automation.

Cron setup (on Digital Ocean droplet):
    # Run at 9:00 AM EST (14:00 UTC) on Tuesdays and Fridays
    0 14 * * 2,5 /home/deploy/dashboard-prod/.venv/bin/python -m auto_blog.scheduler >> /var/log/auto_blog.log 2>&1

Manual one-shot run:
    python -m auto_blog.scheduler
    python -m auto_blog.scheduler --dry-run        # generate but don't publish
    python -m auto_blog.scheduler --topic 3        # force topic index 3
    python -m auto_blog.scheduler --test-wp        # test WordPress connection only
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Configure logging (writes to file + stdout) ──────────────────────────────
LOG_FILE = Path("/tmp/auto_blog.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("auto_blog.scheduler")


def run_once(
    dry_run: bool = False,
    force_topic_index: int | None = None,
) -> bool:
    """
    Generate one blog post and publish (or print if dry_run).

    Returns True on success, False on any error.
    """
    from auto_blog.blog_generator import BlogGenerator
    from auto_blog.config import BlogConfig
    from auto_blog.topics import TOPIC_BANK, get_scheduled_topic
    from auto_blog.wordpress_poster import WordPressPoster

    config = BlogConfig()
    errors = config.validate()
    if errors and not dry_run:
        log.warning("Config issues (continuing with fallbacks): %s", "; ".join(errors))

    # ── Pick topic ────────────────────────────────────────────────────────────
    if force_topic_index is not None:
        topic = TOPIC_BANK[force_topic_index % len(TOPIC_BANK)]
        log.info("Forced topic [%d]: %s", force_topic_index, topic.title)
    else:
        topic = get_scheduled_topic()
        if topic is None:
            log.info("Not a scheduled post day — exiting.")
            return True
        log.info("Scheduled topic: %s", topic.title)

    # ── Generate content ──────────────────────────────────────────────────────
    log.info("Generating blog post…")
    generator = BlogGenerator(config)
    post = generator.generate(topic)
    log.info("Generated post: '%s'  words≈%d", post.title, len(post.html_content.split()))

    if dry_run:
        print("\n" + "=" * 70)
        print(f"DRY RUN — Post title : {post.title}")
        print(f"Focus keyword        : {post.focus_keyword}")
        print(f"Meta description     : {post.meta_description}")
        print(f"Tags                 : {', '.join(post.tags)}")
        print(f"Category             : {post.category}")
        print("=" * 70)
        print(post.html_content[:1000], "…")
        return True

    # ── Publish to WordPress ──────────────────────────────────────────────────
    poster = WordPressPoster(config)
    result = poster.publish(post)

    if result.success:
        log.info("SUCCESS — Post published: %s (id=%s)", result.post_url, result.post_id)
        return True
    else:
        log.error("FAILED — %s", result.error)
        return False


def test_wp_connection() -> None:
    from auto_blog.config import BlogConfig
    from auto_blog.wordpress_poster import WordPressPoster

    config = BlogConfig()
    errors = config.validate()
    if errors:
        print("Config warnings:", "; ".join(errors))

    poster = WordPressPoster(config)
    ok = poster.test_connection()
    sys.exit(0 if ok else 1)


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto Blog Scheduler — generate + publish a trading blog post"
    )
    parser.add_argument("--dry-run", action="store_true", help="Generate but do not publish")
    parser.add_argument("--topic", type=int, default=None, metavar="N", help="Force topic index")
    parser.add_argument("--test-wp", action="store_true", help="Test WordPress connection and exit")
    args = parser.parse_args()

    if args.test_wp:
        test_wp_connection()
        return

    log.info("=== auto_blog run started at %s UTC ===", datetime.now(timezone.utc).isoformat())
    success = run_once(dry_run=args.dry_run, force_topic_index=args.topic)
    log.info("=== auto_blog run finished — %s ===", "OK" if success else "FAILED")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
