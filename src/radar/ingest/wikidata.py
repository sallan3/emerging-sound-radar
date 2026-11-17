"""Wikidata join layer: Discogs artist ID -> English Wikipedia article.

Uses Wikidata property P1953 (Discogs artist ID). Rather than pulling every P1953
statement, it queries only candidate artists from the Discogs parquet: artists with
at least `min_works` distinct works (masters, or releases without a master), since
artists with one or two records rarely have a Wikipedia article.

Writes data/interim/artist_wikipedia_map.parquet with columns:
    discogs_artist_id, wikidata_qid, enwiki_title

Usage:
    python -m radar.ingest.wikidata --min-works 3
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from urllib.parse import unquote

import duckdb
import pandas as pd
import requests

from radar.config import INTERIM, USER_AGENT

SPARQL_URL = "https://query.wikidata.org/sparql"
DEFAULT_RELEASES = INTERIM / "discogs_releases.parquet"
DEFAULT_OUT = INTERIM / "artist_wikipedia_map.parquet"

# Discogs uses artist 194 for "Various"; it is not a real artist.
EXCLUDED_ARTIST_IDS = {194}

QUERY_TEMPLATE = """
SELECT ?discogs ?item ?article WHERE {{
  VALUES ?discogs {{ {values} }}
  ?item wdt:P1953 ?discogs .
  ?article schema:about ?item ;
           schema:isPartOf <https://en.wikipedia.org/> .
}}
"""


def candidate_artist_ids(releases_path: Path, min_works: int = 3) -> list[int]:
    """Artists credited on at least `min_works` distinct works in the releases parquet.

    A work is a master, or a release on its own when it has no master, so represses
    and reissues of the same record count once.
    """
    query = """
        SELECT artist_id
        FROM (
            SELECT unnest(artist_ids) AS artist_id,
                   coalesce(master_id, -release_id) AS work_id
            FROM read_parquet(?)
        )
        GROUP BY artist_id
        HAVING count(DISTINCT work_id) >= ?
        ORDER BY artist_id
    """
    ids = duckdb.execute(query, [str(releases_path), min_works]).fetchall()
    return [i for (i,) in ids if i not in EXCLUDED_ARTIST_IDS]


def chunked(items: list[int], size: int) -> Iterator[list[int]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def build_query(artist_ids: Iterable[int]) -> str:
    # P1953 values are stored as strings in Wikidata
    values = " ".join(f'"{i}"' for i in artist_ids)
    return QUERY_TEMPLATE.format(values=values)


def parse_response(payload: dict) -> list[dict]:
    rows = []
    for binding in payload["results"]["bindings"]:
        discogs = binding["discogs"]["value"]
        if not discogs.isdigit():
            continue
        article_url = binding["article"]["value"]
        rows.append(
            {
                "discogs_artist_id": int(discogs),
                "wikidata_qid": binding["item"]["value"].rsplit("/", 1)[-1],
                # Keep the URL form (underscores, decoded) used by the pageviews API
                "enwiki_title": unquote(article_url.split("/wiki/", 1)[-1]),
            }
        )
    return rows


def fetch_chunk(
    session: requests.Session, artist_ids: list[int], max_retries: int = 5
) -> list[dict]:
    query = build_query(artist_ids)
    for attempt in range(max_retries):
        try:
            response = session.post(
                SPARQL_URL,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json"},
                timeout=90,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            wait = 30 * (attempt + 1)
            print(f"{type(exc).__name__}, retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        if response.status_code == 200:
            return parse_response(response.json())
        if response.status_code in (429, 500, 502, 503, 504):
            wait = int(response.headers.get("Retry-After", 2 ** (attempt + 1)))
            print(f"status {response.status_code}, retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        response.raise_for_status()
    raise RuntimeError(f"Wikidata query failed after {max_retries} attempts")


COLUMNS = ["discogs_artist_id", "wikidata_qid", "enwiki_title"]


def build_map(
    artist_ids: list[int],
    chunk_size: int = 400,
    pause: float = 1.0,
    cache_dir: Path | None = None,
) -> pd.DataFrame:
    """Query Wikidata chunk by chunk. With `cache_dir`, each finished chunk is saved there
    and skipped on a rerun, so a crash part-way through does not lose earlier work."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []
    chunks = list(chunked(artist_ids, chunk_size))
    cached = 0
    for n, chunk in enumerate(chunks, start=1):
        path = cache_dir / f"{chunk[0]}_{chunk[-1]}_{len(chunk)}.parquet" if cache_dir else None
        if path is not None and path.exists():
            frames.append(pd.read_parquet(path))
            cached += 1
        else:
            frame = pd.DataFrame(fetch_chunk(session, chunk), columns=COLUMNS)
            if path is not None:
                frame.to_parquet(path, index=False)
            frames.append(frame)
            time.sleep(pause)
        if n % 25 == 0 or n == len(chunks):
            matches = sum(len(f) for f in frames)
            print(
                f"chunk {n}/{len(chunks)} ({cached} cached): {matches:,} matches", file=sys.stderr
            )
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)
    # One Discogs ID can map to several Wikidata items (e.g. duplicates); keep the first
    return frame.drop_duplicates("discogs_artist_id").reset_index(drop=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Map Discogs artist IDs to Wikipedia articles")
    parser.add_argument("--releases", type=Path, default=DEFAULT_RELEASES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--min-works", type=int, default=3)
    parser.add_argument("--chunk-size", type=int, default=400)
    parser.add_argument("--pause", type=float, default=2.0, help="Seconds between queries")
    args = parser.parse_args(argv)

    ids = candidate_artist_ids(args.releases, args.min_works)
    print(f"{len(ids):,} candidate artists with >= {args.min_works} works", file=sys.stderr)
    cache_dir = args.out.parent / "wikidata_chunks"
    frame = build_map(ids, args.chunk_size, pause=args.pause, cache_dir=cache_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.out, index=False)
    print(f"matched {len(frame):,} of {len(ids):,} ({len(frame) / max(len(ids), 1):.1%})")


if __name__ == "__main__":
    main()
