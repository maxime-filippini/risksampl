from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

import polars as pl
from pydantic import BaseModel, ConfigDict

CANONICAL_SCHEMA_VERSION = 1
CANONICAL_SCHEMA = pl.Schema(
    {
        "instrument_id": pl.String,
        "observation_date": pl.Date,
        "metric": pl.String,
        "value": pl.Float64,
    }
)
_ARTIFACT_PREFIX = f"canonical-market-data/v{CANONICAL_SCHEMA_VERSION}"


class CanonicalSnapshotError(Exception):
    """Base error for canonical snapshot publication and loading."""


class CanonicalSchemaError(CanonicalSnapshotError):
    """The canonical data does not conform to the declared schema."""


class ChecksumMismatchError(CanonicalSnapshotError):
    """The pinned snapshot object does not match its manifest checksum."""


class UnsupportedSchemaVersionError(CanonicalSnapshotError):
    """The manifest declares a schema version this service cannot read."""


class ImmutableArtifactError(CanonicalSnapshotError):
    """An immutable artifact key already contains different bytes."""


class ArtifactStore(Protocol):
    """Minimal immutable byte-store boundary used by snapshot artifacts."""

    def put_if_absent(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...


class DirectoryArtifactStore:
    """Directory-backed immutable artifact store for local operation and tests."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def put_if_absent(self, key: str, data: bytes) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as artifact:
                artifact.write(data)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ImmutableArtifactError(
                    f"artifact {key!r} already exists with different content"
                ) from None

    def get(self, key: str) -> bytes:
        return self._path_for(key).read_bytes()

    def _path_for(self, key: str) -> Path:
        relative_path = PurePosixPath(key)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"artifact key must be a relative object key: {key!r}")
        return self._root.joinpath(*relative_path.parts)


class InstrumentDateCoverage(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_id: str
    first_observation_date: dt.date
    latest_observation_date: dt.date


class CanonicalSnapshotManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    schema_version: int
    created_at: dt.datetime
    object_key: str
    sha256: str
    row_count: int
    date_coverage: tuple[InstrumentDateCoverage, ...]

    def to_bytes(self) -> bytes:
        document = self.model_dump(mode="json")
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()


@dataclass(frozen=True, slots=True)
class PublishedCanonicalSnapshot:
    manifest: CanonicalSnapshotManifest
    manifest_key: str


def publish_canonical_snapshot(
    observations: pl.DataFrame,
    store: ArtifactStore,
    *,
    created_at: dt.datetime | None = None,
) -> PublishedCanonicalSnapshot:
    """Publish one complete canonical frame as immutable Parquet and manifest."""
    canonical = _canonicalize(observations)
    parquet = io.BytesIO()
    canonical.write_parquet(parquet, compression="zstd")
    object_bytes = parquet.getvalue()
    object_checksum = hashlib.sha256(object_bytes).hexdigest()

    creation_time = created_at or dt.datetime.now(dt.UTC)
    if creation_time.tzinfo is None:
        raise ValueError("created_at must include a timezone")
    creation_time = creation_time.astimezone(dt.UTC)
    identity = (
        f"{CANONICAL_SCHEMA_VERSION}\0{creation_time.isoformat()}\0{object_checksum}"
    ).encode()
    snapshot_id = hashlib.sha256(identity).hexdigest()
    object_key = f"{_ARTIFACT_PREFIX}/objects/{object_checksum}.parquet"
    manifest_key = f"{_ARTIFACT_PREFIX}/manifests/{snapshot_id}.json"

    manifest = CanonicalSnapshotManifest(
        snapshot_id=snapshot_id,
        schema_version=CANONICAL_SCHEMA_VERSION,
        created_at=creation_time,
        object_key=object_key,
        sha256=object_checksum,
        row_count=canonical.height,
        date_coverage=_date_coverage(canonical),
    )
    store.put_if_absent(object_key, object_bytes)
    store.put_if_absent(manifest_key, manifest.to_bytes())
    return PublishedCanonicalSnapshot(manifest=manifest, manifest_key=manifest_key)


def load_canonical_snapshot(
    store: ArtifactStore,
    manifest_key: str,
) -> pl.DataFrame:
    """Verify and load the Parquet object pinned by an immutable manifest."""
    manifest = CanonicalSnapshotManifest.model_validate_json(store.get(manifest_key))
    if manifest.schema_version != CANONICAL_SCHEMA_VERSION:
        raise UnsupportedSchemaVersionError(
            f"unsupported canonical schema version {manifest.schema_version}; "
            f"supported version is {CANONICAL_SCHEMA_VERSION}"
        )

    object_bytes = store.get(manifest.object_key)
    actual_checksum = hashlib.sha256(object_bytes).hexdigest()
    if actual_checksum != manifest.sha256:
        raise ChecksumMismatchError(
            f"snapshot {manifest.snapshot_id!r} checksum mismatch: "
            f"expected {manifest.sha256}, got {actual_checksum}"
        )

    observations = pl.read_parquet(io.BytesIO(object_bytes))
    _validate_schema(observations)
    return observations


def _canonicalize(observations: pl.DataFrame) -> pl.DataFrame:
    _validate_schema(observations)
    return observations.sort(
        "instrument_id",
        "observation_date",
        "metric",
        "value",
    )


def _validate_schema(observations: pl.DataFrame) -> None:
    if observations.schema != CANONICAL_SCHEMA:
        raise CanonicalSchemaError(
            f"canonical schema v{CANONICAL_SCHEMA_VERSION} requires "
            f"{CANONICAL_SCHEMA}, got {observations.schema}"
        )
    instrument_ids = observations["instrument_id"]
    if instrument_ids.null_count() or instrument_ids.str.strip_chars().eq("").any():
        raise CanonicalSchemaError("instrument_id must contain non-empty stable IDs")


def _date_coverage(
    observations: pl.DataFrame,
) -> tuple[InstrumentDateCoverage, ...]:
    coverage = (
        observations.group_by("instrument_id")
        .agg(
            pl.col("observation_date").min().alias("first_observation_date"),
            pl.col("observation_date").max().alias("latest_observation_date"),
        )
        .sort("instrument_id")
    )
    return tuple(
        InstrumentDateCoverage.model_validate(row)
        for row in coverage.iter_rows(named=True)
    )
