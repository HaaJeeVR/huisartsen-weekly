"""Monthly trend analysis: turn past digest items into blog ideation briefs.

Reads sidecar JSON files from docs/digests/ produced by the weekly run,
asks Claude as strategic analyst to identify 3-5 blog-worthy themes, and
returns structured Trend objects ready for rendering.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import anthropic

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 8192
MAX_RETRIES = 3
RETRY_DELAY = 5

DIGESTS_DIR = Path(__file__).parent.parent / "docs" / "digests"


@dataclass
class TrendEvidence:
    week: str               # e.g. "2026-W20"
    title: str
    relevance: str          # 1-sentence why this supports the theme
    digest_url: str         # link to that week's digest


@dataclass
class BlogBrief:
    working_title: str
    hook: str               # opening line / paragraph
    key_points: list[str]
    call_to_action: str


@dataclass
class Trend:
    theme_id: str           # slug
    theme_title: str
    thesis: str
    evidence: list[TrendEvidence] = field(default_factory=list)
    contrarian_insight: str = ""
    banker_angle: str = ""
    blog_brief: BlogBrief = None  # type: ignore


@dataclass
class TrendReport:
    period_label: str       # "Mei 2026"
    period_start: str       # ISO date
    period_end: str         # ISO date
    weeks_covered: list[str]
    item_count: int
    trends: list[Trend]
    generated_at: str


SYSTEM_PROMPT = """Je bent strategisch analist voor een Nederlandse private banker
die huisartsenpraktijken als zakelijke klanten heeft. Hij schrijft regelmatig korte
blogs om zich te positioneren als specialist. Zijn lezers zijn huisartsen,
praktijkhouders en andere zorgprofessionals.

Op basis van de digest-items van de afgelopen weken identificeer je 3 tot 5 thema's
die blogwaardig zijn. "Blogwaardig" betekent:

- SCHERP: een contraire of niet-voor-de-hand-liggende invalshoek; niet de
  conventionele wijsheid die elke vakgenoot al beschrijft.
- ACTIONABLE: met concrete implicaties voor de praktijkhouder of voor de
  banker zelf. Geen observaties zonder advies.
- BANKER-PERSPECTIEF: hij heeft een unieke positie omdat hij over veel
  praktijken heen kijkt en de financiele kant ziet. Speel die positie uit.
  Hij is GEEN huisarts, geen jurist, geen zorgmanager - hij is bankier.
- TIJDIG: gebaseerd op werkelijke ontwikkelingen in de items, geen evergreen
  content.
- VERBINDEND: meerdere items uit verschillende weken die samen een patroon
  tonen zijn het sterkst. Niet één los nieuwsbericht.

VOORBEELDEN VAN GOEDE ANGLES:
- "Huisvestingsproblemen bij huisartsen zijn geen huisvestingsprobleem maar
  een opvolgingsprobleem"
- "Waarom de winstcijfers van zorgverzekeraars je tarievengesprek 2027
  fundamenteel anders maken"
- "Drie patronen bij overnames van huisartsenpraktijken nu de markt schuift"
- "De stille kostenpost in elke praktijk: continuiteitsrisico in je IT-stack"

VOORBEELDEN VAN SLECHTE ANGLES (NIET GEBRUIKEN):
- "Trends in de huisartsenzorg 2026" (te breed, geen angle)
- "Belangrijk om aandacht voor te hebben: X" (geen invalshoek)
- "Generieke samenvatting van wat speelt" (geen mening)
- Onderwerpen die direct uit een enkele news item komen zonder patroon

Voor elk geidentificeerd thema lever je:
1. theme_title - korte titel, max 8 woorden
2. thesis - 1-2 zinnen scherpe stelling, niet generiek
3. evidence - 2-5 items uit de digest data, met week en titel exact zoals
   in de input, plus een korte relevantie-uitleg per item
4. contrarian_insight - wat de gangbare lezing mist of fout heeft (1-2 zinnen)
5. banker_angle - concrete uitwerking vanuit zijn bankier-positie. Wat ziet
   hij wat anderen niet zien? (2-3 zinnen)
6. blog_brief:
   - working_title: pakkende blogtitel
   - hook: openingsregel of -alinea (1-2 zinnen)
   - key_points: 3 tot 4 punten om in de blog te raken
   - call_to_action: afsluitende uitnodiging tot reactie of contact (1 zin)

Lever EXACT dit JSON-object terug, geen markdown, geen fences, geen toelichting:

