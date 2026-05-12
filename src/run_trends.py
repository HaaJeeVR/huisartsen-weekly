"""Entry point for the monthly trend analysis workflow."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from render import (
    render_trends_report, scan_existing_trends,
    write_trends_report,
)
from trends import TrendReport, analyse_trends, load_recent_digests

log = logging.getLogger(__name__)

DUTCH_MONTHS = {
    1: "januari", 2: "februari", 3: "maart", 4: "april",
    5: "mei", 6: "juni", 7: "juli", 8: "augustus",
    9: "september", 10: "oktober", 11: "november", 12: "december",
}


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    log.info("=== Loading recent digest data ===")
    items, weeks = load_recent_digests(weeks_back=6)
    log.info("Loaded %d items across %d weeks", len(items), len(weeks))

    if len(items) < 6:
        log.error("Te weinig digest-items (%d) voor zinvolle trend-analyse. "
                  "Heb minimaal 2-3 weken nodig.", len(items))
        return 1

    log.info("=== Analysing trends ===")
    trends = analyse_trends(items)
    if not trends:
        log.error("Geen thema's gevonden door de analist.")
        return 1

    now = datetime.now(ZoneInfo("Europe/Amsterdam"))
    period_label = f"{DUTCH_MONTHS[now.month].capitalize()} {now.year}"

    # Get earliest and latest dates from items
    item_dates = [datetime.fromisoformat(i.get("published", "1970-01-01"))
                  for i in items if i.get("published")]
    period_start = min(item_dates).date().isoformat() if item_dates else ""
    period_end = max(item_dates).date().isoformat() if item_dates else now.date().isoformat()

    report = TrendReport(
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
        weeks_covered=weeks,
        item_count=len(items),
        trends=trends,
        generated_at=now.isoformat(),
    )

    log.info("=== Rendering trends report ===")
    prior = scan_existing_trends()
    html = render_trends_report(report, prior)
    write_trends_report(html, now)

    log.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
