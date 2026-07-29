"""Incremental ingestion for the enabled canonical market-data universe.

The workflow reads one authoritative snapshot, fetches only each instrument's
recent overlap window, retains every exact provider page, and validates
instrument updates independently. Invalid instruments keep their previous
validated rows while unaffected instruments may advance. A complete candidate
snapshot is promoted only after its immutable object and manifest reload
successfully.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from collections.abc import Callable, Iterable
from typing import Final, Literal, Protocol, cast

import httpx
import polars as pl
from pydantic import BaseModel, ConfigDict, field_validator

from risksampl_services.canonical_market_data import (
    CANONICAL_SCHEMA,
    ArtifactStore,
    InstrumentFinding,
    InstrumentSnapshotStatus,
    PublishedCanonicalSnapshot,
    load_canonical_snapshot,
    publish_canonical_snapshot,
)
from risksampl_services.instrument_backfill import (
    BackfillValidationError,
    Instrument,
    ProviderNormalizationError,
    ProviderNormalizer,
    ProviderResponseError,
    RawProviderResponse,
    RetainedRawProviderResponse,
    resolve_exchange_calendar,
    retain_raw_provider_response,
    validate_candidate_snapshot,
)

INSTRUMENT_CHECK_VERSION: Final = 1
_CANONICAL_KEY: Final = ("instrument_id", "observation_date", "metric")


class IncrementalIngestionError(Exception):
    """Base error for incremental market-data runs."""


class CurrentSnapshotRequiredError(IncrementalIngestionError):
    """Daily ingestion cannot run before the first canonical snapshot exists."""


class ConcurrentIngestionError(IncrementalIngestionError):
    """Another logical run currently owns the promotion lock."""


class AuthoritativeSnapshotChangedError(IncrementalIngestionError):
    """The current pointer changed before atomic promotion."""


class IncrementalHistoryProvider(Protocol):
    """Provider port that fetches one bounded recent date range."""

    def fetch_recent(
        self,
        instrument: Instrument,
        *,
        start_date: dt.date,
        end_date: dt.date,
    ) -> Iterable[RawProviderResponse]: ...


class IncrementalIngestionPolicy(BaseModel):
    """Versioned settings for overlap and instrument-level findings."""

    model_config = ConfigDict(frozen=True)

    overlap_days: int = 3
    stale_warning_after_days: int = 5
    required_metrics: tuple[str, ...] = ("adjusted_close",)

    @field_validator("overlap_days")
    @classmethod
    def validate_overlap_days(cls, value: int) -> int:
        if value < 0:
            raise ValueError("overlap_days must not be negative")
        return value

    @field_validator("stale_warning_after_days")
    @classmethod
    def validate_stale_days(cls, value: int) -> int:
        if value < 1:
            raise ValueError("stale_warning_after_days must be positive")
        return value

    @field_validator("required_metrics")
    @classmethod
    def validate_required_metrics(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(metric.strip() for metric in value)
        if not normalized or any(not metric for metric in normalized):
            raise ValueError("required_metrics must contain non-empty metric names")
        if len(normalized) != len(set(normalized)):
            raise ValueError("required_metrics must not contain duplicates")
        return normalized


InstrumentCheck = Callable[
    [Instrument, pl.DataFrame, IncrementalIngestionPolicy, dt.date],
    Iterable[InstrumentFinding],
]
SnapshotCheck = Callable[[pl.DataFrame], None]
RunStatus = Literal["promoted", "no_change"]


class IncrementalIngestionResult(BaseModel):
    """Terminal, idempotently replayable result of one logical daily run."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    logical_run_id: str
    status: RunStatus
    started_at: dt.datetime
    finished_at: dt.datetime
    base_snapshot_manifest_key: str
    snapshot: PublishedCanonicalSnapshot | None
    raw_responses: tuple[RetainedRawProviderResponse, ...]
    instrument_status: tuple[InstrumentSnapshotStatus, ...]

    @property
    def promoted_snapshot_manifest_key(self) -> str | None:
        if self.snapshot is None:
            return None
        return self.snapshot.manifest_key


