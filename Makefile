PYTHON ?= python3
VENV = .venv
BIN = $(VENV)/bin

.PHONY: setup lint format test sample

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
