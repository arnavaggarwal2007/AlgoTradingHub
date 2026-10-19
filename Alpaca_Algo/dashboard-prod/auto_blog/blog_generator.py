"""
auto_blog/blog_generator.py

Generates SEO-optimized trading blog posts using OpenAI GPT-4.
Falls back to GPT-3.5-turbo if GPT-4 quota is exceeded.

Layout of a generated post:
  - H1 title (keyword-rich, clickbait-safe)
  - Introduction (hook + problem statement)
  - H2/H3 sections (3-5 sections, each with keyword placement)
  - Trading examples with real signals
  - Affiliate CTA paragraph
  - Conclusion + call-to-action
  - FAQ (for SEO featured snippets)
  - Meta description
  - Focus keyword (Yoast/RankMath compatible)
"""
from __future__ import annotations

import logging
import random
from datetime import date
from typing import Optional

try:
    from openai import OpenAI  # openai>=1.0.0
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False

from auto_blog.topics import BlogTopic, get_scheduled_topic
from auto_blog.config import BlogConfig

logger = logging.getLogger(__name__)

# ─── Prompt Templates ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """
You are an expert stock trading educator and content writer specializing in
swing trading, technical analysis, and algorithmic strategies.

Write in a professional yet accessible tone. Your audience is:
- Retail traders (beginner to intermediate)
- People interested in passive income from trading
- Investors looking for systematic edge

SEO guidelines:
- Include the focus keyword in H1, first paragraph, at least 2 H2 headings, and conclusion
- Use LSI (Latent Semantic Indexing) keywords naturally throughout
- Write 1000-1500 words per post
- Add a FAQ section at the end (4-6 questions) for featured snippet optimization
- Include affiliate disclosure at the start if a broker is mentioned
- NEVER give specific personalized investment advice
- ALWAYS include risk disclaimer at end of post

Output format: Full HTML (use <h1>, <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em> tags)
Include meta_description (155 chars) and focus_keyword in a JSON block at the end.
"""

_TOPIC_PROMPT_TEMPLATE = """
Write a comprehensive, SEO-optimized blog post about: {topic}

Focus keyword: {keyword}
Secondary keywords: {secondary_keywords}
Target audience: {audience}
Tone: {tone}
Today's date: {today}

Structure:
1. H1 Title (use focus keyword, make it compelling)
2. Introduction (hook + problem/solution, 100-150 words)
3. Section 1: {section_1}
4. Section 2: {section_2}
5. Section 3: {section_3}
{section_4_line}
6. Affiliate recommendation (mention {affiliate_name}, natural integration)
7. Real example from PreSwingTrade dashboard (mention "Pre-Swing Trade Analysis Dashboard")
8. Conclusion + CTA to try the dashboard: {cta_url}
9. Risk Disclaimer
10. FAQ (5 questions, SEO-targeted)

