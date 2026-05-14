"""Curated item dataclass.

In v2 (hybride model) cureert Cowork de items zelf — geen Anthropic SDK
call meer in deze module. Dit bestand bevat alleen nog de CuratedItem
dataclass die door render.py en publish_digest.py wordt gebruikt.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CuratedItem:
    title: str
    url: str
    source: str
    category: str
    published: str         # YYYY-MM-DD
    summary: str           # Feitelijke samenvatting in eigen woorden
    why_it_matters: str    # Opinionated take vanuit banker-perspectief
    rank: int              # 1 = belangrijkste
    # Set wanneer de originele URL een aggregator was en Cowork een primaire
    # bron heeft gevonden. via_* bewaren het ontdekkingspad.
    via_source: str = ""
    via_url: str = ""
    primary_kind: str = ""   # "report" | "outlet" | "" (none)
