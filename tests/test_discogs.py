import gzip

import pyarrow.parquet as pq
import pytest
from lxml import etree

from radar.ingest.discogs import iter_releases, parse_release, parse_released, write_parquet

# Shape follows the Discogs releases dump: release-level artists, a tracklist with its own
# track-level artists, labels as attributes, master_id with is_main_release.
SAMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<releases>
  <release id="1" status="Accepted">
    <artists>
      <artist><id>1</id><name>The Persuader</name><anv/><join/><role/><tracks/></artist>
    </artists>
    <title>Stockholm</title>
    <labels><label name="Svek" catno="SK032" id="5"/></labels>
    <extraartists>
      <artist><id>999</id><name>Mastering Engineer</name><role>Mastered By</role></artist>
    </extraartists>
    <genres><genre>Electronic</genre></genres>
    <styles><style>Deep House</style></styles>
    <country>Sweden</country>
    <released>1999-03-00</released>
    <master_id is_main_release="true">5427</master_id>
    <tracklist>
      <track>
        <position>A</position><title>Ostermalm</title>
        <artists><artist><id>777</id><name>Guest On Track</name></artist></artists>
      </track>
    </tracklist>
  </release>
  <release id="2" status="Accepted">
    <artists><artist><id>2</id><name>Some Band</name></artist></artists>
    <title>Not Electronic</title>
    <labels><label name="Rock Label" catno="R1" id="6"/></labels>
    <genres><genre>Rock</genre></genres>
    <styles><style>Indie Rock</style></styles>
    <country>UK</country>
    <released>2001</released>
  </release>
  <release id="3" status="Accepted">
    <artists>
      <artist><id>3</id><name>Producer A</name></artist>
      <artist><id>4</id><name>Producer B</name></artist>
    </artists>
    <title>Reissue</title>
    <labels>
      <label name="Label X" catno="LX1" id="7"/>
      <label name="Label Y" catno="LY1" id="8"/>
    </labels>
    <genres><genre>Electronic</genre><genre>Funk / Soul</genre></genres>
    <styles><style>Hard Groove</style><style>Techno</style></styles>
    <country>Germany</country>
    <released>2024-06-14</released>
    <master_id is_main_release="false">5427</master_id>
  </release>
  <release id="4" status="Accepted">
    <artists><artist><id>5</id><name>No Date Artist</name></artist></artists>
    <title>Undated</title>
    <labels><label name="White Label" catno="none"/></labels>
    <genres><genre>Electronic</genre></genres>
    <styles><style>Footwork</style></styles>
  </release>
</releases>
"""


@pytest.fixture
def dump(tmp_path):
    path = tmp_path / "discogs_test_releases.xml.gz"
    with gzip.open(path, "wb") as fh:
        fh.write(SAMPLE_XML)
    return path


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1999-03-14", (1999, 3, "day")),
        ("1999-03-00", (1999, 3, "month")),
        ("1999-00-00", (1999, None, "year")),
        ("1999", (1999, None, "year")),
        ("0000-00-00", (None, None, "none")),
        ("unknown", (None, None, "none")),
        (None, (None, None, "none")),
    ],
)
def test_parse_released(raw, expected):
    assert parse_released(raw) == expected


def test_keeps_only_electronic(dump):
    rows = list(iter_releases(dump, progress_every=0))
    assert [r["release_id"] for r in rows] == [1, 3, 4]


def test_release_level_artists_only(dump):
    first = next(iter_releases(dump, progress_every=0))
    # 777 is a track-level credit and 999 an extra artist; neither should be kept
    assert first["artist_ids"] == [1]


def test_fields_for_reissue(dump):
    rows = {r["release_id"]: r for r in iter_releases(dump, progress_every=0)}
    reissue = rows[3]
    assert reissue["master_id"] == 5427
    assert reissue["is_main_release"] is False
    assert reissue["styles"] == ["Hard Groove", "Techno"]
    assert reissue["label_ids"] == [7, 8]
    assert (reissue["year"], reissue["month"], reissue["date_precision"]) == (2024, 6, "day")


def test_missing_master_label_id_and_date(dump):
    rows = {r["release_id"]: r for r in iter_releases(dump, progress_every=0)}
    undated = rows[4]
    assert undated["master_id"] is None
    assert undated["label_ids"] == []
    assert undated["label_names"] == ["White Label"]
    assert undated["date_precision"] == "none"


def test_master_id_zero_means_no_master():
    # The real dump writes <master_id>0</master_id> instead of omitting the tag
    elem = etree.fromstring(
        b'<release id="9"><genres><genre>Electronic</genre></genres>'
        b'<master_id is_main_release="false">0</master_id></release>'
    )
    row = parse_release(elem)
    assert row["master_id"] is None
    assert row["is_main_release"] is False


def test_limit_counts_matching_releases(dump):
    rows = list(iter_releases(dump, limit=2, progress_every=0))
    assert [r["release_id"] for r in rows] == [1, 3]


def test_write_parquet_roundtrip(dump, tmp_path):
    out = tmp_path / "out.parquet"
    n = write_parquet(iter_releases(dump, progress_every=0), out, batch_size=2)
    table = pq.read_table(out)
    assert n == table.num_rows == 3
    assert table.column("styles").to_pylist()[1] == ["Hard Groove", "Techno"]
