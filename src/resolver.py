"""Resolve aggregator URLs to primary sources.

When a curated item points to an aggregator (HuisartsVandaag, Google News),
ask Claude with web_search to find the actual primary source: the underlying
report, official document, or originating news outlet.

Falls back gracefully to the original URL when no better source is found.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import anthropic

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 2048
MAX_RETRIES = 3
RETRY_DELAY = 5

# Domains we treat as aggregators that warrant resolution.
AGGREGATOR_DOMAINS = {
    "huisartsvandaag.nl",
    "news.google.com",
}


@dataclass
class ResolvedSource:
    primary_url: str
    primary_source_name: str
    kind: str               # "report", "outlet", or "none"
    reasoning: str


SYSTEM_PROMPT = """Je bent een onderzoeker die voor een persdigest de meest primaire bron
van een nieuwsverhaal opzoekt. Je krijgt een artikel van een Nederlandse aggregator
(HuisartsVandaag of Google News). Vind via web_search de meest gezaghebbende
oorspronkelijke bron.

Prioriteit:
1. ONDERLIGGEND RAPPORT of officieel document: de feitelijke publicatie waar het verhaal
   op gebaseerd is. Bijvoorbeeld een factsheet van BS Health Consultancy, een IGJ-rapport,
   een NHG-standaard, een DNB-publicatie, een rechterlijke uitspraak, een Kamerbrief.
   Liefst een PDF of officiele pagina van de uitgevende organisatie.

2. NIEUWSOUTLET die het verhaal als eerste of meest grondig bracht (niet weer een
   aggregator). Bijvoorbeeld Skipr, Zorgvisie, NOS, Volkskrant, FD, Telegraaf. Linken naar
   de eigen pagina van die outlet, niet naar Google News.

3. Als geen van beide te vinden is: kind = "none".

Belangrijke regels:
- LINK NOOIT NAAR EEN ANDERE AGGREGATOR. Geen Google News URLs, geen HuisartsVandaag URLs.
- Verifieer dat de URL bestaat en het verhaal daadwerkelijk behandelt voor je hem teruggeeft.
- Bij twijfel tussen rapport en outlet: kies het rapport.
- Als alleen een paywalled outlet beschikbaar is en daarachter het echte rapport zit,
  link dan naar het rapport.

Lever EXACT dit JSON-object, niets anders (geen markdown, geen toelichting buiten JSON):

{
  "primary_url": "<https URL of null>",
  "primary_source_name": "<naam uitgever zoals 'Skipr' of 'BS Health Consultancy' of null>",
  "kind": "report" | "outlet" | "none",
  "reasoning": "<een zin uitleg waarom dit de juiste bron is>"
}
"""


def is_aggregator_url(url: str) -> bool:
    """True if the URL points to a known aggregator we want to resolve."""
    try:
        host = urlparse(url).netloc.lower()
        host = host.removeprefix("www.")
        return host in AGGREGATOR_DOMAINS
    except Exception:
        return False


def _build_user_prompt(title: str, source: str, summary: str, url: str) -> str:
    return (
        f"Titel: {title}\n"
        f"Huidige bron (aggregator): {source}\n"
        f"Huidige URL: {url}\n"
        f"Samenvatting uit RSS:\n{summary}\n\n"
        f"Vind de primaire bron volgens de regels in het systeem-prompt."
    )


def _parse_response(raw: str) -> Optional[dict]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        log.warning("Resolver returned invalid JSON: %s. Raw: %s", e, raw[:300])
        return None


def _extract_text_blocks(response) -> str:
    """Concatenate all text blocks from a Claude response.

    With web_search enabled, the response may include tool_use and search-result
    blocks interleaved with text. We only need the final text.
    """
    chunks = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            chunks.append(block.text)
    return "\n".join(chunks)


def resolve_one(client: anthropic.Anthropic, title: str, source: str,
                summary: str, url: str) -> Optional[ResolvedSource]:
    """Run one resolver call with retry. Returns None on failure."""
    user = _build_user_prompt(title, source, summary, url)
    last_err: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=[{"type": "web_search_20250305", "name": "web_search",
                        "max_uses": 4}],
                messages=[{"role": "user", "content": user}],
            )
            raw = _extract_text_blocks(response)
            parsed = _parse_response(raw)
            if not parsed:
                return None

            primary_url = parsed.get("primary_url")
            if not primary_url or primary_url in ("null", "None"):
                return ResolvedSource(
                    primary_url="",
                    primary_source_name="",
                    kind="none",
                    reasoning=parsed.get("reasoning", ""),
                )

            # Safety: refuse to return another aggregator
            if is_aggregator_url(primary_url):
                log.warning("Resolver returned another aggregator URL: %s", primary_url)
                return None

            return ResolvedSource(
                primary_url=primary_url,
                primary_source_name=parsed.get("primary_source_name") or "",
                kind=parsed.get("kind", "outlet"),
                reasoning=parsed.get("reasoning", ""),
            )

        except Exception as e:
            last_err = e
            log.warning("Resolver call failed (attempt %d/%d): %s",
                        attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)

    log.error("Resolver exhausted retries: %s", last_err)
    return None


def resolve_items(items, force_all: bool = False):
    """Resolve aggregator items in-place by updating their url, source, via_source, via_url.

    `items` is a list of CuratedItem. Mutates them.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("No ANTHROPIC_API_KEY; skipping resolution.")
        return

    client = anthropic.Anthropic(api_key=api_key)

    for item in items:
        if not force_all and not is_aggregator_url(item.url):
            continue

        log.info("Resolving primary source for: %s", item.title[:80])
        resolved = resolve_one(client, item.title, item.source,
                               item.summary, item.url)
        if not resolved or resolved.kind == "none" or not resolved.primary_url:
            log.info("  -> no primary source found, keeping original")
            continue

        log.info("  -> %s (%s): %s",
                 resolved.primary_source_name, resolved.kind, resolved.primary_url)

        # Move original (aggregator) into via_*, set primary as main link
        item.via_source = item.source
        item.via_url = item.url
        item.url = resolved.primary_url
        item.source = resolved.primary_source_name or item.source
        item.primary_kind = resolved.kind
