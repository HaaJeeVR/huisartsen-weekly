"""Pipeline entry point: fetch -> curate -> render -> write."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fetch import fetch_all, load_sources
from curate import curate
from resolver import resolve_items
from render import (
    render_digest, render_index, scan_existing_digests,
    write_digest, write_digest_data, write_index,
)

log = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    sources_path = Path(__file__).parent / "sources.yaml"
    config = load_sources(str(sources_path))

    log.info("=== Fetching candidates ===")
    candidates = fetch_all(str(sources_path))

    if len(candidates) < config["editorial"]["min_items"]:
        log.error("Too few candidates (%d); aborting to avoid a thin digest.",
                  len(candidates))
        return 1

    log.info("=== Curating with Claude ===")
    curated = curate(candidates, config)

    if len(curated) < config["editorial"]["min_items"]:
        log.warning("Editor returned %d items, below min_items=%d. "
                    "Publishing anyway.",
                    len(curated), config["editorial"]["min_items"])

    log.info("=== Resolving primary sources for aggregator items ===")
    resolve_items(curated)

    log.info("=== Rendering HTML ===")
    publish_date = datetime.now(ZoneInfo("Europe/Amsterdam"))
    sources_used = [c.source for c in curated]
    digest_html = render_digest(curated, publish_date, sources_used)
    digest_path = write_digest(digest_html, publish_date)
    write_digest_data(curated, publish_date, sources_used)

    log.info("=== Updating index ===")
    digests = scan_existing_digests()
    index_html = render_index(digests)
    write_index(index_html)

    log.info("Done. Digest: %s", digest_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