{
  "trends": [
    {
      "theme_id": "korte-slug",
      "theme_title": "...",
      "thesis": "...",
      "evidence": [
        {"week": "2026-W20", "title": "exact zoals in input", "relevance": "..."}
      ],
      "contrarian_insight": "...",
      "banker_angle": "...",
      "blog_brief": {
        "working_title": "...",
        "hook": "...",
        "key_points": ["...", "...", "..."],
        "call_to_action": "..."
      }
    }
  ]
}

Schrijf alles in het Nederlands. Korte zinnen. Geen em-dashes. Geen open deuren.
Geef niet 5 thema's als er maar 3 sterk zijn. Liever minder en scherper.
"""


def load_recent_digests(weeks_back: int = 6) -> tuple[list[dict], list[str]]:
    """Load curated items from the past N weeks of sidecar JSON files.

    Returns (items_with_week, weeks_covered).
    items_with_week: each dict has CuratedItem fields plus 'week' label.
    """
    if not DIGESTS_DIR.exists():
        return [], []

    cutoff = datetime.now() - timedelta(weeks=weeks_back)
    all_items: list[dict] = []
    weeks: list[str] = []

    for path in sorted(DIGESTS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Could not parse %s: %s", path, e)
            continue

        publish_dt = datetime.fromisoformat(data["publish_date"])
        # Normalize: compare naive to naive
        if publish_dt.tzinfo:
            publish_dt = publish_dt.replace(tzinfo=None)
        if publish_dt < cutoff:
            continue

        week = f"{data['iso_year']}-W{data['iso_week']:02d}"
        weeks.append(week)
        for item in data.get("items", []):
            item_copy = dict(item)
            item_copy["week"] = week
            item_copy["digest_url"] = f"../digests/{data['html_filename']}"
            all_items.append(item_copy)

    return all_items, sorted(set(weeks))


def _build_user_prompt(items: list[dict]) -> str:
    """Render items grouped by week as readable input for the analyst."""
    by_week: dict[str, list[dict]] = {}
    for item in items:
        by_week.setdefault(item["week"], []).append(item)

    lines = [f"Digest-items uit de afgelopen {len(by_week)} weken:\n"]
    for week in sorted(by_week.keys()):
        lines.append(f"\n=== {week} ===")
        for it in by_week[week]:
            lines.append(f"\n[{it.get('rank', '?')}] {it['title']}")
            lines.append(f"    Bron: {it.get('source', '?')} | Categorie: {it.get('category', '?')}")
            if it.get("via_source"):
                lines.append(f"    Via: {it['via_source']}")
            lines.append(f"    Samenvatting: {it.get('summary', '')}")
            if it.get("why_it_matters"):
                lines.append(f"    Waarom dit ertoe doet: {it['why_it_matters']}")
    lines.append("\n\nIdentificeer 3-5 blogwaardige thema's volgens de regels in het systeem-prompt.")
    return "\n".join(lines)


def _parse_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


def _call_with_retry(client: anthropic.Anthropic, system: str, user: str) -> str:
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
            log.warning("Analyst call failed (attempt %d/%d): %s",
                        attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
    raise RuntimeError(f"Analyst failed after {MAX_RETRIES} attempts: {last_err}")


def _build_evidence(parsed_evidence: list[dict], items: list[dict]) -> list[TrendEvidence]:
    """Map analyst-returned evidence references back to actual digest URLs."""
    title_to_url = {it["title"]: it.get("digest_url", "") for it in items}
    result = []
    for ev in parsed_evidence:
        title = ev.get("title", "").strip()
        result.append(TrendEvidence(
            week=ev.get("week", ""),
            title=title,
            relevance=ev.get("relevance", ""),
            digest_url=title_to_url.get(title, ""),
        ))
    return result


def analyse_trends(items: list[dict]) -> list[Trend]:
    """Run the analyst pass and return structured trends."""
    if len(items) < 4:
        log.warning("Too few items (%d) for meaningful trend analysis.", len(items))
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)
    user = _build_user_prompt(items)

    raw = _call_with_retry(client, SYSTEM_PROMPT, user)
    parsed = _parse_response(raw)

    trends: list[Trend] = []
    for t in parsed.get("trends", []):
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
            evidence=_build_evidence(t.get("evidence", []), items),
            contrarian_insight=t.get("contrarian_insight", ""),
            banker_angle=t.get("banker_angle", ""),
            blog_brief=brief,
        ))
    log.info("Analyst returned %d trends.", len(trends))
    return trends
