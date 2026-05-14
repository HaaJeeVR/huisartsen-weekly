"""Helpers voor het herkennen van aggregator-URLs.

In v2 doet Cowork de resolution zelf via WebFetch/WebSearch. Dit bestand
bevat alleen nog de helper-functie en een lijst van bekende aggregators
zodat Cowork kan checken of een URL nog opgelost moet worden.
"""

from __future__ import annotations

from urllib.parse import urlparse

AGGREGATOR_DOMAINS = {
    "huisartsvandaag.nl",
    "news.google.com",
}


def is_aggregator_url(url: str) -> bool:
    """True als de URL naar een bekende aggregator wijst die we willen resolven."""
    try:
        host = urlparse(url).netloc.lower()
        host = host.removeprefix("www.")
        return host in AGGREGATOR_DOMAINS
    except Exception:
        return False
