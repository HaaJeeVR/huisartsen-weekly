"""Trend-dataclasses + helpers voor het maandelijkse themabriefing-rapport.

In v2 doet Cowork de analyse zelf — geen Anthropic SDK call meer in deze
module. Dit bestand bevat de dataclasses + load_recent_digests() die de
input verzamelt voor Cowork om mee te werken.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

DIGESTS_DIR = Path(__file__).parent.parent / "docs" / "digests"


@dataclass
class TrendEvidence:
    week: str               # bv "2026-W20"
    title: str
    relevance: str          # 1-zinner waarom dit het thema ondersteunt
    digest_url: str         # link naar de digest van die week


@dataclass
class BlogBrief:
    working_title: str
    hook: str
    key_points: list[str]
    call_to_action: str


@dataclass
class Trend:
    theme_id: str
    theme_title: str
    thesis: str
    evidence: list[TrendEvidence] = field(default_factory=list)
    contrarian_insight: str = ""
    banker_angle: str = ""
    blog_brief: Optional[BlogBrief] = None


@dataclass
class TrendReport:
    period_label: str       # bv "Mei 2026"
    period_start: str       # ISO date
    period_end: str         # ISO date
    weeks_covered: list[str]
    item_count: int
    trends: list[Trend]
    generated_at: str


def load_recent_digests(weeks_back: int = 6) -> tuple[list[dict], list[str]]:
    """Laad gecureerde items uit sidecar JSONs van afgelopen N weken.

    Returns (items_with_week, weeks_covered).
    """
    if not DIGESTS_DIR.exists():
        return [], []

    cutoff = datetime.now() - timedelta(weeks=weeks_back)
    all_items: list[dict] = []
    weeks: list[str] = []

    for path in sorted(DIGESTS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Could not parse %s: %s", path, e)
            continue

        publish_dt = datetime.fromisoformat(data["publish_date"])
        if publish_dt.tzinfo:
            publish_dt = publish_dt.replace(tzinfo=None)
        if publish_dt < cutoff:
            continue

        week = f"{data['iso_year']}-W{data['iso_week']:02d}"
        weeks.append(week)
        for item in data.get("items", []):
            item_copy = dict(item)
            item_copy["week"] = week
            item_copy["digest_url"] = f"../digests/{data['html_filename']}"
            all_items.append(item_copy)

    return all_items, sorted(set(weeks))


def build_evidence(parsed_evidence: list[dict], items: list[dict]) -> list[TrendEvidence]:
    """Map analist-evidence-refs terug naar feitelijke digest URLs."""
    title_to_url = {it["title"]: it.get("digest_url", "") for it in items}
    result = []
    for ev in parsed_evidence:
        title = ev.get("title", "").strip()
        result.append(TrendEvidence(
            week=ev.get("week", ""),
            title=title,
            relevance=ev.get("relevance", ""),
            digest_url=title_to_url.get(title, ""),
        ))
    return result
