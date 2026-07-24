"""Immutable canonical market-data snapshots and their artifact metadata.

A snapshot is the complete canonical DataFrame for one publication point. Its
Parquet bytes are stored as an immutable object. A separate JSON manifest
describes and checksums that object. Callers retain the manifest key—not a
mutable filename—as the durable reference needed to load the exact snapshot.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, Protocol

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


class ManifestConsistencyError(CanonicalSnapshotError):
    """The manifest disagrees with its identity or canonical object."""


class ImmutableArtifactError(CanonicalSnapshotError):
    """An immutable artifact key already contains different bytes."""


class ArtifactStore(Protocol):
    """Storage boundary for immutable, key-addressed artifact bytes.

    An artifact key is a relative, opaque identifier within a store, such as a
    Parquet object key or JSON manifest key. ``put_if_absent`` gives publication
    its immutability guarantee: an existing key may contain the same bytes, but
    it must never be overwritten with different bytes.
    """

    def put_if_absent(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...


class DirectoryArtifactStore:
    """Filesystem implementation of :class:`ArtifactStore`.

    Object keys are mapped beneath one root directory. This adapter gives local
    runs and tests the same key-based semantics expected from remote object
    storage, without making snapshot code depend on a particular cloud vendor.
    """

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
    """Inclusive canonical date range available for one stable instrument ID.

    Coverage is derived from the validated canonical DataFrame rather than
    copied from provider metadata, so it describes the data readers will
    actually receive from the snapshot.
    """

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    first_observation_date: dt.date
    latest_observation_date: dt.date


class InstrumentFinding(BaseModel):
    """One versioned, machine-readable instrument validation result."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    severity: Literal["error", "warning"]
    reason_code: str
    check_version: int
    message: str
    measured_values: dict[str, str | int | float | bool | None]


