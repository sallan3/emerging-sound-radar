"""Discogs monthly releases dump (CC0).

Stream-parses the gzipped releases XML, keeps releases in one genre (Electronic by
default) and writes one row per release to data/interim/discogs_releases.parquet.

Only release-level artists are kept. Artists credited on individual tracks
(tracklist/track/artists) and extra credits (extraartists) are ignored, because the
release-level credit is what defines who "made" the record.

Usage:
    python -m radar.ingest.discogs data/raw/discogs_20261101_releases.xml.gz --limit 200000
"""

from __future__ import annotations

import argparse
import gzip
import re
import sys
import time
from collections.abc import Iterable, Iterator
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from lxml import etree

from radar.config import INTERIM

TARGET_GENRE = "Electronic"
DEFAULT_OUT = INTERIM / "discogs_releases.parquet"

# Discogs dates come as "1999-03-14", "1999-03-00", "1999-00-00", "1999" or junk.
_DATE_RE = re.compile(r"^\s*(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?")

SCHEMA = pa.schema(
    [
        ("release_id", pa.int64()),
        ("master_id", pa.int64()),
        ("is_main_release", pa.bool_()),
        ("status", pa.string()),
        ("title", pa.string()),
        ("released_raw", pa.string()),
        ("year", pa.int16()),
        ("month", pa.int8()),
        ("date_precision", pa.string()),
        ("country", pa.string()),
        ("styles", pa.list_(pa.string())),
        ("artist_ids", pa.list_(pa.int64())),
        ("label_ids", pa.list_(pa.int64())),
        ("label_names", pa.list_(pa.string())),
    ]
)


def parse_released(value: str | None) -> tuple[int | None, int | None, str]:
    """Return (year, month, precision) where precision is day, month, year or none."""
    if not value:
        return None, None, "none"
    match = _DATE_RE.match(value)
    if not match:
        return None, None, "none"
    year = int(match.group(1))
    if year < 1900:
        return None, None, "none"
    month = int(match.group(2)) if match.group(2) else 0
    day = int(match.group(3)) if match.group(3) else 0
    if not 1 <= month <= 12:
        return year, None, "year"
    if not 1 <= day <= 31:
        return year, month, "month"
    return year, month, "day"


def _text(parent: etree._Element, path: str) -> str | None:
    node = parent.find(path)
    if node is None or node.text is None:
        return None
    text = node.text.strip()
    return text or None


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    return int(value) if value.isdigit() else None


def parse_release(elem: etree._Element, genre: str = TARGET_GENRE) -> dict | None:
    """Turn one <release> element into a row, or None if it is not in the genre."""
    genres = [g.text.strip() for g in elem.findall("genres/genre") if g.text]
    if genre not in genres:
        return None

    master = elem.find("master_id")
    master_id = _to_int(master.text) if master is not None else None
    # The real dump writes <master_id>0</master_id> for releases without a master
    if master_id == 0:
        master_id = None
    is_main = master_id is not None and master.get("is_main_release") == "true"

    released_raw = _text(elem, "released")
    year, month, precision = parse_released(released_raw)

    labels = elem.findall("labels/label")

    return {
        "release_id": _to_int(elem.get("id")),
        "master_id": master_id,
        "is_main_release": is_main,
        "status": elem.get("status"),
        "title": _text(elem, "title"),
        "released_raw": released_raw,
        "year": year,
        "month": month,
        "date_precision": precision,
        "country": _text(elem, "country"),
        "styles": [s.text.strip() for s in elem.findall("styles/style") if s.text],
        # "artists/artist/id" is relative to <release>, so track-level credits are excluded
        "artist_ids": [
            i for i in (_to_int(a.text) for a in elem.findall("artists/artist/id")) if i is not None
        ],
        "label_ids": [i for i in (_to_int(lab.get("id")) for lab in labels) if i is not None],
        "label_names": [lab.get("name") for lab in labels if lab.get("name")],
    }


def _open(path: Path):
    return gzip.open(path, "rb") if path.suffix == ".gz" else open(path, "rb")


def iter_releases(
    path: Path,
    genre: str = TARGET_GENRE,
    limit: int | None = None,
    progress_every: int = 500_000,
) -> Iterator[dict]:
    """Yield rows for releases in `genre`, keeping memory flat on multi-GB dumps.

    `limit` caps the number of rows yielded (matching releases), not releases scanned.
    """
    scanned = kept = 0
    started = time.monotonic()
    with _open(Path(path)) as fh:
        for _, elem in etree.iterparse(fh, events=("end",), tag="release", huge_tree=True):
            row = parse_release(elem, genre)
            scanned += 1

            # Free memory: clear this element and drop already-processed siblings
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

            if progress_every and scanned % progress_every == 0:
                rate = scanned / max(time.monotonic() - started, 1e-9)
                print(f"scanned {scanned:,} kept {kept:,} ({rate:,.0f}/s)", file=sys.stderr)

            if row is None:
                continue
            kept += 1
            yield row
            if limit is not None and kept >= limit:
                break


def write_parquet(rows: Iterable[dict], out: Path, batch_size: int = 50_000) -> int:
    """Write rows to Parquet in batches. Returns the number of rows written."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    batch: list[dict] = []
    with pq.ParquetWriter(out, SCHEMA, compression="zstd") as writer:
        for row in rows:
            batch.append(row)
            if len(batch) >= batch_size:
                writer.write_table(pa.Table.from_pylist(batch, schema=SCHEMA))
                written += len(batch)
                batch = []
        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=SCHEMA))
            written += len(batch)
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("dump", type=Path, help="Path to discogs_YYYYMMDD_releases.xml.gz")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--genre", default=TARGET_GENRE)
    parser.add_argument("--limit", type=int, default=None, help="Stop after N matching releases")
    args = parser.parse_args(argv)

    n = write_parquet(iter_releases(args.dump, args.genre, args.limit), args.out)
    print(f"wrote {n:,} {args.genre} releases to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
