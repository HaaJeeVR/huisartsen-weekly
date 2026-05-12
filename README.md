# Huisartsen Weekly

Wekelijkse digest over de Nederlandse huisartsenzorg, geautomatiseerd verzameld
en redactioneel gecureerd door Claude. Elke maandagochtend een nieuwe editie,
gepubliceerd via GitHub Pages.

## Wat het is

Een Python-pijplijn die op maandagochtend:

1. Tien RSS-feeds van vakbronnen, beroepsverenigingen en toezichthouders pullt
2. Drie Google News queries draait voor landelijke + lokale dekking
3. Items van de afgelopen 7 dagen filtert en dedupliceert
4. Claude als senior redacteur 4-8 items laat selecteren en voorzien van
   feitelijke samenvatting + opinionated "Waarom dit ertoe doet"
5. Voor items uit aggregators (HuisartsVandaag, Google News): Claude met
   web_search de primaire bron laat opzoeken (onderliggend rapport, IGJ-
   publicatie, of originele nieuwsoutlet) en daar naar laat linken
6. De editie als statische HTML naar `docs/digests/YYYY-Www.html` schrijft,
   plus een sidecar JSON met gestructureerde data voor trend-analyse
7. De index pagina bijwerkt
8. Het geheel terugcommit naar de repo; GitHub Pages serveert het

Naast de wekelijkse digest draait er een **maandelijkse themabriefing**, op de
eerste maandag van elke maand:

1. Leest alle digest-JSON van de afgelopen 6 weken
2. Claude als strategisch analist identificeert 3-5 blogwaardige thema's
3. Per thema: stelling, bewijs uit items, contraire invalshoek, banker-angle,
   en een kant-en-klare blog brief (werktitel, hook, key points, CTA)
4. Wegschrijven naar `docs/trends/YYYY-MM.html`

Lens: private banker met portefeuille huisartsenpraktijken. Focus op
bekostiging, regelgeving, praktijkeconomie, arbeidsmarkt, organisatiepolitiek
en digitalisering met financiele impact. Geen klinisch.

## Eenmalige setup

1. **Clone deze repo naar je GitHub account** (of fork hem).

2. **Voeg je Anthropic API key toe als repo secret:**
   - Repo settings → Secrets and variables → Actions → New repository secret
   - Naam: `ANTHROPIC_API_KEY`
   - Waarde: je API key

3. **Zet GitHub Pages aan:**
   - Repo settings → Pages
   - Source: Deploy from a branch
   - Branch: `main` (of je default branch), folder: `/docs`
   - Save. Binnen een minuut staat je site op
     `https://<je-username>.github.io/huisartsendigest/`

4. **Geef GitHub Actions schrijfrechten:**
   - Repo settings → Actions → General → Workflow permissions
   - "Read and write permissions" aanvinken
   - Save

5. **Test handmatig:**
   - Tab Actions → Weekly Huisartsen Digest → Run workflow
   - Wacht ~1 minuut, dan staat de eerste editie online

Daarna draait alles autonoom. Elke maandag 07:00 Europe/Amsterdam.

## Lokaal draaien

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
cd src
python main.py
```

Resultaat: `docs/digests/<huidige-week>.html` en bijgewerkte `docs/index.html`.

## Bronnen aanpassen

Open `src/sources.yaml`. Drie secties:

- `rss_feeds`: directe RSS van vakbronnen, met gewicht (1.0 = hoog vertrouwen)
- `google_news_queries`: zoektermen voor breed nieuws
- `editorial`: aantal items, lookback, prioriteits-thema's voor de redacteur

Een feed kapot? Niks aan de hand; de pijplijn slaat hem over en logt het.
Wel handig om af en toe je Actions-logs te checken.

## Mappenstructuur

```
huisartsendigest/
├── .github/workflows/
│   ├── weekly-digest.yml              # maandag 07:00 lokaal
│   └── monthly-trends.yml             # eerste maandag 08:00 lokaal
├── src/
│   ├── sources.yaml                   # bronnen en redactionele criteria
│   ├── fetch.py                       # RSS + Google News, dedup
│   ├── curate.py                      # Claude als redacteur
│   ├── resolver.py                    # primaire bronnen voor aggregators
│   ├── trends.py                      # maandelijkse thema-analyse
│   ├── render.py                      # Jinja2 -> HTML, JSON sidecar
│   ├── main.py                        # wekelijkse pijplijn
│   ├── run_trends.py                  # maandelijkse pijplijn
│   └── templates/
│       ├── digest.html.j2
│       ├── index.html.j2
│       └── trends.html.j2
├── docs/                              # GitHub Pages root
│   ├── index.html
│   ├── style.css
│   ├── digests/
│   │   ├── 2026-W20.html              # leesbare digest
│   │   └── 2026-W20.json              # gestructureerde data voor trends
│   └── trends/
│       └── 2026-05.html               # maandelijkse themabriefing
└── README.md
```

## Kosten

Per wekelijkse run ongeveer 30-60 cent. De maandelijkse trend-analyse kost
ongeveer 20-40 cent extra (een enkele grote API-call met 6 weken data).
Totaal per jaar: 20 tot 40 euro.

## Failsafes

- Eén crashende feed laat de rest doorlopen
- Claude API call krijgt 3x retry met backoff
- Bij minder dan 3 kandidaat-items: pijplijn stopt, geen thin digest
- Workflow heeft `concurrency` group, kan dus geen overlap geven
- Twee cron-triggers per maandag (05:00 + 06:00 UTC) zodat we het hele jaar
  rond 07:00 lokaal draaien; dedup-check voorkomt dubbele digests

## Wat het niet doet (bewust)

- Geen zoekfunctie over het archief (komt later, indien gewenst)
- Geen trend-detectie over meerdere weken (komt later)
- Geen notificatie dat de digest klaar is (open vraag: wil je dit via mail of
  Telegram?)
- Geen javascript runtime; bewust statisch en cacheable
- Geen cookies, tracking, of advertenties


## Maandelijkse themabriefing

Naast de wekelijkse digest draait er op de eerste maandag van elke maand
een tweede pijplijn: `run_trends.py`. Die leest de structured data van de
afgelopen 4 tot 6 weken aan digests (sidecar JSON-bestanden naast elke
HTML), en vraagt Claude als strategisch analist om 3 tot 5 thema's te
identificeren die door de weken heenliepen en blog-waardig zijn.

Per thema lever de briefing:

- Een scherpe stelling (1-2 zinnen, niet generiek)
- 2-5 evidence-items met links naar de oorspronkelijke digests
- Een contraire invalshoek (wat mist de mainstream-lezing?)
- Een banker-angle (wat zie jij wat anderen niet zien?)
- Een kant-en-klare blog brief: werktitel, hook, 3-4 kernpunten, CTA

Output: `docs/trends/YYYY-MM.html`. Wordt vanuit de hoofd-index gelinkt.

### Trigger

- Automatisch elke eerste maandag van de maand, 08:00 Europe/Amsterdam
- Handmatig via tab Actions → Monthly Themabriefing → Run workflow
  (bijvoorbeeld wanneer je op een specifiek moment inspiratie nodig hebt)

### Wat het niet doet

Het is bewust geen frequentie-analyse of grafiek. De inschatting is dat
een thema pas blog-waardig is als je er 600-1000 woorden over kunt
schrijven met een eigen invalshoek, en dat kan Claude beter beoordelen
dan een woord-teller.

## Licentie

Voor persoonlijk gebruik. Bronartikelen blijven eigendom van de oorspronkelijke
uitgevers; deze digest linkt door en herhaalt geen significante passages.