End with a JSON block:
```json
{{"meta_description": "...", "focus_keyword": "...", "tags": ["...", "..."]}}
```
"""


class BlogGenerator:
    """
    Generates blog post content using OpenAI API.

    Usage:
        gen = BlogGenerator(config)
        post = gen.generate()
        print(post.title)
        print(post.html_content)
    """

    def __init__(self, config: BlogConfig):
        self.config = config
        if _HAS_OPENAI and config.openai_api_key:
            self.client = OpenAI(api_key=config.openai_api_key)
        else:
            self.client = None
            logger.warning("OpenAI not available — will use template fallback")

    def generate(self, topic: Optional[BlogTopic] = None) -> "GeneratedPost":
        """Generate a full blog post for the given (or scheduled) topic."""
        if topic is None:
            topic = get_scheduled_topic()

        logger.info("Generating post: %s", topic.title)

        if self.client is not None:
            return self._generate_with_ai(topic)
        else:
            return self._generate_from_template(topic)

    # ── AI Generation ─────────────────────────────────────────────────────────

    def _generate_with_ai(self, topic: BlogTopic) -> "GeneratedPost":
        section4_line = (
            f"4b. Section 4: {topic.section_4}"
            if topic.section_4 else ""
        )

        user_prompt = _TOPIC_PROMPT_TEMPLATE.format(
            topic=topic.title,
            keyword=topic.keyword,
            secondary_keywords=", ".join(topic.secondary_keywords),
            audience=topic.audience,
            tone=topic.tone,
            today=date.today().strftime("%B %d, %Y"),
            section_1=topic.sections[0] if len(topic.sections) > 0 else "Overview",
            section_2=topic.sections[1] if len(topic.sections) > 1 else "Key Concepts",
            section_3=topic.sections[2] if len(topic.sections) > 2 else "Practical Tips",
            section_4_line=section4_line,
            affiliate_name=self.config.primary_affiliate_name,
            cta_url=self.config.dashboard_url,
        )

        for model in ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo-16k"]:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user",   "content": user_prompt},
                    ],
                    max_tokens=2500,
                    temperature=0.72,
                )
                raw = response.choices[0].message.content
                return self._parse_response(raw, topic)
            except Exception as exc:
                logger.warning("Model %s failed: %s — trying next", model, exc)

        # All AI models failed — fallback
        logger.error("All AI models failed, using template")
        return self._generate_from_template(topic)

    # ── Parse AI Response ─────────────────────────────────────────────────────

    def _parse_response(self, raw: str, topic: BlogTopic) -> "GeneratedPost":
        import json, re

        html_content = raw
        meta_description = ""
        focus_keyword = topic.keyword
        tags = topic.secondary_keywords[:5]

        # Extract JSON block at end
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if json_match:
            try:
                meta = json.loads(json_match.group(1))
                meta_description = meta.get("meta_description", "")
                focus_keyword    = meta.get("focus_keyword", focus_keyword)
                tags             = meta.get("tags", tags)
                # Strip the JSON block from HTML
                html_content = raw[:json_match.start()].strip()
            except json.JSONDecodeError:
                pass

        # Extract H1 title from HTML
        title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html_content, re.IGNORECASE)
        title = title_match.group(1) if title_match else topic.title

        if not meta_description:
            # Auto-generate from first <p>
            p_match = re.search(r"<p[^>]*>(.*?)</p>", html_content, re.IGNORECASE | re.DOTALL)
            if p_match:
                text = re.sub(r"<[^>]+>", "", p_match.group(1))
                meta_description = text[:155].strip()

        return GeneratedPost(
            title=title,
            html_content=html_content,
            meta_description=meta_description,
            focus_keyword=focus_keyword,
            tags=tags,
            category=topic.category,
            affiliate_links=topic.affiliate_links,
        )

    # ── Template Fallback (No API Key Needed) ─────────────────────────────────

    def _generate_from_template(self, topic: BlogTopic) -> "GeneratedPost":
        """
        Generates a basic post from a template when OpenAI is unavailable.
        Content is acceptable but not as rich.
        """
        today = date.today().strftime("%B %d, %Y")
        title = topic.title
        kw    = topic.keyword

        html = f"""<h1>{title}</h1>

<p><em>Affiliate Disclosure: This post may contain affiliate links. We may earn a commission
if you sign up for a broker through our links, at no cost to you.</em></p>

<p>If you've been looking for a reliable way to identify <strong>{kw}</strong> opportunities,
you're in the right place. In this guide, we'll walk through exactly how professional swing
traders spot high-probability setups using systematic analysis — and how you can too.</p>

<h2>What Is {topic.sections[0] if topic.sections else kw.title()}?</h2>
<p>Understanding {kw} is essential for any serious swing trader. Whether you're trading
large-cap stocks or small-cap growth names, a systematic approach dramatically improves
your win rate over time.</p>

<ul>
<li><strong>Key Principle 1:</strong> Always define your risk before entering</li>
<li><strong>Key Principle 2:</strong> Follow the trend of the higher timeframe</li>
<li><strong>Key Principle 3:</strong> Use volume confirmation</li>
</ul>

