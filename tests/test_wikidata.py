import pyarrow as pa
import pyarrow.parquet as pq

from radar.ingest.discogs import SCHEMA
from radar.ingest.wikidata import build_query, candidate_artist_ids, chunked, parse_response


def _release(release_id, master_id, artist_ids):
    return {
        "release_id": release_id,
        "master_id": master_id,
        "is_main_release": False,
        "status": "Accepted",
        "title": "t",
        "released_raw": "2020",
        "year": 2020,
        "month": None,
        "date_precision": "year",
        "country": "UK",
        "styles": ["Techno"],
        "artist_ids": artist_ids,
        "label_ids": [],
        "label_names": [],
    }


def test_candidates_count_works_not_pressings(tmp_path):
    rows = [
        # Artist 1: three pressings of one master -> 1 work
        _release(1, 100, [1]),
        _release(2, 100, [1]),
        _release(3, 100, [1]),
        # Artist 2: two masters + one release without master -> 3 works
        _release(4, 200, [2]),
        _release(5, 201, [2]),
        _release(6, None, [2, 194]),
        # "Various" (194) is excluded even with enough works
        _release(7, 300, [194]),
        _release(8, 301, [194]),
    ]
    path = tmp_path / "releases.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), path)

    assert candidate_artist_ids(path, min_works=3) == [2]
    assert candidate_artist_ids(path, min_works=1) == [1, 2]


def test_build_query_quotes_ids():
    query = build_query([1, 23])
    assert 'VALUES ?discogs { "1" "23" }' in query
    assert "wdt:P1953" in query


def test_parse_response():
    payload = {
        "results": {
            "bindings": [
                {
                    "discogs": {"value": "3909"},
                    "item": {"value": "http://www.wikidata.org/entity/Q193338"},
                    "article": {"value": "https://en.wikipedia.org/wiki/Moby"},
                },
                {
                    "discogs": {"value": "1234"},
                    "item": {"value": "http://www.wikidata.org/entity/Q1"},
                    "article": {"value": "https://en.wikipedia.org/wiki/R%C3%B6yksopp"},
                },
            ]
        }
    }
    assert parse_response(payload) == [
        {"discogs_artist_id": 3909, "wikidata_qid": "Q193338", "enwiki_title": "Moby"},
        {"discogs_artist_id": 1234, "wikidata_qid": "Q1", "enwiki_title": "Röyksopp"},
    ]


def test_chunked():
    assert list(chunked([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
