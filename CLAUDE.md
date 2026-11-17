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
   Old monthly dumps are still downloadable by year, e.g.
   https://data.discogs.com/?download=data%2F2024%2Fdiscogs_20240701_releases.xml.gz
   (the old discogs-data-dumps.s3 URLs return 403 as of Nov 2026). data.discogs.com is behind
   Cloudflare: it returns 429 with a ~20 min Retry-After after a burst of requests, and ignores
   Range headers, so interrupted downloads restart from zero.
   Plan: compare the current dump with one older dump (e.g. Jan 2023) to measure the lag curve
   (how complete a quarter is N months later) and correct recent quarters, rather than
   downloading a dump for every vintage.
2. Wikipedia coverage bias: underground artists often have no article. Report match rate per style.
3. Dump size: stream-parse, filter early, store as Parquet. A full parse of the releases dump
   (~17M releases in mid-2024) takes on the order of hours; use `--limit` while developing.
4. Reissue inflation: the same record appears as many releases (pressings, represses, reissues).
   Supply counts unique masters, dated by the earliest version; releases without a master count
   on their own. Otherwise a wave of vinyl represses looks like a new scene.
5. Date precision: many Discogs releases only have a year ("1999" or "1999-00-00"). The parser
   records precision (day/month/year/none). Measure the share with month precision before
   committing to quarterly supply; fall back to annual supply features if it is too low.
6. Artist-to-style attribution for demand: an artist's pageviews are split across styles in
   proportion to that artist's releases per style in the trailing window (not all-time), so an
   artist who moves from house to techno moves their attention with them.
7. Superstar dominance: a few huge artists (filed under House etc.) can swamp a style's summed
   pageviews, and news spikes (deaths, scandals) distort single quarters. Measure style demand on
   a log scale (e.g. mean of log1p quarterly views per matched artist, or median per-artist
   growth) rather than raw sums, and use `agent=user` pageviews only.
8. Thin styles: set a minimum number of matched artists per style (start at 15) for a style to
   enter the model; report excluded styles rather than silently dropping them.
9. Wikidata coverage: the join only queries artists with >= 3 works (`--min-works`). Report the
   match rate overall and per style; it will be far lower for underground styles.

## Constraints

- Personal project, personal environment only. Never use Evident data, PitchBook data, Evident code,
  or the `evident-data-dev` GCP project.
- Do not commit raw paid or rate-limited third-party data. Commit code, a small CC0/derived sample
  in data/sample/, and style-level aggregates only where terms allow.
- Keep API keys in environment variables (.env, gitignored).
- No emojis in code.

## Working conventions

- Build in Claude Code from the repo root (it reads this file automatically, runs on the Mac with
  the project venv, can run long jobs and commit as sallan3). Use the Claude chat for research
  (data sources, terms) and writing (README, application note); update this file when either
  changes the plan.
- Git identity is set locally in this repo (sallan3, no-reply email); never use --global here.
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

## Decisions

- Scope: all Electronic releases for the model; write-up focused on house/techno and neighbours.
- Storage: local DuckDB + Parquet (reproducible, no GCP account needed).
- Style-article pageviews (e.g. the "Hard groove" Wikipedia page): cross-check only. Demand and
  the target use artist pageviews only. Report how many styles have a matching article and
  whether style-article views move with artist-based demand; promote to a feature later only if
  coverage and correlation are good. (Many styles have no article; genre-page views measure
  curiosity more than listening.)
- Work in review checkpoints: after the first run on real data, stop, report, update this file
  and commit before starting multi-hour jobs.

## Open decisions

- Timing: apply after weekend 1 with the baseline version, or wait for the full project?
- Soundcharts: pay for one month after the sandbox check?

## Next steps

Done:
- Repo published at github.com/sallan3/emerging-sound-radar (private for now).
- Plan reviewed 17 Nov 2026 (pitfalls 4-9 added; scope and storage decided).
- Discogs streaming parser (`src/radar/ingest/discogs.py`): Electronic only, release-level
  artists only, master_id + is_main_release, date precision, Parquet output. Fixture tests in
  `tests/test_discogs.py`. Synthetic benchmark: ~30k releases/s scanned, ~260 MB peak memory.
