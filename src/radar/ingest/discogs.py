"""Discogs monthly releases dump (CC0).

Responsibility: stream-parse the gzipped releases XML, keep genre == Electronic,
and write one row per (release_id, style) with release date, label, country and
artist IDs to data/interim/discogs_releases.parquet.
"""
