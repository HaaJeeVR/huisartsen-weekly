"""Use Claude as senior editor to curate items and write commentary.

Input: list of NewsItem candidates from fetch.py.
Output: list of CuratedItem with selection, summary, and 'why-this-matters'.

Includes retry logic and a JSON-only response contract.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import anthropic

from fetch import NewsItem

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4096
MAX_RETRIES = 3
RETRY_DELAY = 5


@dataclass
class CuratedItem:
    title: str
    url: str
    source: str
    category: str
    published: str
    summary: str           # Feitelijke samenvatting in eigen woorden
    why_it_matters: str    # Opinionated take vanuit banker-perspectief
    rank: int              # 1 = belangrijkste
    # Set by resolver when the original URL was an aggregator and a primary
    # source was found. The via_* fields preserve the discovery path.
    via_source: str = ""
    via_url: str = ""
    primary_kind: str = ""   # "report" | "outlet" | "" (none)


SYSTEM_PROMPT = """Je bent senior redacteur van een wekelijkse digest over de Nederlandse huisartsenzorg.
De lezer is een private banker met een portefeuille huisartsenpraktijken als zakelijke klant.
Hij is geinteresseerd in: bekostiging en tarieven, regelgeving, praktijkeconomie, overname/opvolging,
arbeidsmarkt, organisatiepolitiek (zorggroepen, ROHA, transitieakkoorden), digitalisering met
financiele of operationele impact, en maatschappelijke debatten die de positie van huisartsen raken.

Hij is NIET geinteresseerd in puur klinische onderzoeksresultaten, patient-facing voorlichting,
of casuistiek zonder bredere relevantie.

Schrijfstijl: direct, opinionated, geen consultancy-blabla. Korte zinnen. Geen jargon zonder reden.
Geen em-dashes. Schrijf in het Nederlands. Geen open deuren als 'het is belangrijk om te onthouden'.

Je krijgt een lijst kandidaat-artikelen. Selecteer er {min_items} tot {max_items} (streven: {target_items}).
Voor elk geselecteerd item lever je:
- summary: 2-3 zinnen feitelijke samenvatting in jouw eigen woorden, geen citaten
- why_it_matters: 1-2 zinnen waarom dit ertoe doet voor een banker met huisarts-klanten, met
  een concrete, opinionated take. Geen platitudes.

Lever JSON terug, niets anders. Geen markdown, geen toelichting, geen ```json fences.
Schema:
{{
  "items": [
    {{
      "url": "<exacte URL uit input>",
      "summary": "...",
      "why_it_matters": "...",
      "rank": 1
    }}
  ]
}}
Rank 1 = belangrijkste item van de week, vervolgens 2, 3, etc.
Als er minder dan {min_items} relevante items zijn, lever dan minder. Vul niet op met irrelevant nieuws.
"""


def _build_user_prompt(items: list[NewsItem]) -> str:
    """Render candidate list as numbered block for the editor."""
    lines = ["Kandidaten van de afgelopen week:\n"]
    for i, item in enumerate(items, 1):
        lines.append(f"[{i}] {item.title}")
        lines.append(f"    Bron: {item.source} ({item.category})")
        lines.append(f"    Datum: {item.published.strftime('%Y-%m-%d')}")
        lines.append(f"    URL: {item.url}")
        if item.summary:
            lines.append(f"    Samenvatting bron: {item.summary[:400]}")
        lines.append("")
    return "\n".join(lines)


def _call_claude_with_retry(client: anthropic.Anthropic, system: str,
                            user: str) -> str:
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return resp.content[0].text
        except Exception as e:
            last_err = e
            log.warning("Claude call failed (attempt %d/%d): %s",
                        attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
    raise RuntimeError(f"Claude failed after {MAX_RETRIES} attempts: {last_err}")


def _parse_response(raw: str) -> list[dict[str, Any]]:
    """Extract JSON from response, tolerant of stray markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    data = json.loads(text.strip())
    return data.get("items", [])


def curate(items: list[NewsItem], config: dict[str, Any]) -> list[CuratedItem]:
    """Run the editorial pass and return ranked curated items."""
    if not items:
        log.warning("No candidate items to curate.")
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)
    ed = config["editorial"]
    system = SYSTEM_PROMPT.format(
        target_items=ed["target_items"],
        min_items=ed["min_items"],
        max_items=ed["max_items"],
    )
    user = _build_user_prompt(items)

    raw = _call_claude_with_retry(client, system, user)
    parsed = _parse_response(raw)
    log.info("Editor selected %d items", len(parsed))

    # Match selected URLs back to original items.
    url_to_item = {i.url: i for i in items}
    curated: list[CuratedItem] = []
    for sel in parsed:
        url = sel.get("url", "").strip()
        original = url_to_item.get(url)
        if not original:
            log.warning("Editor returned unknown URL: %s", url)
            continue
        curated.append(CuratedItem(
            title=original.title,
            url=original.url,
            source=original.source,
            category=original.category,
            published=original.published.strftime("%Y-%m-%d"),
            summary=sel.get("summary", "").strip(),
            why_it_matters=sel.get("why_it_matters", "").strip(),
            rank=int(sel.get("rank", 99)),
        ))
    curated.sort(key=lambda c: c.rank)
    return curated