- Wikidata P1953 join (`src/radar/ingest/wikidata.py`): candidates = artists with >= 3 works
  (masters, or releases without a master), chunked SPARQL with retries. Offline tests in
  `tests/test_wikidata.py`. NOT yet run against the live endpoint.
- Make targets: `make discogs [LIMIT=200000] [DUMP=...]` (DUMP defaults to the latest dump in
  data/raw), `make wikidata [MIN_WORKS=3]`.
- Keys in `.env`: Discogs token, Last.fm key, Wikimedia user agent, Soundcharts sandbox.
- Dumps in data/raw (17 Nov 2026, both gzip-verified): discogs_20261101_releases.xml.gz
  (11.4 GB) and discogs_20230101_releases.xml.gz (11.6 GB, for the lag curve).

Findings from the first real-data runs (17 Nov 2026, steps 5-6):
- Sample = first 200k Electronic releases of the 20261101 dump. The dump is ordered by
  release_id, so this sample is release ids 1-213k, almost all released 1985-2005: nothing in
  the 2015-2026 window. Shares below describe old catalogue, not the analysis window.
- Real dump vs fixture: (a) releases without a master have `<master_id>0</master_id>`, not a
  missing tag; the parser stored 0, which would merge ~20% of releases into one "work".
  Fixed (0 -> None) with a test. (b) No `status` attribute on releases, so `status` is all
  null. (c) Each release has `data_quality` (e.g. "Correct"), not parsed yet.
- Parse speed: 200k Electronic releases in 10 s, 240 MB peak memory. Early ids are almost all
  Electronic, so the full-dump rate is still unknown; expect tens of minutes, not hours.
- Sample date precision: year 66.0%, day 23.0%, month 9.7%, none 1.3% (month-or-better 33%).
  Month share rises over time (23% for 1990-94, 45% for 2000-04). Quarterly vs annual cannot be
  decided until the full parse covers 2015-2026.
- Sample masters: 79.4% of releases have a master; 44.5% are the main release; 107,767
  distinct masters. 8.2% are credited to "Various" (artist 194). Styles missing on 0.04%.
- Top sample styles by works (master, or release without one): House 36.0k, Techno 32.4k,
  Trance 16.2k, Deep House 12.6k, Electro 10.9k, Downtempo 10.4k, Hardcore 9.8k,
  Experimental 9.6k, Breakbeat 9.4k, Drum n Bass 9.3k (period-skewed: 1990s-heavy).
- Wikidata live check works (MIN_WORKS=20: 433 of 693 = 62.5%, 11 s). Full sample run
  (MIN_WORKS=3): 3,949 of 14,432 candidates = 27.4% in 3.3 min (one 429, honoured
  Retry-After). Per style: House 34%, Techno 23%, Deep House 31%, Tech House 26%,
  Acid 21%, Hard Trance 19%, Hardcore 16%; Downtempo/Disco/Electro/Ambient 46-54%.
  Underground dance styles match worst, as expected. Usable but thin for techno.
- Aliases: several Discogs artist ids map to the same article (Wolfgang Voigt 15 ids,
  Uwe Schmidt 10). 3,949 ids -> 3,797 articles. Pageviews must be fetched and counted once
  per article, with alias ids pooled for style attribution.

To do (Sofia):
1. Test the Soundcharts sandbox for Beatport chart endpoints and history depth.
2. Email Songstats about trial API access.

To do (next build steps, in Claude Code):
7. Full `make discogs` run on the 20261101 dump, then re-run `make wikidata`; re-check date
   precision and match rates for 2015-2026 releases only; decide quarterly vs annual supply.
8. Pageviews ingest for mapped artists + style articles.
9. Supply and demand panels, labels, momentum baseline.
