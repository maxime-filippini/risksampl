import datetime as dt
import hashlib
import io
from pathlib import Path
from typing import Protocol, cast

import polars as pl
import pyarrow.parquet as pq  # pyright: ignore[reportMissingTypeStubs]
import pytest
from polars.testing import assert_frame_equal

from risksampl_services.canonical_market_data import (
    CANONICAL_SCHEMA,
    CANONICAL_SCHEMA_VERSION,
    CanonicalSchemaError,
    ChecksumMismatchError,
    DirectoryArtifactStore,
    ImmutableArtifactError,
    UnsupportedSchemaVersionError,
    load_canonical_snapshot,
    publish_canonical_snapshot,
)


class _ParquetColumnMetadata(Protocol):
    @property
    def compression(self) -> str: ...


class _ParquetRowGroupMetadata(Protocol):
    def column(self, index: int) -> _ParquetColumnMetadata: ...


class _ParquetFileMetadata(Protocol):
    @property
    def num_row_groups(self) -> int: ...

    @property
    def num_columns(self) -> int: ...

    def row_group(self, index: int) -> _ParquetRowGroupMetadata: ...


class _ParquetFile(Protocol):
    @property
    def metadata(self) -> _ParquetFileMetadata: ...


def _read_parquet_file(data: bytes) -> _ParquetFile:
    return cast(
        _ParquetFile,
        pq.ParquetFile(io.BytesIO(data)),  # pyright: ignore[reportUnknownMemberType]
    )


def _observations(
    instrument_ids: list[str | None],
    observation_dates: list[dt.date],
    values: list[float],
) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "instrument_id": instrument_ids,
            "observation_date": observation_dates,
            "metric": ["adjusted_close"] * len(instrument_ids),
            "value": values,
        },
        schema=CANONICAL_SCHEMA,
    )


def test_canonical_snapshot_round_trips_through_artifact_store(
    tmp_path: Path,
) -> None:
    observations = _observations(
        ["instrument-b", "instrument-a", "instrument-a"],
        [
            dt.date(2026, 7, 23),
            dt.date(2026, 7, 24),
            dt.date(2026, 7, 23),
        ],
        [202.25, 101.5, 100.0],
    )
    store = DirectoryArtifactStore(tmp_path)

    published = publish_canonical_snapshot(
        observations,
        store,
        created_at=dt.datetime(2026, 7, 24, 12, tzinfo=dt.UTC),
    )
    loaded = load_canonical_snapshot(store, published.manifest_key)

    expected = observations.sort("instrument_id", "observation_date", "metric")
    assert_frame_equal(loaded, expected)


@pytest.mark.parametrize("instrument_id", [None, ""])
def test_canonical_snapshot_requires_stable_instrument_identity(
    tmp_path: Path,
    instrument_id: str | None,
) -> None:
    observations = _observations(
        [instrument_id],
        [dt.date(2026, 7, 24)],
        [101.5],
    )

    with pytest.raises(
        CanonicalSchemaError,
        match="instrument_id must contain non-empty stable IDs",
    ):
        publish_canonical_snapshot(observations, DirectoryArtifactStore(tmp_path))


def test_manifest_records_snapshot_provenance_and_date_coverage(
    tmp_path: Path,
) -> None:
    observations = _observations(
        ["instrument-b", "instrument-a", "instrument-a"],
        [
            dt.date(2026, 7, 22),
            dt.date(2026, 7, 24),
            dt.date(2026, 7, 23),
        ],
        [202.25, 101.5, 100.0],
    )
    store = DirectoryArtifactStore(tmp_path)
    created_at = dt.datetime(2026, 7, 24, 12, tzinfo=dt.UTC)

    published = publish_canonical_snapshot(
        observations,
        store,
        created_at=created_at,
    )

    manifest = published.manifest
    object_bytes = store.get(manifest.object_key)
    assert manifest.model_dump(mode="json") == {
        "snapshot_id": manifest.snapshot_id,
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "created_at": "2026-07-24T12:00:00Z",
        "object_key": (
            "canonical-market-data/v1/objects/"
            f"{hashlib.sha256(object_bytes).hexdigest()}.parquet"
        ),
        "sha256": hashlib.sha256(object_bytes).hexdigest(),
        "row_count": 3,
        "date_coverage": [
            {
                "instrument_id": "instrument-a",
                "first_observation_date": "2026-07-23",
                "latest_observation_date": "2026-07-24",
            },
            {
                "instrument_id": "instrument-b",
                "first_observation_date": "2026-07-22",
                "latest_observation_date": "2026-07-22",
            },
        ],
    }


