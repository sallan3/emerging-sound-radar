"""Paths and settings shared across the pipeline."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
SAMPLE = DATA / "sample"
REPORTS = ROOT / "reports"

# Analysis window: Wikipedia pageviews start July 2015
START_QUARTER = "2015Q3"
END_QUARTER = "2026Q3"

# Wikimedia asks API clients to identify themselves with contact details
USER_AGENT = os.getenv(
    "WIKIMEDIA_USER_AGENT",
    "emerging-sound-radar/0.1 (https://github.com/sallan3/emerging-sound-radar)",
)
