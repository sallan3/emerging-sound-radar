"""Paths and settings shared across the pipeline."""

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
