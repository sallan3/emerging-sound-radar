# Emerging Sound Radar

Which dance music styles have rising demand but not enough new releases?

> Work in progress. The answer, chart and recommendation will go here first.

## The answer

_To come: top styles by supply-demand gap, one chart, and a short recommendation._

## How it works

- **Supply:** new releases per style from the Discogs monthly data dumps (CC0).
- **Demand:** attention per style from Wikipedia pageviews (from July 2015).
- **Forecast:** which styles' demand will grow fastest over the next 4 quarters,
  tested with a rolling backtest against a simple momentum baseline.

## Run it

```bash
make setup     # create .venv and install
cp .env.example .env   # add API keys (optional for the sample run)
make sample    # run end-to-end on the cached sample
make test
```

## Limitations

_To come._

## Data credits

Discogs data dumps (CC0). Wikimedia pageviews API. Last.fm (data used under the
Last.fm API terms; see https://www.last.fm).
