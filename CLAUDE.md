# Emerging Sound Radar (POC)

Portfolio project for a Data Scientist application at Melotech. Started November 2026.

## Brief

Melotech (Berlin, legal entity Canopus GmbH, founder/CEO Soheil Mirpour) is an AI-native media
company: it produces music, video and apps at scale, creates tracks, curates playlists and builds
video channels. It reports 2B+ minutes heard/watched in ~18 months and is backed by Cherry Ventures,
Speedinvest and GFC. Still largely in stealth.

The role (first dedicated Data Scientist; Berlin / London / NYC listings) asks for:
- opening up new, messy data sources and making them reliable
- analysing trends, audience behaviour and performance to find growth opportunities
- prototyping and deploying forecasting / content-analysis models (AWS)
- designing and reading experiments (A/B tests, holdouts)
- owning leadership dashboards and explaining metric changes
- using LLMs and agentic coding tools in data workflows
- bonus: strong interest in music, video or social media

The application asks for a link to something built on GitHub. This repo is that link.

## What this project is trying to achieve

One focused, reproducible project that does the job described above, applied to music.

Core question: which dance music styles have rising demand but not enough new releases?
That supply-demand gap is where an AI-native studio should produce next.

- Supply = new releases per style (Discogs)
- Demand = attention per style (Wikipedia pageviews; optionally Beatport chart points)
- Output = a ranked list of styles with forecast demand growth, supply growth and the gap,
  plus a written recommendation ("if I were commissioning 10 tracks next month...")

What a reviewer should see in about 2 minutes: the question, the answer, one chart and the
recommendation at the top of the README; an honest backtest against a simple baseline below it.

## Method (summary)

- Unit of analysis: style x quarter, 2015 Q3 to 2026 Q3 (Wikipedia pageviews start July 2015).
- Target: does a style's demand growth over the next 4 quarters land in the top 20% of styles,
  measured relative to electronic music overall?
- Features at time t only (no look-ahead): release growth, share of releases by first-time artists,
  new labels entering, number of countries releasing, pageview acceleration (last 3m vs prior 3m).