<h2>How the Pre-Swing Trade Dashboard Identifies {kw.title()}</h2>
<p>Our <strong>Pre-Swing Trade Analysis Dashboard</strong> (available at
<a href="{self.config.dashboard_url}">{self.config.dashboard_url}</a>) automatically
scans 100+ stocks and surfaces the highest-scoring setups every day.</p>

<p>Features include:</p>
<ul>
<li>Real-time signal scanning across 100+ stocks</li>
<li>v67 algorithm with EMA21/SMA50/SMA200 alignment screening</li>
<li>1-year backtesting with equity curve</li>
<li>Demand zone visualization and target levels</li>
</ul>

<h2>Top Broker for Swing Trading</h2>
<p>We recommend <strong>{self.config.primary_affiliate_name}</strong> for swing trading.
It offers commission-free trades, excellent charting, and real-time data —
everything you need to act on signals fast.</p>

<p><a href="{self.config.primary_affiliate_url}" rel="nofollow sponsored">
→ Open your free {self.config.primary_affiliate_name} account here</a></p>

<h2>Conclusion</h2>
<p>Mastering <strong>{kw}</strong> doesn't happen overnight, but the right tools make
all the difference. Start with the Pre-Swing Trade Analysis Dashboard — it's free to try.</p>

<p><a href="{self.config.dashboard_url}">→ Try the Dashboard Free</a></p>

<p><em><strong>Risk Disclaimer:</strong> Trading involves risk of loss. Past performance
does not guarantee future results. This post is for educational purposes only and does not
constitute investment advice. Always consult a licensed financial advisor before trading.</em></p>

<h2>Frequently Asked Questions</h2>

<h3>What is {kw}?</h3>
<p>{kw.title()} refers to identifying stocks in a trend that are pulling back to key
support levels, signaling a potential entry point for swing traders.</p>

<h3>How accurate is the Pre-Swing Trade Dashboard?</h3>
<p>Our backtesting over 1-year shows a 60-70% win rate on qualifying setups, though
past performance does not guarantee future results.</p>

<h3>Do I need expensive software?</h3>
<p>No. The Pre-Swing Trade Analysis Dashboard is available at an affordable subscription
and provides everything needed to identify and track swing setups.</p>

<h3>Which broker should I use?</h3>
<p>We recommend {self.config.primary_affiliate_name} for its commission-free trades and
powerful charting tools.</p>

<em>Published {today} — Updated regularly for accuracy.</em>
"""

        return GeneratedPost(
            title=title,
            html_content=html,
            meta_description=f"Learn about {kw} with our systematic approach. "
                             f"Free dashboard, backtested signals, and step-by-step guide. "
                             f"Updated {today}.",
            focus_keyword=kw,
            tags=topic.secondary_keywords[:5],
            category=topic.category,
            affiliate_links=topic.affiliate_links,
        )


# ─── Result Dataclass ─────────────────────────────────────────────────────────

class GeneratedPost:
    """Holds the result of blog generation."""

    def __init__(
        self,
        title: str,
        html_content: str,
        meta_description: str,
        focus_keyword: str,
        tags: list[str],
        category: str,
        affiliate_links: list[dict],
    ):
        self.title            = title
        self.html_content     = html_content
        self.meta_description = meta_description
        self.focus_keyword    = focus_keyword
        self.tags             = tags
        self.category         = category
        self.affiliate_links  = affiliate_links

    def inject_affiliate_links(self) -> None:
        """Replace placeholder text with actual affiliate links in HTML."""
        for link in self.affiliate_links:
            placeholder = link.get("placeholder", "")
            url         = link.get("url", "")
            anchor      = link.get("anchor_text", placeholder)
            if placeholder and url:
                tagged = f'<a href="{url}" rel="nofollow sponsored" target="_blank">{anchor}</a>'
                self.html_content = self.html_content.replace(placeholder, tagged)

    def __repr__(self) -> str:
        return f"<GeneratedPost title={self.title!r} keyword={self.focus_keyword!r}>"
