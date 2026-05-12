"""Fetch news items from RSS feeds and Google News.

Output: list of NewsItem dicts with title, url, source, category, published, summary.
Each step is wrapped in try/except so one broken feed does not kill the run.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote_plus, urlparse

import feedparser
import yaml
from dateutil import parser as date_parser
from rapidfuzz import fuzz

log = logging.getLogger(__name__)

USER_AGENT = "huisartsendigest/0.1 (+https://github.com/)"
GOOGLE_NEWS_BASE = "https://news.google.com/rss/search"


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    category: str
    weight: float
    published: datetime
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["published"] = self.published.isoformat()
        return d


def load_sources(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _clean_html(text: str) -> str:
    """Strip HTML tags and normalise whitespace from RSS summaries."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_date(entry: dict[str, Any]) -> datetime | None:
    """Try multiple date fields from a feedparser entry."""
    for field_name in ("published", "updated", "created"):
        value = entry.get(field_name)
        if not value:
            continue
        try:
            dt = date_parser.parse(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            continue
    return None


def fetch_rss(feed_url: str, source_name: str, category: str, weight: float,
              since: datetime) -> list[NewsItem]:
    """Fetch a single RSS feed and return items newer than `since`."""
    items: list[NewsItem] = []
    try:
        parsed = feedparser.parse(feed_url, agent=USER_AGENT)
        if parsed.bozo and not parsed.entries:
            log.warning("Feed %s returned no entries (bozo=%s)", source_name, parsed.bozo_exception)
            return items

        for entry in parsed.entries:
            published = _parse_date(entry)
            if not published:
                continue
            if published < since:
                continue

            url = entry.get("link", "").strip()
            title = entry.get("title", "").strip()
            if not url or not title:
                continue

            summary = _clean_html(entry.get("summary", entry.get("description", "")))

            items.append(NewsItem(
                title=title,
                url=url,
                source=source_name,
                category=category,
                weight=weight,
                published=published,
                summary=summary[:600],
            ))
        log.info("Fetched %d items from %s", len(items), source_name)
    except Exception as e:
        log.exception("Failed to fetch %s: %s", source_name, e)
    return items


def fetch_google_news(query: str, source_name: str, category: str,
                      weight: float, since: datetime) -> list[NewsItem]:
    """Google News exposes search results as RSS, including 'when:Nd' time-filter."""
    days_back = max(1, (datetime.now(timezone.utc) - since).days + 1)
    full_query = f"{query} when:{days_back}d"
    url = f"{GOOGLE_NEWS_BASE}?q={quote_plus(full_query)}&hl=nl&gl=NL&ceid=NL:nl"
    return fetch_rss(url, source_name, category, weight, since)


def _canonical_url(url: str) -> str:
    """Strip tracking params and fragments to help with dedup."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def dedupe(items: list[NewsItem], title_threshold: int = 85) -> list[NewsItem]:
    """Dedupe on canonical URL, then on fuzzy title match.

    Keeps the item with the highest source weight when collision occurs.
    """
    seen_urls: dict[str, NewsItem] = {}
    for item in items:
        key = _canonical_url(item.url)
        if key in seen_urls:
            if item.weight > seen_urls[key].weight:
                seen_urls[key] = item
        else:
            seen_urls[key] = item

    deduped: list[NewsItem] = []
    for item in seen_urls.values():
        collision = None
        for existing in deduped:
            if fuzz.token_set_ratio(item.title, existing.title) >= title_threshold:
                collision = existing
                break
        if collision is None:
            deduped.append(item)
        elif item.weight > collision.weight:
            deduped.remove(collision)
            deduped.append(item)
    return deduped


def fetch_all(sources_path: str) -> list[NewsItem]:
    config = load_sources(sources_path)
    lookback = config["editorial"]["lookback_days"]
    since = datetime.now(timezone.utc) - timedelta(days=lookback)

    all_items: list[NewsItem] = []
    for feed in config.get("rss_feeds", []):
        all_items.extend(fetch_rss(
            feed_url=feed["url"],
            source_name=feed["name"],
            category=feed["category"],
            weight=feed["weight"],
            since=since,
        ))
    for q in config.get("google_news_queries", []):
        all_items.extend(fetch_google_news(
            query=q["query"],
            source_name=q["name"],
            category=q["category"],
            weight=q["weight"],
            since=since,
        ))

    log.info("Total before dedup: %d", len(all_items))
    deduped = dedupe(all_items)
    log.info("Total after dedup: %d", len(deduped))
    return sorted(deduped, key=lambda x: x.published, reverse=True)


if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    path = sys.argv[1] if len(sys.argv) > 1 else "src/sources.yaml"
    items = fetch_all(path)
    print(json.dumps([i.to_dict() for i in items], indent=2, ensure_ascii=False))