- Baseline: plain momentum (rank by last year's growth). The model must beat this; report honestly
  if it only just does.
- Backtest: rolling origin (train to year Y, predict Y+1), precision@10 per year.
- LLM component: map messy Last.fm tags (and Beatport genres) onto Discogs styles; hand-label ~200
  and report accuracy.

Example of the intended output (illustrative numbers only):

    style            p_breakout   demand_growth_fcst   supply_growth   gap
    Hard Groove      0.71         +0.34                +0.12           +0.22
    Baile Funk       0.64         +0.29                +0.09           +0.20

## Data sources

### Free core (the repo must run end-to-end on these)

| Source | Gives | History | Role | Notes |
|---|---|---|---|---|
| Discogs monthly data dumps (data.discogs.com) | Releases with styles, dates, labels, countries, artists | Decades | Supply panel | CC0 licence. Releases dump is multi-GB gzipped XML; stream with lxml iterparse and keep genre=Electronic only. API: 25 req/min anonymous, 60 with token. |
| Wikidata | Discogs artist ID (P1953) -> Wikipedia article | n/a | Join layer | SPARQL query |
| Wikimedia pageviews REST API | Daily views per article | From 2015-07-01 | Demand panel | Free, no key |
| Last.fm API | Listener counts, free-text tags | Snapshots only | LLM tag mapping; optional weekly collector | Non-commercial by default; credit + link back; max 100 MB stored. Do not commit raw dumps. |

### Optional paid layer (Beatport demand)

| Source | Status | Notes |
|---|---|---|
| Soundcharts API | Best candidate | Self-serve from $50/month (10k queries). Has Beatport charts and a historical charts API. Free sandbox (app id / key: soundcharts / soundcharts). Before paying, check in the sandbox: (1) how far back Beatport history goes (want 2021 or earlier), (2) whether chart-history endpoints are "premium" / excluded from the base plan, (3) terms on publishing derived data. Popularity scores only go back 90 days, so chart history is what matters. |
| Songstats API | Email api@songstats.com | Only option with 1001Tracklists DJ-support data (earliest dance music signal). Enterprise, pricing not public, history depth undocumented. Ask for trial access for a portfolio project; do not plan around it. |
| BeatStats | Method only | Website, no API/export. Borrow the idea: compute chart points from daily Beatport Top 100 positions (e.g. points = 101 - position, summed per style per quarter). |

If Beatport data is used: build a Beatport genre -> Discogs style mapping table (another LLM +
accuracy check), and test whether Beatport points and Wikipedia pageviews move together.

### Ruled out (mention in README as limitations / what I'd license at Melotech)

- Spotify Web API: Feb 2026 changes (Premium required for Developer Mode, 5 test users, endpoints
  cut); developer terms restrict using Spotify content for ML/AI.
- Google Trends: official API is an application-only alpha; pytrends archived April 2025.
- 1001Tracklists: no official API; do not scrape into a public repo.
- Managed scrapers of Beatport (e.g. Anakin Wire): live pages only (no history) and rely on getting
  around anti-bot protection; Beatport's own v4 API is partner-gated. Wrong signal for a
  rights-sensitive company.

## Context worth using in the write-up

- Beatport announced (13 Aug 2026) it will reject fully or mostly AI-generated tracks; AI-assisted,
  majority-human tracks are still accepted. So Beatport is a demand signal for which styles are
  rising, but likely not a release channel for Melotech's own output.

## Known pitfalls

1. Discogs cataloguing lag: recent releases are entered late, so recent quarters look smaller.
   Prefer point-in-time features (use an older monthly dump as-of date t if still available).
2. Wikipedia coverage bias: underground artists often have no article. Report match rate per style.
3. Dump size: stream-parse, filter early, store as Parquet.

## Constraints

- Personal project, personal environment only. Never use Evident data, PitchBook data, Evident code,
  or the `evident-data-dev` GCP project.
- Do not commit raw paid or rate-limited third-party data. Commit code, a small CC0/derived sample
  in data/sample/, and style-level aggregates only where terms allow.
- Keep API keys in environment variables (.env, gitignored).
- No emojis in code.

## Working conventions

- Editor: VS Code. Interpreter is `.venv/bin/python` (see .vscode/settings.json). Ruff formats on save.
- Commands: `make setup` (venv + install with dev extras), `make lint`, `make format`, `make test`,
  `make sample` (end-to-end on data/sample/, to be implemented).
- Package code lives in `src/radar/`; import as `from radar import ...`. Paths come from `radar.config`.
- Each ingest module writes Parquet to `data/interim/`; panel/features/labels write to `data/processed/`.
- `data/raw/`, `data/interim/`, `data/processed/` and `.env` are gitignored. Only `data/sample/` is committed.
- CI (GitHub Actions) runs ruff and pytest on every push.

## Repo layout

    emerging-sound-radar/
      README.md              question, answer, one chart, recommendation up top
      Makefile               `make sample` runs end-to-end on cached data
      src/radar/
        ingest/  discogs.py  wikidata.py  pageviews.py  lastfm.py  (soundcharts.py optional)
        panel.py  labels.py  features.py  backtest.py  tag_mapping.py
      data/sample/           small Parquet extract so reviewers need no keys
      reports/radar_2026Q4.md
      tests/
      .github/workflows/weekly_snapshot.yml   (stretch)

## Schedule

- Weekend 1: Discogs ingest + supply panel; Wikidata join; pageviews + demand panel; labels;
  momentum baseline. (Enough to apply with.)
- Weekend 2: features, model, rolling backtest; LLM tag mapping with accuracy check; README,
  chart, written recommendation. Optional: Soundcharts Beatport layer, weekly Last.fm collector.

Melotech's process: 30-min intro call, 90-min case interview, 90-min founder interview; can move
from start to offer within a week. The project doubles as case-interview material.

## Open decisions

- Scope: all electronic for the model, write-up focused on house/techno? (leaning yes)
- Storage: local DuckDB (reproducible, no GCP account needed) vs personal BigQuery? (leaning DuckDB)
- Timing: apply after weekend 1 with the baseline version, or wait for the full project?
- Soundcharts: pay for one month after the sandbox check?

## Next steps

1. Test the Soundcharts sandbox for Beatport chart endpoints and history depth.
2. Email Songstats about trial API access.
3. Get a Discogs personal token and a Last.fm API key; download the latest Discogs releases dump.
4. Write the Discogs streaming parser and the Wikidata P1953 join query.