class InstrumentSnapshotStatus(BaseModel):
    """Eligibility, freshness, and findings captured at snapshot creation."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    exchange_calendar_id: str
    eligible: bool
    latest_observation_date: dt.date
    findings: tuple[InstrumentFinding, ...] = ()


class CanonicalSnapshotManifest(BaseModel):
    """Immutable metadata needed to identify and verify one canonical snapshot.

    The manifest points to the Parquet object through ``object_key`` and records
    its checksum, schema version, row count, creation time, and per-instrument
    coverage. The manifest itself is stored as a separate artifact; its storage
    key is the durable snapshot reference passed to
    :func:`load_canonical_snapshot`.
    """

    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    schema_version: int
    created_at: dt.datetime
    object_key: str
    sha256: str
    row_count: int
    date_coverage: tuple[InstrumentDateCoverage, ...]
    instrument_status: tuple[InstrumentSnapshotStatus, ...] = ()

    def to_bytes(self) -> bytes:
        document = self.model_dump(mode="json")
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()


@dataclass(frozen=True, slots=True)
class PublishedCanonicalSnapshot:
    """Result of publishing a canonical snapshot and its manifest.

    ``manifest`` exposes the parsed metadata for immediate use.
    ``manifest_key`` identifies the immutable JSON manifest in the artifact
    store and is what operational state should persist as the snapshot pointer.
    """

    manifest: CanonicalSnapshotManifest
    manifest_key: str


def publish_canonical_snapshot(
    observations: pl.DataFrame,
    store: ArtifactStore,
    *,
    created_at: dt.datetime | None = None,
    instrument_status: Iterable[InstrumentSnapshotStatus] = (),
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
    snapshot_id = _snapshot_id(creation_time, object_checksum)
    object_key = f"{_ARTIFACT_PREFIX}/objects/{object_checksum}.parquet"
    manifest_key = f"{_ARTIFACT_PREFIX}/manifests/{snapshot_id}.json"
    sorted_instrument_status = tuple(
        sorted(tuple(instrument_status), key=_instrument_status_id)
    )

    manifest = CanonicalSnapshotManifest(
        snapshot_id=snapshot_id,
        schema_version=CANONICAL_SCHEMA_VERSION,
        created_at=creation_time,
        object_key=object_key,
        sha256=object_checksum,
        row_count=canonical.height,
        date_coverage=_date_coverage(canonical),
        instrument_status=sorted_instrument_status,
    )
    _validate_manifest_consistency(manifest, canonical, manifest_key)
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
    expected_object_key = f"{_ARTIFACT_PREFIX}/objects/{manifest.sha256}.parquet"
    if manifest.object_key != expected_object_key:
        raise ManifestConsistencyError(
            "canonical manifest object key does not match its checksum"
        )
    expected_snapshot_id = _snapshot_id(
        manifest.created_at,
        manifest.sha256,
    )
    if manifest.snapshot_id != expected_snapshot_id:
        raise ManifestConsistencyError(
            "canonical manifest snapshot ID does not match its contents"
        )
    expected_manifest_key = f"{_ARTIFACT_PREFIX}/manifests/{manifest.snapshot_id}.json"
    if manifest_key != expected_manifest_key:
        raise ManifestConsistencyError(
            "canonical manifest key does not match its snapshot ID"
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
    _validate_manifest_consistency(manifest, observations, manifest_key)
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
    if any(observations[column].null_count() for column in observations.columns):
        raise CanonicalSchemaError("canonical observations must not contain nulls")
    duplicate_count = (
        observations.group_by("instrument_id", "observation_date", "metric")
        .len()
        .filter(pl.col("len") > 1)
        .height
    )
    if duplicate_count:
        raise CanonicalSchemaError(
            "canonical observations must be unique by instrument, date, and metric"
        )


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


def _snapshot_id(created_at: dt.datetime, object_checksum: str) -> str:
    identity = (
        f"{CANONICAL_SCHEMA_VERSION}\0{created_at.isoformat()}\0{object_checksum}"
    ).encode()
    return hashlib.sha256(identity).hexdigest()


def _instrument_status_id(status: InstrumentSnapshotStatus) -> str:
    return status.instrument_id


def _validate_manifest_consistency(
    manifest: CanonicalSnapshotManifest,
    observations: pl.DataFrame,
    manifest_key: str,
) -> None:
    if manifest.row_count != observations.height:
        raise ManifestConsistencyError(
            "canonical manifest row count does not match its object"
        )
    if manifest.date_coverage != _date_coverage(observations):
        raise ManifestConsistencyError(
            "canonical manifest date coverage does not match its object"
        )
    coverage_by_instrument = {
        item.instrument_id: item for item in manifest.date_coverage
    }
    status_ids = [status.instrument_id for status in manifest.instrument_status]
    if len(status_ids) != len(set(status_ids)):
        raise ManifestConsistencyError(
            "canonical manifest instrument status contains duplicate instruments"
        )
    for status in manifest.instrument_status:
        coverage = coverage_by_instrument.get(status.instrument_id)
        if coverage is None:
            raise ManifestConsistencyError(
                "canonical manifest instrument status has no object coverage"
            )
        if status.latest_observation_date != coverage.latest_observation_date:
            raise ManifestConsistencyError(
                "canonical manifest instrument freshness disagrees with object coverage"
            )
        if any(
            finding.instrument_id != status.instrument_id for finding in status.findings
        ):
            raise ManifestConsistencyError(
                "canonical manifest finding belongs to a different instrument"
            )
        has_error = any(finding.severity == "error" for finding in status.findings)
        if status.eligible == has_error:
            raise ManifestConsistencyError(
                "canonical manifest eligibility disagrees with instrument findings"
            )

    expected_manifest_key = f"{_ARTIFACT_PREFIX}/manifests/{manifest.snapshot_id}.json"
    if manifest_key != expected_manifest_key:
        raise ManifestConsistencyError(
            "canonical manifest key does not match its snapshot ID"
        )