def test_snapshot_object_is_zstd_compressed_parquet(tmp_path: Path) -> None:
    observations = _observations(
        ["instrument-a"],
        [dt.date(2026, 7, 24)],
        [101.5],
    )
    store = DirectoryArtifactStore(tmp_path)

    published = publish_canonical_snapshot(
        observations,
        store,
        created_at=dt.datetime(2026, 7, 24, 12, tzinfo=dt.UTC),
    )

    parquet = _read_parquet_file(store.get(published.manifest.object_key))
    compressions = {
        parquet.metadata.row_group(row_group).column(column).compression
        for row_group in range(parquet.metadata.num_row_groups)
        for column in range(parquet.metadata.num_columns)
    }
    assert compressions == {"ZSTD"}


def test_snapshot_keys_are_deterministic_and_artifacts_are_immutable(
    tmp_path: Path,
) -> None:
    observations = _observations(
        ["instrument-b", "instrument-a"],
        [dt.date(2026, 7, 24), dt.date(2026, 7, 23)],
        [202.25, 101.5],
    )
    store = DirectoryArtifactStore(tmp_path)
    created_at = dt.datetime(2026, 7, 24, 12, tzinfo=dt.UTC)

    first = publish_canonical_snapshot(
        observations,
        store,
        created_at=created_at,
    )
    second = publish_canonical_snapshot(
        observations.reverse(),
        store,
        created_at=created_at,
    )

    assert second == first
    with pytest.raises(ImmutableArtifactError, match="different content"):
        store.put_if_absent(first.manifest.object_key, b"replacement")


def test_reader_rejects_a_snapshot_with_a_checksum_mismatch(
    tmp_path: Path,
) -> None:
    observations = _observations(
        ["instrument-a"],
        [dt.date(2026, 7, 24)],
        [101.5],
    )
    store = DirectoryArtifactStore(tmp_path)
    published = publish_canonical_snapshot(
        observations,
        store,
        created_at=dt.datetime(2026, 7, 24, 12, tzinfo=dt.UTC),
    )
    object_path = tmp_path.joinpath(*published.manifest.object_key.split("/"))
    object_path.write_bytes(b"corrupt")

    with pytest.raises(ChecksumMismatchError, match="checksum mismatch"):
        load_canonical_snapshot(store, published.manifest_key)


def test_reader_rejects_unsupported_schema_before_loading_object(
    tmp_path: Path,
) -> None:
    observations = _observations(
        ["instrument-a"],
        [dt.date(2026, 7, 24)],
        [101.5],
    )
    store = DirectoryArtifactStore(tmp_path)
    published = publish_canonical_snapshot(
        observations,
        store,
        created_at=dt.datetime(2026, 7, 24, 12, tzinfo=dt.UTC),
    )
    unsupported_manifest = published.manifest.model_copy(
        update={
            "schema_version": CANONICAL_SCHEMA_VERSION + 1,
            "object_key": "missing/object.parquet",
        }
    )
    unsupported_manifest_key = "canonical-market-data/unsupported.json"
    store.put_if_absent(unsupported_manifest_key, unsupported_manifest.to_bytes())

    with pytest.raises(
        UnsupportedSchemaVersionError,
        match="unsupported canonical schema version 2",
    ):
        load_canonical_snapshot(store, unsupported_manifest_key)
