"""Fetch candidate items and write them to pending/YYYY-Www.json.

Draait op GitHub Actions; geen Claude API key nodig. Output is bedoeld voor
Cowork om vervolgens redactioneel te cureren.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fetch import fetch_all, load_sources

log = logging.getLogger(__name__)

PENDING_DIR = Path(__file__).parent.parent / "pending"


def _iso_week_key(d: datetime) -> str:
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    sources_path = Path(__file__).parent / "sources.yaml"
    config = load_sources(str(sources_path))

    log.info("=== Fetching candidates ===")
    candidates = fetch_all(str(sources_path))

    min_items = config["editorial"]["min_items"]
    if len(candidates) < min_items:
        log.error("Too few candidates (%d < min %d); aborting.",
                  len(candidates), min_items)
        return 1

    now = datetime.now(ZoneInfo("Europe/Amsterdam"))
    week_key = _iso_week_key(now)

    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PENDING_DIR / f"{week_key}.json"

    payload = {
        "iso_year": now.isocalendar().year,
        "iso_week": now.isocalendar().week,
        "fetched_at": now.isoformat(),
        "candidate_count": len(candidates),
        "candidates": [c.to_dict() for c in candidates],
    }
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("Wrote %d candidates to %s", len(candidates), out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
