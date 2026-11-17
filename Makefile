PYTHON ?= python3
VENV = .venv
BIN = $(VENV)/bin

.PHONY: setup lint format test sample discogs wikidata

# Latest releases dump in data/raw unless DUMP=... is given
DUMP ?= $(lastword $(sort $(wildcard data/raw/discogs_*_releases.xml.gz)))
MIN_WORKS ?= 3

setup:  ## Create the virtual environment and install the package with dev tools
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"

lint:
	$(BIN)/ruff check src tests

format:
	$(BIN)/ruff format src tests

test:
	$(BIN)/pytest

sample:  ## Run the full pipeline on the cached sample in data/sample (to be implemented)
	@echo "Not implemented yet"

discogs:  ## Parse the Discogs releases dump (Electronic only). Optional: LIMIT=200000 DUMP=path
	$(BIN)/python -m radar.ingest.discogs $(DUMP) $(if $(LIMIT),--limit $(LIMIT))

wikidata:  ## Map Discogs artists with >= MIN_WORKS works to English Wikipedia
	$(BIN)/python -m radar.ingest.wikidata --min-works $(MIN_WORKS)
