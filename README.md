# Huisartsen Weekly

Wekelijkse digest over de Nederlandse huisartsenzorg, geautomatiseerd verzameld
en redactioneel gecureerd in Cowork. Elke maandag een nieuwe editie,
gepubliceerd via GitHub Pages.

## Architectuur (v2 hybride)

Dit project bestaat uit twee helften, met een duidelijke knip:

**Cloud-kant (GitHub Actions, gratis)**

1. Elke maandagochtend draait een workflow die tien RSS-feeds van vakbronnen,
   beroepsverenigingen en toezichthouders pullt, plus vijf Google News queries
   voor landelijke + lokale dekking.
2. Items van de afgelopen 7 dagen worden gededupliceerd op canonical URL en
   fuzzy titel-match.
3. De ruwe kandidatenlijst wordt naar `pending/YYYY-Www.json` geschreven en
   teruggecommit naar de repo.

**Lokaal in Cowork (jouw Claude Pro abonnement, geen API kosten)**

4. Jij opent Cowork ergens deze week, pulled de repo, en vraagt Claude de
   pending-JSON te lezen.
5. Cowork (Claude) cureert: selectie van 4-8 items, feitelijke samenvatting +
   opinionated "Waarom dit ertoe doet" vanuit banker-perspectief.
6. Voor items uit aggregators (HuisartsVandaag, Google News): Cowork gebruikt
   WebFetch/WebSearch om de primaire bron op te zoeken (onderliggend rapport,
   IGJ-publicatie, of originele nieuwsoutlet).
7. Cowork schrijft de selectie naar `curated/YYYY-Www.json`.
8. Cowork draait `python src/publish_digest.py --week YYYY-Www`. Dit rendert
   de HTML naar `docs/digests/`, schrijft een sidecar JSON voor latere
   trend-analyse, en werkt de index bij.
9. Cowork doet `git commit && git push`. GitHub Pages serveert het direct.

Naast de wekelijkse digest is er een **maandelijkse themabriefing**, ook in
Cowork: Claude leest 6 weken aan digest-JSONs, identificeert 3-5 blogwaardige
thema's per stuk met stelling/contraire invalshoek/banker-angle/blog-brief, en
publiceert via `python src/publish_trends.py --month YYYY-MM`.

Lens: private banker met portefeuille huisartsenpraktijken. Focus op
bekostiging, regelgeving, praktijkeconomie, arbeidsmarkt, organisatiepolitiek
en digitalisering met financiele impact. Geen klinisch.

## Eenmalige setup

1. Clone deze repo naar je GitHub account (of fork hem).
2. **Settings > Pages**: source = "Deploy from a branch", branch = `main`,
   folder = `/docs`.
3. **Settings > Actions > General**: zet "Workflow permissions" op
   "Read and write permissions" zodat de fetch-workflow kan terugcommitten.
4. Trigger eenmalig handmatig: **Actions > Weekly Fetch Candidates >
   Run workflow**. Na ~2 minuten staat er een `pending/YYYY-Www.json` in je
   repo.

## Wekelijkse run in Cowork

Zie [`COWORK.md`](./COWORK.md) voor het volledige runbook met copy-paste
prompts. Verkorte versie:

```
cd huisartsen-weekly
git pull
# Open Cowork in deze folder
# Vraag: "Cureer de pending digest voor deze week"
# Cowork doet de selectie + schrijft curated/YYYY-Www.json
python src/publish_digest.py --latest
git add docs/ curated/
git commit -m "Digest week YYYY-Www"
git push
```

## Repo structuur

```
.github/workflows/
  fetch-candidates.yml       # cloud: wekelijkse fetch
src/
  fetch.py                   # RSS + Google News pullen
  fetch_candidates.py        # Actions entry: writes pending/
  publish_digest.py          # Cowork entry: reads curated + publishes
  publish_trends.py          # Cowork entry: rendert maandbriefing
  curate.py                  # CuratedItem dataclass (geen LLM-code)
  resolver.py                # is_aggregator_url helper
  trends.py                  # Trend-dataclasses + load_recent_digests
  render.py                  # Jinja templates -> HTML
  sources.yaml               # feeds + Google News queries
  templates/                 # Jinja2 HTML templates
pending/                     # Actions schrijft hier kandidatenlijsten
curated/                     # Cowork schrijft hier de selectie
curated_trends/              # Cowork schrijft hier maand-analyses
docs/                        # GitHub Pages serveert deze folder
  digests/                   # gepubliceerde wekelijkse digests
  trends/                    # gepubliceerde maandbriefings
  style.css
```

## Waarom hybride?

De oude v1-architectuur draaide Claude via de Anthropic API binnen GitHub
Actions. Dat werkte maar kostte 1-3 euro per maand en vereiste een aparte
API-account. In v2 is de redactionele intelligentie verplaatst naar Cowork
(jouw Pro-abonnement), terwijl de saaie fetch-stap nog steeds in de cloud
draait. Resultaat: nul API-kosten, jij blijft redactionele controle houden,
en de pipeline is robuuster omdat een falende LLM-call de cron niet meer
kan breken.

Trade-off: je moet één keer per week ~10 minuten in Cowork bezig zijn om de
digest live te krijgen. Als je dat niet doet, mis je die editie. De cloud-
fetch blijft wel doorlopen, dus je kunt later altijd nog inhalen.