class IncrementalIngestionState(Protocol):
    """Mutable state boundary implemented transactionally by PostgreSQL.

    A durable adapter must make ``complete_ingestion`` one transaction that
    verifies the base pointer, updates the authoritative canonical pointer,
    records the terminal run, and releases the overlap lock. Artifact objects
    are immutable and deliberately written before this transaction.
    """

    def enabled_instruments(self) -> tuple[Instrument, ...]: ...

    def current_snapshot_manifest_key(self) -> str | None: ...

    def begin_ingestion(
        self,
        logical_run_id: str,
        started_at: dt.datetime,
    ) -> IncrementalIngestionResult | None: ...

    def complete_ingestion(self, result: IncrementalIngestionResult) -> None: ...

    def fail_ingestion(
        self,
        logical_run_id: str,
        *,
        finished_at: dt.datetime,
        error: str,
    ) -> None: ...


class InMemoryIncrementalIngestionState:
    """In-memory model of idempotent runs, overlap locking, and atomic promotion."""

    def __init__(
        self,
        instruments: Iterable[Instrument],
        *,
        current_snapshot_manifest_key: str | None,
    ) -> None:
        self._instruments = {
            instrument.instrument_id: instrument for instrument in instruments
        }
        self._current_snapshot_manifest_key = current_snapshot_manifest_key
        self._results: dict[str, IncrementalIngestionResult] = {}
        self._run_status: dict[str, Literal["running", "failed"]] = {}
        self._lock_owner: str | None = None

    def enabled_instruments(self) -> tuple[Instrument, ...]:
        return tuple(
            sorted(
                (
                    instrument
                    for instrument in self._instruments.values()
                    if instrument.enabled
                ),
                key=lambda instrument: instrument.instrument_id,
            )
        )

    def current_snapshot_manifest_key(self) -> str | None:
        return self._current_snapshot_manifest_key

    def begin_ingestion(
        self,
        logical_run_id: str,
        started_at: dt.datetime,
    ) -> IncrementalIngestionResult | None:
        del started_at
        completed = self._results.get(logical_run_id)
        if completed is not None:
            return completed
        if self._lock_owner is not None:
            raise ConcurrentIngestionError(
                f"logical run {self._lock_owner!r} owns the ingestion lock"
            )
        self._lock_owner = logical_run_id
        self._run_status[logical_run_id] = "running"
        return None

    def complete_ingestion(self, result: IncrementalIngestionResult) -> None:
        if self._lock_owner != result.logical_run_id:
            raise ConcurrentIngestionError(
                f"logical run {result.logical_run_id!r} does not own the lock"
            )
        if self._current_snapshot_manifest_key != result.base_snapshot_manifest_key:
            raise AuthoritativeSnapshotChangedError(
                "authoritative canonical snapshot changed before promotion"
            )

        if result.snapshot is not None:
            self._current_snapshot_manifest_key = result.snapshot.manifest_key
            coverage = {
                item.instrument_id: item
                for item in result.snapshot.manifest.date_coverage
            }
            for instrument in self.enabled_instruments():
                item = coverage[instrument.instrument_id]
                self._instruments[instrument.instrument_id] = instrument.model_copy(
                    update={
                        "first_validated_observation_date": (
                            item.first_observation_date
                        ),
                        "latest_validated_observation_date": (
                            item.latest_observation_date
                        ),
                    }
                )
        self._results[result.logical_run_id] = result
        self._run_status.pop(result.logical_run_id, None)
        self._lock_owner = None

    def fail_ingestion(
        self,
        logical_run_id: str,
        *,
        finished_at: dt.datetime,
        error: str,
    ) -> None:
        del finished_at, error
        if self._lock_owner == logical_run_id:
            self._lock_owner = None
        self._run_status[logical_run_id] = "failed"

    def instrument(self, instrument_id: str) -> Instrument:
        return self._instruments[instrument_id]

    def run_state(
        self,
        logical_run_id: str,
    ) -> Literal["running", "failed", "promoted", "no_change"] | None:
        result = self._results.get(logical_run_id)
        if result is not None:
            return result.status
        return self._run_status.get(logical_run_id)


