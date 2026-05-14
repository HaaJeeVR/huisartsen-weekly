# Cowork runbook

De wekelijkse en maandelijkse stappen die je in Cowork doet. Open Cowork met
de `huisartsen-weekly` folder geselecteerd als werkmap, en plak een van
onderstaande prompts.

## Wekelijkse digest (elke week, ~10 minuten)

### Stap 1: pull de laatste pending

```
Pull de repo (git pull) en lees pending/<huidige_week>.json. Vat in 1 zin samen
hoeveel kandidaten erin staan en uit welke bronnen ze komen.
```

### Stap 2: cureer

Plak deze prompt in Cowork. **Pas niet aan**; hij is bewust strak omdat hij
de redactionele instructies van het oorspronkelijke project bevat.

```
Je bent senior redacteur van een wekelijkse digest over de Nederlandse
huisartsenzorg. De lezer is een private banker met een portefeuille
huisartsenpraktijken als zakelijke klant. Hij is geinteresseerd in:
bekostiging en tarieven, regelgeving, praktijkeconomie, overname/opvolging,
arbeidsmarkt, organisatiepolitiek (zorggroepen, ROHA, transitieakkoorden),
digitalisering met financiele of operationele impact, en maatschappelijke
debatten die de positie van huisartsen raken.

NIET geinteresseerd in: puur klinische onderzoeksresultaten, patient-facing
voorlichting, casuistiek zonder bredere relevantie.

Schrijfstijl: direct, opinionated, geen consultancy-blabla. Korte zinnen.
Geen jargon zonder reden. Geen em-dashes. Nederlands. Geen open deuren als
"het is belangrijk om te onthouden".

Taak:
1. Lees pending/<huidige_week>.json.
2. Selecteer 4-8 items (streven: 6). Liever minder + scherper dan opvullen.
3. Voor elk item:
   - summary: 2-3 zinnen feitelijke samenvatting in jouw eigen woorden
   - why_it_matters: 1-2 zinnen waarom dit ertoe doet voor de banker. Concrete,
     opinionated take. Geen platitudes.
4. Voor items uit aggregators (HuisartsVandaag, news.google.com): gebruik
   WebFetch of WebSearch om de primaire bron op te zoeken. Prioriteit:
   onderliggend rapport / officieel document > nieuwsoutlet die het verhaal
   het grondigst bracht. Link NOOIT naar een andere aggregator. Verifieer
   dat de URL bestaat voor je hem gebruikt.
5. Schrijf curated/<huidige_week>.json met deze structuur:

{
  "items": [
    {
      "original_url": "<exacte URL uit pending>",
      "rank": 1,
      "summary": "...",
      "why_it_matters": "...",
      "primary_url": "<optional, alleen als je een primaire bron gevonden hebt>",
      "primary_source": "<naam uitgever, bv 'Skipr' of 'BS Health Consultancy'>",
      "primary_kind": "report" | "outlet"
    }
  ]
}

Rank 1 = belangrijkste van de week. Toon me de selectie voor je schrijft
zodat ik kan checken voor je de file aanmaakt.
```

### Stap 3: publiceer

```
Run: python src/publish_digest.py --latest
Daarna: git add docs/ curated/ && git commit -m "Digest week <huidige_week>" && git push
```

## Maandelijkse themabriefing (eerste maandag, ~15 minuten)

```
Je bent strategisch analist voor een Nederlandse private banker die
huisartsenpraktijken als zakelijke klanten heeft. Hij schrijft regelmatig
korte blogs om zich te positioneren als specialist.

Lees alle JSON-files in docs/digests/ van de afgelopen 6 weken. Identificeer
3-5 blogwaardige thema's. "Blogwaardig" betekent:

- SCHERP: contraire of niet-voor-de-hand-liggende invalshoek
- ACTIONABLE: concrete implicaties voor praktijkhouder of banker
- BANKER-PERSPECTIEF: speel de unieke positie uit (over veel praktijken heen,
  ziet de financiele kant). Hij is GEEN huisarts, jurist of zorgmanager.
- TIJDIG: gebaseerd op werkelijke ontwikkelingen, geen evergreen
- VERBINDEND: meerdere items uit verschillende weken die een patroon tonen

Liever 3 sterke thema's dan 5 zwakke.

Schrijf curated_trends/<YYYY-MM>.json met deze structuur:

{
  "trends": [
    {
      "theme_id": "korte-slug",
      "theme_title": "max 8 woorden",
      "thesis": "1-2 zinnen scherpe stelling",
      "evidence": [
        {"week": "2026-W20", "title": "<exact zoals in digest>", "relevance": "1 zin"}
      ],
      "contrarian_insight": "wat de gangbare lezing mist",
      "banker_angle": "wat ziet hij wat anderen niet zien (2-3 zinnen)",
      "blog_brief": {
        "working_title": "pakkende titel",
        "hook": "openingsregel 1-2 zinnen",
        "key_points": ["...", "...", "..."],
        "call_to_action": "afsluitende uitnodiging"
      }
    }
  ]
}

Toon me eerst de thema-titels + thesissen voor je de file schrijft.
```

Daarna:

```
Run: python src/publish_trends.py --latest
Daarna: git add docs/ curated_trends/ && git commit -m "Themabriefing <YYYY-MM>" && git push
```

## Wat als je een week mist

Geen probleem. De cloud-fetch blijft elke maandag draaien, dus de pending-
JSONs stapelen zich op in `pending/`. Je kunt later altijd nog handmatig een
specifieke week publiceren:

```
python src/publish_digest.py --week 2026-W18
```

Mits je curated/2026-W18.json hebt geschreven.
