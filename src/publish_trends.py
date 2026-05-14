"""Read a Cowork-curated trend report and publish it.

Cowork leest de digest-JSONs van afgelopen weken (via trends.load_recent_digests),
analyseert de patronen zelf, en schrijft het rapport naar
curated_trends/YYYY-MM.json. Dit script leest dat en rendert de HTML.

Usage:
    python src/publish_trends.py --month 2026-05
    python src/publish_trends.py --latest
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from render import (
    render_trends_report, scan_existing_trends, write_trends_report,
)
from trends import (
    BlogBrief, Trend, TrendEvidence, TrendReport, build_evidence,
    load_recent_digests,
)

log = logging.getLogger(__name__)

CURATED_TRENDS_DIR = Path(__file__).parent.parent / "curated_trends"

DUTCH_MONTHS = {
    1: "januari", 2: "februari", 3: "maart", 4: "april",
    5: "mei", 6: "juni", 7: "juli", 8: "augustus",
    9: "september", 10: "oktober", 11: "november", 12: "december",
}


def _find_latest_month() -> str | None:
    if not CURATED_TRENDS_DIR.exists():
        return None
    months = sorted(p.stem for p in CURATED_TRENDS_DIR.glob("*.json"))
    return months[-1] if months else None


def _build_report(curated_data: dict, items: list[dict],
                  weeks: list[str], now: datetime) -> TrendReport:
    trends: list[Trend] = []
    for t in curated_data.get("trends", []):
        brief_data = t.get("blog_brief", {})
        brief = BlogBrief(
            working_title=brief_data.get("working_title", ""),
            hook=brief_data.get("hook", ""),
            key_points=brief_data.get("key_points", []),
            call_to_action=brief_data.get("call_to_action", ""),
        )
        trends.append(Trend(
            theme_id=t.get("theme_id", ""),
            theme_title=t.get("theme_title", ""),
            thesis=t.get("thesis", ""),
            evidence=build_evidence(t.get("evidence", []), items),
            contrarian_insight=t.get("contrarian_insight", ""),
            banker_angle=t.get("banker_angle", ""),
            blog_brief=brief,
        ))

    period_label = f"{DUTCH_MONTHS[now.month].capitalize()} {now.year}"
    item_dates = [
        datetime.fromisoformat(i.get("published", "1970-01-01"))
        for i in items if i.get("published")
    ]
    period_start = min(item_dates).date().isoformat() if item_dates else ""
    period_end = max(item_dates).date().isoformat() if item_dates else now.date().isoformat()

    return TrendReport(
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
        weeks_covered=weeks,
        item_count=len(items),
        trends=trends,
        generated_at=now.isoformat(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--month", help="YYYY-MM, bv 2026-05")
    group.add_argument("--latest", action="store_true",
                       help="Gebruik de meest recente maand met curated_trends JSON")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    month_key = args.month
    if args.latest:
        month_key = _find_latest_month()
        if not month_key:
            log.error("Geen curated_trends JSON gevonden.")
            return 1
        log.info("Using latest month: %s", month_key)

    curated_path = CURATED_TRENDS_DIR / f"{month_key}.json"
    if not curated_path.exists():
        log.error("Curated trends file ontbreekt: %s", curated_path)
        log.error("Cowork moet eerst de themabriefing wegschrijven.")
        return 1

    curated_data = json.loads(curated_path.read_text(encoding="utf-8"))

    log.info("=== Loading recent digest data voor evidence-mapping ===")
    items, weeks = load_recent_digests(weeks_back=6)
    log.info("Loaded %d items across %d weeks", len(items), len(weeks))

    now = datetime.now(ZoneInfo("Europe/Amsterdam"))
    report = _build_report(curated_data, items, weeks, now)

    log.info("=== Rendering trends report ===")
    prior = scan_existing_trends()
    html = render_trends_report(report, prior)
    write_trends_report(html, now)

    log.info("Done. %d trends gerenderd.", len(report.trends))
    return 0


if __name__ == "__main__":
    sys.exit(main())
