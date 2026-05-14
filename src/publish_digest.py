"""Read a Cowork-curated digest and publish it.

Cowork (Claude in cowork mode) leest pending/YYYY-Www.json, cureert de items
zelf, en schrijft de selectie naar curated/YYYY-Www.json. Dit script leest
beide bestanden, maakt CuratedItem dataclasses, en rendert de HTML.

Usage:
    python src/publish_digest.py --week 2026-W20
    python src/publish_digest.py --latest
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from curate import CuratedItem
from render import (
    render_digest, render_index, scan_existing_digests,
    write_digest, write_digest_data, write_index,
)

log = logging.getLogger(__name__)

PENDING_DIR = Path(__file__).parent.parent / "pending"
CURATED_DIR = Path(__file__).parent.parent / "curated"


def _find_latest_week() -> str | None:
    """Return the highest YYYY-Www that has both pending and curated files."""
    if not (PENDING_DIR.exists() and CURATED_DIR.exists()):
        return None
    pending = {p.stem for p in PENDING_DIR.glob("*.json")}
    curated = {p.stem for p in CURATED_DIR.glob("*.json")}
    both = sorted(pending & curated)
    return both[-1] if both else None


def _build_curated(curated_data: dict, pending_data: dict) -> list[CuratedItem]:
    """Match Cowork-provided selections back to the original candidate metadata."""
    url_to_candidate = {c["url"]: c for c in pending_data.get("candidates", [])}

    items: list[CuratedItem] = []
    for sel in curated_data.get("items", []):
        original_url = sel.get("original_url", "").strip()
        candidate = url_to_candidate.get(original_url)
        if not candidate:
            log.warning("Curated item refers to unknown URL: %s", original_url)
            continue

        # If Cowork resolved a primary source, swap url/source and store the
        # aggregator in via_*.
        primary_url = sel.get("primary_url") or ""
        primary_source = sel.get("primary_source") or ""
        primary_kind = sel.get("primary_kind") or ""

        if primary_url and primary_url != original_url:
            display_url = primary_url
            display_source = primary_source or candidate["source"]
            via_url = original_url
            via_source = candidate["source"]
        else:
            display_url = original_url
            display_source = candidate["source"]
            via_url = ""
            via_source = ""

        # Normalise published to YYYY-MM-DD (input is full ISO string).
        published_raw = candidate.get("published", "")
        try:
            published = datetime.fromisoformat(published_raw).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            published = published_raw[:10]

        items.append(CuratedItem(
            title=candidate["title"],
            url=display_url,
            source=display_source,
            category=candidate["category"],
            published=published,
            summary=sel.get("summary", "").strip(),
            why_it_matters=sel.get("why_it_matters", "").strip(),
            rank=int(sel.get("rank", 99)),
            via_source=via_source,
            via_url=via_url,
            primary_kind=primary_kind,
        ))
    items.sort(key=lambda c: c.rank)
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--week", help="ISO-week key, bv 2026-W20")
    group.add_argument("--latest", action="store_true",
                       help="Gebruik de meest recente week waar zowel pending als curated voor bestaat")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    week_key = args.week
    if args.latest:
        week_key = _find_latest_week()
        if not week_key:
            log.error("Geen week gevonden met zowel pending als curated JSON.")
            return 1
        log.info("Using latest week: %s", week_key)

    pending_path = PENDING_DIR / f"{week_key}.json"
    curated_path = CURATED_DIR / f"{week_key}.json"

    if not pending_path.exists():
        log.error("Pending file ontbreekt: %s", pending_path)
        return 1
    if not curated_path.exists():
        log.error("Curated file ontbreekt: %s", curated_path)
        log.error("Cowork moet eerst %s schrijven met de redactionele selectie.",
                  curated_path)
        return 1

    pending_data = json.loads(pending_path.read_text(encoding="utf-8"))
    curated_data = json.loads(curated_path.read_text(encoding="utf-8"))

    curated_items = _build_curated(curated_data, pending_data)
    if not curated_items:
        log.error("Geen geldige curated items na matching.")
        return 1
    log.info("Resolved %d curated items", len(curated_items))

    # Use ISO week to build the publish date (Monday of that week).
    iso_year = pending_data["iso_year"]
    iso_week = pending_data["iso_week"]
    publish_date = datetime.fromisocalendar(iso_year, iso_week, 1) \
        .replace(tzinfo=ZoneInfo("Europe/Amsterdam"))

    sources_used = [c.source for c in curated_items]
    log.info("=== Rendering HTML ===")
    digest_html = render_digest(curated_items, publish_date, sources_used)
    digest_path = write_digest(digest_html, publish_date)
    write_digest_data(curated_items, publish_date, sources_used)

    log.info("=== Updating index ===")
    digests = scan_existing_digests()
    index_html = render_index(digests)
    write_index(index_html)

    log.info("Done. Digest: %s", digest_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