class IncrementalIngestionService:
    """Build, validate, and atomically promote one incremental snapshot."""

    def __init__(
        self,
        *,
        state: IncrementalIngestionState,
        provider: IncrementalHistoryProvider,
        normalizer: ProviderNormalizer,
        artifact_store: ArtifactStore,
        policy: IncrementalIngestionPolicy | None = None,
        instrument_checks: Iterable[InstrumentCheck] = (),
        snapshot_checks: Iterable[SnapshotCheck] = (),
        clock: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self._state = state
        self._provider = provider
        self._normalizer = normalizer
        self._artifact_store = artifact_store
        self._policy = policy or IncrementalIngestionPolicy()
        self._instrument_checks = (
            validate_incremental_observations,
            *tuple(instrument_checks),
        )
        self._snapshot_checks = (
            validate_candidate_snapshot,
            *tuple(snapshot_checks),
        )
        self._clock = clock or (lambda: dt.datetime.now(dt.UTC))

    def run(
        self,
        logical_run_id: str,
        *,
        as_of_date: dt.date | None = None,
    ) -> IncrementalIngestionResult:
        logical_run_id = logical_run_id.strip()
        if not logical_run_id:
            raise ValueError("logical_run_id must be non-empty")
        started_at = self._utc_now()
        previous_result = self._state.begin_ingestion(
            logical_run_id,
            started_at,
        )
        if previous_result is not None:
            return previous_result

        try:
            result = self._run_once(
                logical_run_id,
                started_at=started_at,
                as_of_date=as_of_date or started_at.date(),
            )
            self._state.complete_ingestion(result)
            return result
        except Exception as error:
            self._state.fail_ingestion(
                logical_run_id,
                finished_at=self._utc_now(),
                error=str(error),
            )
            raise

    def _run_once(
        self,
        logical_run_id: str,
        *,
        started_at: dt.datetime,
        as_of_date: dt.date,
    ) -> IncrementalIngestionResult:
        base_manifest_key = self._state.current_snapshot_manifest_key()
        if base_manifest_key is None:
            raise CurrentSnapshotRequiredError(
                "incremental ingestion requires an authoritative canonical snapshot"
            )
        current = load_canonical_snapshot(
            self._artifact_store,
            base_manifest_key,
        )
        candidate = current
        retained: list[RetainedRawProviderResponse] = []
        statuses: list[InstrumentSnapshotStatus] = []

        for instrument in self._state.enabled_instruments():
            current_instrument = current.filter(
                pl.col("instrument_id") == instrument.instrument_id
            )
            if current_instrument.is_empty():
                raise BackfillValidationError(
                    f"enabled instrument {instrument.instrument_id!r} "
                    "has no canonical history"
                )
            latest_before = cast(
                dt.date,
                current_instrument["observation_date"].max(),
            )
            try:
                calendar_id = resolve_exchange_calendar(instrument.exchange_code)
            except BackfillValidationError as error:
                finding = _error_finding(
                    instrument,
                    "instrument.unknown_exchange_code",
                    error,
                    {"exchange_code": instrument.exchange_code},
                )
                statuses.append(
                    _status(
                        instrument,
                        exchange_calendar_id="unmapped",
                        latest_observation_date=latest_before,
                        findings=(finding,),
                    )
                )
                continue

            start_date = latest_before - dt.timedelta(days=self._policy.overlap_days)
            responses: list[RawProviderResponse] = []
            findings: list[InstrumentFinding] = []
            try:
                for response in self._provider.fetch_recent(
                    instrument,
                    start_date=start_date,
                    end_date=as_of_date,
                ):
                    retained.append(
                        retain_raw_provider_response(
                            response,
                            self._artifact_store,
                        )
                    )
                    responses.append(response)
                if not responses:
                    raise ProviderResponseError(
                        "provider returned no retained response pages"
                    )
                normalized = self._normalizer.normalize(
                    instrument,
                    tuple(responses),
                )
                for check in self._instrument_checks:
                    findings.extend(
                        check(
                            instrument,
                            normalized,
                            self._policy,
                            as_of_date,
                        )
                    )
            except ProviderResponseError as error:
                findings.append(
                    _error_finding(
                        instrument,
                        "instrument.provider_request_failed",
                        error,
                        {
                            "start_date": start_date.isoformat(),
                            "end_date": as_of_date.isoformat(),
                        },
                    )
                )
                normalized = pl.DataFrame(schema=CANONICAL_SCHEMA)
            except ProviderNormalizationError as error:
                findings.append(
                    _error_finding(
                        instrument,
                        "instrument.provider_response_invalid",
                        error,
                        {"retained_response_count": len(responses)},
                    )
                )
                normalized = pl.DataFrame(schema=CANONICAL_SCHEMA)

            if any(finding.severity == "error" for finding in findings):
                statuses.append(
                    _status(
                        instrument,
                        exchange_calendar_id=calendar_id,
                        latest_observation_date=latest_before,
                        findings=tuple(findings),
                    )
                )
                continue

            merged_instrument = _merge_instrument_history(
                current_instrument,
                normalized,
            )
            latest_after = cast(
                dt.date,
                merged_instrument["observation_date"].max(),
            )
            age_days = (as_of_date - latest_after).days
            if age_days > self._policy.stale_warning_after_days:
                findings.append(
                    InstrumentFinding(
                        instrument_id=instrument.instrument_id,
                        severity="warning",
                        reason_code="instrument.latest_observation_stale",
                        check_version=INSTRUMENT_CHECK_VERSION,
                        message="latest validated observation is stale",
                        measured_values={
                            "latest_observation_date": latest_after.isoformat(),
                            "as_of_date": as_of_date.isoformat(),
                            "age_days": age_days,
                            "warning_after_days": (
                                self._policy.stale_warning_after_days
                            ),
                        },
                    )
                )
            candidate = pl.concat(
                [
                    candidate.filter(
                        pl.col("instrument_id") != instrument.instrument_id
                    ),
                    merged_instrument,
                ],
                how="vertical",
            )
            statuses.append(
                _status(
                    instrument,
                    exchange_calendar_id=calendar_id,
                    latest_observation_date=latest_after,
                    findings=tuple(findings),
                )
            )

        for check in self._snapshot_checks:
            check(candidate)
        finished_at = self._utc_now()
        sorted_candidate = _sort_canonical(candidate)
        sorted_current = _sort_canonical(current)
        if sorted_candidate.equals(sorted_current):
            return IncrementalIngestionResult(
                logical_run_id=logical_run_id,
                status="no_change",
                started_at=started_at,
                finished_at=finished_at,
                base_snapshot_manifest_key=base_manifest_key,
                snapshot=None,
                raw_responses=tuple(retained),
                instrument_status=tuple(statuses),
            )

        published = publish_canonical_snapshot(
            sorted_candidate,
            self._artifact_store,
            created_at=finished_at,
            instrument_status=statuses,
        )
        verified = load_canonical_snapshot(
            self._artifact_store,
            published.manifest_key,
        )
        if not verified.equals(sorted_candidate):
            raise BackfillValidationError(
                "reloaded canonical snapshot differs from its candidate"
            )
        return IncrementalIngestionResult(
            logical_run_id=logical_run_id,
            status="promoted",
            started_at=started_at,
            finished_at=finished_at,
            base_snapshot_manifest_key=base_manifest_key,
            snapshot=published,
            raw_responses=tuple(retained),
            instrument_status=tuple(statuses),
        )

    def _utc_now(self) -> dt.datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value.astimezone(dt.UTC)


def validate_incremental_observations(
    instrument: Instrument,
    observations: pl.DataFrame,
    policy: IncrementalIngestionPolicy,
    as_of_date: dt.date,
) -> tuple[InstrumentFinding, ...]:
    """Return structured errors/warnings without mutating canonical history."""
    del as_of_date
    findings: list[InstrumentFinding] = []
    if observations.schema != CANONICAL_SCHEMA:
        return (
            _error_finding(
                instrument,
                "instrument.schema_mismatch",
                "normalized observations do not use the canonical schema",
                {"actual_schema": str(observations.schema)},
            ),
        )
    if observations.is_empty():
        return (
            InstrumentFinding(
                instrument_id=instrument.instrument_id,
                severity="warning",
                reason_code="instrument.no_new_observations",
                check_version=INSTRUMENT_CHECK_VERSION,
                message="provider response contained no observations",
                measured_values={"observation_count": 0},
            ),
        )
    null_count = sum(
        observations[column].null_count() for column in observations.columns
    )
    if null_count:
        findings.append(
            _error_finding(
                instrument,
                "instrument.null_observation",
                "normalized observations contain nulls",
                {"null_count": null_count},
            )
        )
    instrument_ids = observations["instrument_id"].unique().to_list()
    if instrument_ids != [instrument.instrument_id]:
        findings.append(
            _error_finding(
                instrument,
                "instrument.identity_mismatch",
                "normalized observations contain another instrument ID",
                {"instrument_ids": ",".join(sorted(map(str, instrument_ids)))},
            )
        )
    finite_values = [
        value
        for value in observations["value"].to_list()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    non_finite_count = sum(not math.isfinite(float(value)) for value in finite_values)
    if non_finite_count:
        findings.append(
            _error_finding(
                instrument,
                "instrument.non_finite_value",
                "normalized observations contain non-finite values",
                {"non_finite_count": non_finite_count},
            )
        )
    duplicate_count = (
        observations.group_by(*_CANONICAL_KEY).len().filter(pl.col("len") > 1).height
    )
    if duplicate_count:
        findings.append(
            _error_finding(
                instrument,
                "instrument.duplicate_observation",
                "normalized observations contain duplicate canonical keys",
                {"duplicate_key_count": duplicate_count},
            )
        )
    observed_metrics = set(observations["metric"].unique().to_list())
    for metric in policy.required_metrics:
        if metric not in observed_metrics:
            findings.append(
                _error_finding(
                    instrument,
                    "instrument.required_metric_missing",
                    f"required metric {metric!r} is absent",
                    {"metric": metric},
                )
            )
    return tuple(findings)


def _merge_instrument_history(
    current: pl.DataFrame,
    incoming: pl.DataFrame,
) -> pl.DataFrame:
    if incoming.is_empty():
        return current
    incoming_keys = incoming.select(*_CANONICAL_KEY)
    preserved = current.join(
        incoming_keys,
        on=list(_CANONICAL_KEY),
        how="anti",
    )
    return _sort_canonical(pl.concat([preserved, incoming], how="vertical"))


def _sort_canonical(observations: pl.DataFrame) -> pl.DataFrame:
    return observations.sort(
        "instrument_id",
        "observation_date",
        "metric",
        "value",
    )


def _status(
    instrument: Instrument,
    *,
    exchange_calendar_id: str,
    latest_observation_date: dt.date,
    findings: tuple[InstrumentFinding, ...],
) -> InstrumentSnapshotStatus:
    return InstrumentSnapshotStatus(
        instrument_id=instrument.instrument_id,
        exchange_calendar_id=exchange_calendar_id,
        eligible=not any(finding.severity == "error" for finding in findings),
        latest_observation_date=latest_observation_date,
        findings=findings,
    )


def _error_finding(
    instrument: Instrument,
    reason_code: str,
    error: Exception | str,
    measured_values: dict[str, str | int | float | bool | None],
) -> InstrumentFinding:
    return InstrumentFinding(
        instrument_id=instrument.instrument_id,
        severity="error",
        reason_code=reason_code,
        check_version=INSTRUMENT_CHECK_VERSION,
        message=str(error),
        measured_values=measured_values,
    )


class MarketstackIncrementalProvider:
    """Fetch paginated Marketstack EOD rows for one explicit date window."""

    def __init__(
        self,
        *,
        access_key: str,
        client: httpx.Client,
        page_size: int = 1000,
        endpoint: str = "https://api.marketstack.com/v2/eod",
        clock: Callable[[], dt.datetime] | None = None,
    ) -> None:
        if not access_key:
            raise ValueError("Marketstack access_key must be non-empty")
        if page_size < 1 or page_size > 1000:
            raise ValueError("Marketstack page_size must be between 1 and 1000")
        self._access_key = access_key
        self._client = client
        self._page_size = page_size
        self._endpoint = endpoint
        self._clock = clock or (lambda: dt.datetime.now(dt.UTC))

    def fetch_recent(
        self,
        instrument: Instrument,
        *,
        start_date: dt.date,
        end_date: dt.date,
    ) -> Iterable[RawProviderResponse]:
        if start_date > end_date:
            raise ValueError("incremental start_date cannot follow end_date")
        offset = 0
        while True:
            try:
                response = self._client.get(
                    self._endpoint,
                    params={
                        "access_key": self._access_key,
                        "symbols": instrument.provider_symbol,
                        "date_from": start_date.isoformat(),
                        "date_to": end_date.isoformat(),
                        "limit": self._page_size,
                        "offset": offset,
                    },
                )
            except httpx.HTTPError as error:
                raise ProviderResponseError(
                    f"Marketstack request failed for {instrument.provider_symbol!r}"
                ) from error
            raw = RawProviderResponse(
                provider="marketstack",
                body=response.content,
                retrieved_at=self._now(),
                request_metadata={
                    "endpoint": self._endpoint,
                    "provider_symbol": instrument.provider_symbol,
                    "exchange_code": instrument.exchange_code,
                    "date_from": start_date.isoformat(),
                    "date_to": end_date.isoformat(),
                    "limit": str(self._page_size),
                    "offset": str(offset),
                },
                response_metadata={
                    "status_code": str(response.status_code),
                    "content_type": response.headers.get("content-type", ""),
                },
            )
            yield raw
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                raise ProviderResponseError(
                    f"Marketstack returned HTTP {response.status_code}"
                ) from error
            pagination = _marketstack_pagination(response)
            returned_offset = _pagination_integer(pagination, "offset")
            count = _pagination_integer(pagination, "count")
            total = _pagination_integer(pagination, "total")
            if returned_offset != offset or count < 0 or total < 0:
                raise ProviderResponseError(
                    "Marketstack response has inconsistent pagination metadata"
                )
            if offset + count >= total:
                return
            if count == 0:
                raise ProviderResponseError(
                    "Marketstack pagination did not advance before reaching total"
                )
            offset += count

    def _now(self) -> dt.datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value.astimezone(dt.UTC)


def _marketstack_pagination(response: httpx.Response) -> dict[str, object]:
    try:
        decoded: object = response.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ProviderResponseError(
            "Marketstack response has invalid pagination metadata"
        ) from error
    if not isinstance(decoded, dict):
        raise ProviderResponseError(
            "Marketstack response has invalid pagination metadata"
        )
    document = cast(dict[str, object], decoded)
    decoded_pagination = document.get("pagination")
    if not isinstance(decoded_pagination, dict):
        raise ProviderResponseError(
            "Marketstack response has invalid pagination metadata"
        )
    return cast(dict[str, object], decoded_pagination)


def _pagination_integer(pagination: dict[str, object], field: str) -> int:
    value = pagination.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ProviderResponseError(
            "Marketstack response has invalid pagination metadata"
        )
    try:
        return int(value)
    except ValueError as error:
        raise ProviderResponseError(
            "Marketstack response has invalid pagination metadata"
        ) from error
