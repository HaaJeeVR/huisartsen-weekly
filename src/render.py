"""Render curated items to HTML and maintain the archive index."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from curate import CuratedItem

log = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
DOCS_DIR = Path(__file__).parent.parent / "docs"
DIGESTS_DIR = DOCS_DIR / "digests"
TRENDS_DIR = DOCS_DIR / "trends"

DUTCH_MONTHS = {
    1: "januari", 2: "februari", 3: "maart", 4: "april",
    5: "mei", 6: "juni", 7: "juli", 8: "augustus",
    9: "september", 10: "oktober", 11: "november", 12: "december",
}


def _dutch_date(d: datetime) -> str:
    return f"{d.day} {DUTCH_MONTHS[d.month]} {d.year}"


def _iso_week_filename(d: datetime) -> str:
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}.html"


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["dutch_date"] = _dutch_date
    return env


def render_digest(items: list[CuratedItem], publish_date: datetime,
                  sources_used: list[str]) -> str:
    """Render a single weekly digest to HTML."""
    iso_year, iso_week, _ = publish_date.isocalendar()
    template = _env().get_template("digest.html.j2")
    return template.render(
        items=items,
        publish_date=publish_date,
        publish_date_human=_dutch_date(publish_date),
        iso_year=iso_year,
        iso_week=iso_week,
        item_count=len(items),
        source_count=len(set(sources_used)),
    )


def render_index(digests: list[dict]) -> str:
    """Render the archive index page."""
    trend_reports = scan_existing_trends()
    template = _env().get_template("index.html.j2")
    return template.render(digests=digests, trend_reports=trend_reports)


def write_digest(html: str, publish_date: datetime) -> Path:
    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
    path = DIGESTS_DIR / _iso_week_filename(publish_date)
    path.write_text(html, encoding="utf-8")
    log.info("Wrote digest to %s", path)
    return path


def write_digest_data(items: list[CuratedItem], publish_date: datetime,
                      sources_used: list[str]) -> Path:
    """Write a sidecar JSON file with structured data for trend analysis."""
    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
    iso_year, iso_week, _ = publish_date.isocalendar()
    stem = _iso_week_filename(publish_date).rsplit(".", 1)[0]
    path = DIGESTS_DIR / f"{stem}.json"
    data = {
        "iso_year": iso_year,
        "iso_week": iso_week,
        "publish_date": publish_date.isoformat(),
        "html_filename": _iso_week_filename(publish_date),
        "source_count": len(set(sources_used)),
        "items": [asdict(i) for i in items],
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote digest data to %s", path)
    return path


def write_index(html: str) -> Path:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    path = DOCS_DIR / "index.html"
    path.write_text(html, encoding="utf-8")
    log.info("Wrote index to %s", path)
    return path


def render_trends_report(report, prior_reports: list[dict]) -> str:
    """Render a monthly trends report to HTML."""
    template = _env().get_template("trends.html.j2")
    return template.render(report=report, prior_reports=prior_reports)


def write_trends_report(html: str, period_end: datetime) -> Path:
    TRENDS_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"{period_end.year}-{period_end.month:02d}.html"
    path = TRENDS_DIR / fname
    path.write_text(html, encoding="utf-8")
    log.info("Wrote trends report to %s", path)
    return path


def scan_existing_trends() -> list[dict]:
    """Scan docs/trends/ and return metadata for the trends index."""
    if not TRENDS_DIR.exists():
        return []
    reports = []
    pattern = re.compile(r"^(\d{4})-(\d{2})\.html$")
    for path in sorted(TRENDS_DIR.glob("*.html"), reverse=True):
        m = pattern.match(path.name)
        if not m:
            continue
        year, month = int(m.group(1)), int(m.group(2))
        date_obj = datetime(year, month, 1)
        reports.append({
            "filename": path.name,
            "year": year,
            "month": month,
            "month_label": f"{DUTCH_MONTHS[month].capitalize()} {year}",
            "url": path.name,
        })
    return reports


def scan_existing_digests() -> list[dict]:
    """Scan docs/digests/ and return metadata for the index."""
    if not DIGESTS_DIR.exists():
        return []
    digests = []
    pattern = re.compile(r"^(\d{4})-W(\d{2})\.html$")
    for path in sorted(DIGESTS_DIR.glob("*.html"), reverse=True):
        m = pattern.match(path.name)
        if not m:
            continue
        year, week = int(m.group(1)), int(m.group(2))
        monday = datetime.fromisocalendar(year, week, 1)
        digests.append({
            "filename": path.name,
            "year": year,
            "week": week,
            "date_human": _dutch_date(monday),
            "url": f"digests/{path.name}",
        })
    return digests


def load_recent_digest_data(weeks_back: int = 6) -> list[dict]:
    """Load digest JSON sidecar files from the past N ISO weeks, newest first.

    Returns list of dicts with iso_year, iso_week, publish_date, items.
    """
    if not DIGESTS_DIR.exists():
        return []
    pattern = re.compile(r"^(\d{4})-W(\d{2})\.json$")
    found = []
    for path in DIGESTS_DIR.glob("*.json"):
        m = pattern.match(path.name)
        if not m:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            found.append(data)
        except Exception as e:
            log.warning("Could not read %s: %s", path, e)
    found.sort(key=lambda d: (d.get("iso_year", 0), d.get("iso_week", 0)),
               reverse=True)
    return found[:weeks_back]
