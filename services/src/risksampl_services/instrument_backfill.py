"""Instrument onboarding through retained evidence and canonical snapshots.

Backfill fetches every provider page for one registered instrument, stores each
exact response as immutable evidence, normalizes and validates those responses,
publishes a complete canonical snapshot, and only then enables the instrument.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from collections.abc import Callable, Iterable, Mapping
from types import MappingProxyType
from typing import Protocol, Self, cast

import httpx
import polars as pl
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from risksampl_services.canonical_market_data import (
    CANONICAL_SCHEMA,
    ArtifactStore,
    PublishedCanonicalSnapshot,
    load_canonical_snapshot,
    publish_canonical_snapshot,
)

RAW_PROVIDER_RESPONSE_SCHEMA_VERSION = 1
_RAW_ARTIFACT_PREFIX = f"raw-provider-responses/v{RAW_PROVIDER_RESPONSE_SCHEMA_VERSION}"
EXCHANGE_CALENDAR_MAPPING_VERSION = 1
EXCHANGE_CALENDAR_IDS: Mapping[str, str] = MappingProxyType(
    {
        "ARCX": "XNYS",
        "BATS": "XNYS",
        "XNAS": "XNAS",
        "XNYS": "XNYS",
        "XPAR": "XPAR",
        "XLON": "XLON",
        "XETR": "XFRA",
    }
)


class InstrumentBackfillError(Exception):
    """Base error for instrument onboarding and catch-up."""


class InstrumentNotFoundError(InstrumentBackfillError):
    """The requested stable instrument ID is not registered."""


class InstrumentAlreadyEnabledError(InstrumentBackfillError):
    """An enabled instrument cannot be backfilled or caught up."""


class ExplicitCatchUpRequiredError(InstrumentBackfillError):
    """A previously disabled instrument must use the catch-up operation."""


class NoCatchUpRequiredError(InstrumentBackfillError):
    """The catch-up operation was requested for a new instrument."""


class ProviderResponseError(InstrumentBackfillError):
    """The provider response could not be fetched or paginated."""


class ProviderNormalizationError(InstrumentBackfillError):
    """The exact provider response could not be normalized."""


class BackfillValidationError(InstrumentBackfillError):
    """Normalized or candidate canonical observations failed validation."""


class UnknownExchangeCodeError(BackfillValidationError):
    """A provider exchange code has no pinned calendar mapping."""


class Instrument(BaseModel):
    """Registered market instrument and its ingestion lifecycle state.

    ``instrument_id`` is the stable internal identity used in canonical data;
    provider symbols are lookup attributes and are never used as that identity.
    Validated coverage is absent before onboarding and retained after disabling.
    ``catch_up_required`` prevents a disabled instrument from being silently
    re-enabled without explicitly filling the period in which it was inactive.
    """

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    provider_symbol: str
    exchange_code: str
    currency: str
    enabled: bool = False
    catch_up_required: bool = False
    first_validated_observation_date: dt.date | None = None
    latest_validated_observation_date: dt.date | None = None

    @field_validator("instrument_id")
    @classmethod
    def validate_instrument_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("instrument_id must be a non-empty stable ID")
        return value

    @field_validator("provider_symbol", "exchange_code")
    @classmethod
    def normalize_provider_identity(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("provider identity values must be non-empty")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("currency must be a three-letter code")
        return value

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        first = self.first_validated_observation_date
        latest = self.latest_validated_observation_date
        if (first is None) != (latest is None):
            raise ValueError("validated observation coverage must be complete")
        if first is not None and latest is not None and first > latest:
            raise ValueError("first validated date cannot follow latest validated date")
        if self.enabled and first is None:
            raise ValueError(
                "an instrument cannot be enabled without validated history"
            )
        if self.enabled and self.catch_up_required:
            raise ValueError("an enabled instrument cannot require catch-up")
        return self


class RawProviderResponse(BaseModel):
    """One provider HTTP response retained before interpretation.

    ``body`` contains the exact response payload passed to normalization.
    Retrieval metadata records when and how it was obtained while deliberately
    excluding credentials. A paginated history request therefore produces one
    instance—and later one immutable artifact—for every provider page.
    """

    model_config = ConfigDict(frozen=True)

    provider: str
    body: bytes
    retrieved_at: dt.datetime
    request_metadata: dict[str, str]
    response_metadata: dict[str, str]

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("provider must be non-empty")
        return value

    @field_validator("retrieved_at")
    @classmethod
    def validate_retrieved_at(cls, value: dt.datetime) -> dt.datetime:
        if value.tzinfo is None:
            raise ValueError("retrieved_at must include a timezone")
        return value.astimezone(dt.UTC)


class RawProviderResponseManifest(BaseModel):
    """Immutable metadata for one stored raw provider response.

    ``object_key`` locates the exact response bytes in the artifact store.
    ``sha256`` verifies those bytes, while ``provider_response_id`` identifies
    this particular retrieval, including its timestamp and request/response
    metadata. The manifest is stored separately under its own manifest key.
    """

    model_config = ConfigDict(frozen=True)

    provider_response_id: str
    schema_version: int
    provider: str
    retrieved_at: dt.datetime
    object_key: str
    sha256: str
    byte_count: int
    request_metadata: dict[str, str]
    response_metadata: dict[str, str]

    def to_bytes(self) -> bytes:
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()


class RetainedRawProviderResponse(BaseModel):
    """Published raw-response manifest together with its artifact-store key.

    The parsed ``manifest`` is convenient for the current workflow.
    ``manifest_key`` is the durable reference another process can persist and
    later use to retrieve the same evidence manifest.
    """

    model_config = ConfigDict(frozen=True)

    manifest: RawProviderResponseManifest
    manifest_key: str

    @property
    def object_key(self) -> str:
        return self.manifest.object_key

    @property
    def request_metadata(self) -> dict[str, str]:
        return self.manifest.request_metadata


class FullHistoryProvider(Protocol):
    """Port for fetching every available provider page for one instrument.

    Implementations yield pages individually so the workflow can retain each
    response before requesting or interpreting the next one.
    """

    def fetch_full_history(
        self,
        instrument: Instrument,
    ) -> Iterable[RawProviderResponse]: ...


class ProviderNormalizer(Protocol):
    """Port that translates retained provider payloads into canonical rows.

    Normalizers understand provider-specific JSON fields, but their output must
    use the provider-independent canonical schema and stable instrument ID.
    """

    def normalize(
        self,
        instrument: Instrument,
        responses: tuple[RawProviderResponse, ...],
    ) -> pl.DataFrame: ...


class BackfillState(Protocol):
    """Port for mutable instrument state and the canonical snapshot pointer.

    Artifact objects and manifests are immutable, but the application still
    needs mutable operational state saying which snapshot is current and which
    instruments are enabled. A durable adapter is expected to implement
    ``complete_backfill`` atomically so the instrument and snapshot pointer
    cannot disagree.
    """

    def get_instrument(self, instrument_id: str) -> Instrument: ...

    def current_snapshot_manifest_key(self) -> str | None: ...

    def complete_backfill(
        self,
        instrument: Instrument,
        snapshot_manifest_key: str,
    ) -> None: ...

    def disable_instrument(self, instrument_id: str) -> Instrument: ...


class InMemoryBackfillState:
    """Non-durable :class:`BackfillState` adapter for tests and local composition.

    It models instruments as a dictionary and the current snapshot as one
    manifest key. Production code can replace it with a PostgreSQL adapter
    without changing the backfill workflow.
    """

    def __init__(
        self,
        instruments: Iterable[Instrument] = (),
        *,
        current_snapshot_manifest_key: str | None = None,
    ) -> None:
        self._instruments = {
            instrument.instrument_id: instrument for instrument in instruments
        }
        self._current_snapshot_manifest_key = current_snapshot_manifest_key

    def get_instrument(self, instrument_id: str) -> Instrument:
        try:
            return self._instruments[instrument_id]
        except KeyError:
            raise InstrumentNotFoundError(
                f"instrument {instrument_id!r} is not registered"
            ) from None

    def current_snapshot_manifest_key(self) -> str | None:
        return self._current_snapshot_manifest_key

    def complete_backfill(
        self,
        instrument: Instrument,
        snapshot_manifest_key: str,
    ) -> None:
        current = self.get_instrument(instrument.instrument_id)
        if (
            instrument.instrument_id,
            instrument.provider_symbol,
            instrument.exchange_code,
            instrument.currency,
        ) != (
            current.instrument_id,
            current.provider_symbol,
            current.exchange_code,
            current.currency,
        ):
            raise ValueError("backfill cannot change stable instrument identity")
        self._instruments[instrument.instrument_id] = instrument
        self._current_snapshot_manifest_key = snapshot_manifest_key

    def disable_instrument(self, instrument_id: str) -> Instrument:
        current = self.get_instrument(instrument_id)
        if not current.enabled:
            return current
        disabled = current.model_copy(
            update={"enabled": False, "catch_up_required": True}
        )
        self._instruments[instrument_id] = disabled
        return disabled


class InstrumentBackfillPolicy(BaseModel):
    """Configured minimum history required to onboard or catch up an instrument.

    Required metrics and observation counts provide baseline instrument checks.
    Optional earliest/latest dates let an operator demand a particular coverage
    window. Policy failures prevent snapshot promotion and leave the instrument
    disabled.
    """

    model_config = ConfigDict(frozen=True)

    required_metrics: tuple[str, ...] = ("adjusted_close",)
    minimum_observations_per_metric: int = 1
    earliest_required_date: dt.date | None = None
    latest_required_date: dt.date | None = None

    @field_validator("required_metrics")
    @classmethod
    def validate_metrics(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(metric.strip() for metric in value)
        if not normalized or any(not metric for metric in normalized):
            raise ValueError("required_metrics must contain non-empty metric names")
        if len(normalized) != len(set(normalized)):
            raise ValueError("required_metrics must not contain duplicates")
        return normalized

    @field_validator("minimum_observations_per_metric")
    @classmethod
    def validate_minimum_observations(cls, value: int) -> int:
        if value < 1:
            raise ValueError("minimum_observations_per_metric must be positive")
        return value

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        if (
            self.earliest_required_date is not None
            and self.latest_required_date is not None
            and self.earliest_required_date > self.latest_required_date
        ):
            raise ValueError(
                "earliest_required_date cannot follow latest_required_date"
            )
        return self


InstrumentCheck = Callable[[Instrument, pl.DataFrame, InstrumentBackfillPolicy], None]
SnapshotCheck = Callable[[pl.DataFrame], None]


class InstrumentBackfillResult(BaseModel):
    """Successful backfill outputs and the immutable references it produced.

    It contains the newly enabled instrument state, the published canonical
    snapshot (including its manifest key), and every retained raw response
    (including each raw-response manifest key).
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    instrument: Instrument
    snapshot: PublishedCanonicalSnapshot
    raw_responses: tuple[RetainedRawProviderResponse, ...]


class InstrumentBackfillService:
    """Coordinates evidence retention, validation, publication, and enablement.

    The service owns ordering rather than storage details: raw responses are
    retained before normalization, the complete candidate snapshot is verified
    after publication, and mutable state changes only through
    ``complete_backfill`` at the end. Initial backfill and explicit catch-up
    share this pipeline but enforce different lifecycle preconditions.
    """

    def __init__(
        self,
        *,
        state: BackfillState,
        provider: FullHistoryProvider,
        normalizer: ProviderNormalizer,
        artifact_store: ArtifactStore,
        policy: InstrumentBackfillPolicy | None = None,
        instrument_checks: Iterable[InstrumentCheck] = (),
        snapshot_checks: Iterable[SnapshotCheck] = (),
        clock: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self._state = state
        self._provider = provider
        self._normalizer = normalizer
        self._artifact_store = artifact_store
        self._policy = policy or InstrumentBackfillPolicy()
        self._instrument_checks = (
            validate_instrument_observations,
            *tuple(instrument_checks),
        )
        self._snapshot_checks = (
            validate_candidate_snapshot,
            *tuple(snapshot_checks),
        )
        self._clock = clock or (lambda: dt.datetime.now(dt.UTC))

    def backfill_and_enable(self, instrument_id: str) -> InstrumentBackfillResult:
        instrument = self._state.get_instrument(instrument_id)
        if instrument.enabled:
            raise InstrumentAlreadyEnabledError(
                f"instrument {instrument_id!r} is already enabled"
            )
        if (
            instrument.catch_up_required
            or instrument.first_validated_observation_date is not None
        ):
            raise ExplicitCatchUpRequiredError(
                f"instrument {instrument_id!r} was previously enabled; "
                "run the explicit catch-up operation"
            )
        return self._fetch_validate_publish_and_enable(instrument)

    def catch_up_and_enable(self, instrument_id: str) -> InstrumentBackfillResult:
        instrument = self._state.get_instrument(instrument_id)
        if instrument.enabled:
            raise InstrumentAlreadyEnabledError(
                f"instrument {instrument_id!r} is already enabled"
            )
        if not instrument.catch_up_required:
            raise NoCatchUpRequiredError(
                f"instrument {instrument_id!r} has no disabled history; "
                "run the initial backfill operation"
            )
        return self._fetch_validate_publish_and_enable(instrument)

    def disable(self, instrument_id: str) -> Instrument:
        return self._state.disable_instrument(instrument_id)

    def _fetch_validate_publish_and_enable(
        self,
        instrument: Instrument,
    ) -> InstrumentBackfillResult:
        resolve_exchange_calendar(instrument.exchange_code)
        responses: list[RawProviderResponse] = []
        retained: list[RetainedRawProviderResponse] = []
        for response in self._provider.fetch_full_history(instrument):
            evidence = retain_raw_provider_response(response, self._artifact_store)
            responses.append(response)
            retained.append(evidence)
        if not responses:
            raise ProviderResponseError(
                f"provider returned no responses for {instrument.provider_symbol!r}"
            )

        normalized = self._normalizer.normalize(instrument, tuple(responses))
        for check in self._instrument_checks:
            check(instrument, normalized, self._policy)

        candidate = self._candidate_snapshot(instrument, normalized)
        for check in self._snapshot_checks:
            check(candidate)

        published = publish_canonical_snapshot(
            candidate,
            self._artifact_store,
            created_at=self._clock(),
        )
        # Re-read the immutable object and checksum before changing operational state.
        load_canonical_snapshot(self._artifact_store, published.manifest_key)
        coverage = next(
            (
                item
                for item in published.manifest.date_coverage
                if item.instrument_id == instrument.instrument_id
            ),
            None,
        )
        if coverage is None:
            raise BackfillValidationError(
                "published canonical data has no coverage for the instrument"
            )
        enabled = instrument.model_copy(
            update={
                "enabled": True,
                "catch_up_required": False,
                "first_validated_observation_date": coverage.first_observation_date,
                "latest_validated_observation_date": coverage.latest_observation_date,
            }
        )
        self._state.complete_backfill(enabled, published.manifest_key)
        return InstrumentBackfillResult(
            instrument=enabled,
            snapshot=published,
            raw_responses=tuple(retained),
        )

    def _candidate_snapshot(
        self,
        instrument: Instrument,
        normalized: pl.DataFrame,
    ) -> pl.DataFrame:
        current_manifest_key = self._state.current_snapshot_manifest_key()
        if current_manifest_key is None:
            existing = pl.DataFrame(schema=CANONICAL_SCHEMA)
        else:
            existing = load_canonical_snapshot(
                self._artifact_store,
                current_manifest_key,
            )
        without_target = existing.filter(
            pl.col("instrument_id") != instrument.instrument_id
        )
        return pl.concat([without_target, normalized], how="vertical")


def retain_raw_provider_response(
    response: RawProviderResponse,
    store: ArtifactStore,
) -> RetainedRawProviderResponse:
    """Retain exact response bytes and immutable, non-secret retrieval metadata."""
    checksum = hashlib.sha256(response.body).hexdigest()
    object_key = f"{_RAW_ARTIFACT_PREFIX}/objects/{checksum}.bin"
    identity_document: dict[str, object] = {
        "schema_version": RAW_PROVIDER_RESPONSE_SCHEMA_VERSION,
        "provider": response.provider,
        "retrieved_at": response.retrieved_at.isoformat(),
        "sha256": checksum,
        "request_metadata": response.request_metadata,
        "response_metadata": response.response_metadata,
    }
    provider_response_id = hashlib.sha256(
        json.dumps(
            identity_document,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    manifest_key = f"{_RAW_ARTIFACT_PREFIX}/manifests/{provider_response_id}.json"
    manifest = RawProviderResponseManifest(
        provider_response_id=provider_response_id,
        schema_version=RAW_PROVIDER_RESPONSE_SCHEMA_VERSION,
        provider=response.provider,
        retrieved_at=response.retrieved_at,
        object_key=object_key,
        sha256=checksum,
        byte_count=len(response.body),
        request_metadata=response.request_metadata,
        response_metadata=response.response_metadata,
    )
    store.put_if_absent(object_key, response.body)
    store.put_if_absent(manifest_key, manifest.to_bytes())
    return RetainedRawProviderResponse(manifest=manifest, manifest_key=manifest_key)


def resolve_exchange_calendar(exchange_code: str) -> str:
    """Resolve one known provider exchange code without heuristic guessing."""
    normalized = exchange_code.strip().upper()
    try:
        return EXCHANGE_CALENDAR_IDS[normalized]
    except KeyError:
        raise UnknownExchangeCodeError(
            f"exchange code {normalized!r} has no mapping in "
            f"exchange-calendar policy v{EXCHANGE_CALENDAR_MAPPING_VERSION}"
        ) from None


def validate_instrument_observations(
    instrument: Instrument,
    observations: pl.DataFrame,
    policy: InstrumentBackfillPolicy,
) -> None:
    if observations.schema != CANONICAL_SCHEMA:
        raise BackfillValidationError(
            f"normalized observations require {CANONICAL_SCHEMA}, "
            f"got {observations.schema}"
        )
    if observations.is_empty():
        raise BackfillValidationError("normalized observations must not be empty")
    if any(observations[column].null_count() for column in observations.columns):
        raise BackfillValidationError("normalized observations must not contain nulls")
    instrument_ids = observations["instrument_id"].unique().to_list()
    if instrument_ids != [instrument.instrument_id]:
        raise BackfillValidationError(
            "normalized observations must contain only the requested instrument ID"
        )
    if not all(math.isfinite(value) for value in observations["value"]):
        raise BackfillValidationError("normalized values must be finite")
    duplicate_count = (
        observations.group_by("instrument_id", "observation_date", "metric")
        .len()
        .filter(pl.col("len") > 1)
        .height
    )
    if duplicate_count:
        raise BackfillValidationError(
            "normalized observations must be unique by instrument, date, and metric"
        )

    for metric in policy.required_metrics:
        metric_observations = observations.filter(pl.col("metric") == metric)
        if metric_observations.height < policy.minimum_observations_per_metric:
            raise BackfillValidationError(
                f"metric {metric!r} requires at least "
                f"{policy.minimum_observations_per_metric} observations; "
                f"got {metric_observations.height}"
            )
        first_date = cast(dt.date, metric_observations["observation_date"].min())
        latest_date = cast(dt.date, metric_observations["observation_date"].max())
        if (
            policy.earliest_required_date is not None
            and first_date > policy.earliest_required_date
        ):
            raise BackfillValidationError(
                f"metric {metric!r} begins on {first_date}, after required "
                f"date {policy.earliest_required_date}"
            )
        if (
            policy.latest_required_date is not None
            and latest_date < policy.latest_required_date
        ):
            raise BackfillValidationError(
                f"metric {metric!r} ends on {latest_date}, before required "
                f"date {policy.latest_required_date}"
            )


def validate_candidate_snapshot(candidate: pl.DataFrame) -> None:
    if candidate.schema != CANONICAL_SCHEMA:
        raise BackfillValidationError(
            f"candidate snapshot requires {CANONICAL_SCHEMA}, got {candidate.schema}"
        )
    duplicate_count = (
        candidate.group_by("instrument_id", "observation_date", "metric")
        .len()
        .filter(pl.col("len") > 1)
        .height
    )
    if duplicate_count:
        raise BackfillValidationError(
            "candidate snapshot must be unique by instrument, date, and metric"
        )


class MarketstackEodNormalizer:
    """Translate Marketstack EOD response pages into canonical observations.

    Provider symbol, exchange code, and currency are checked against the
    registered instrument before provider fields are mapped to canonical metric
    names. The output uses the stable internal instrument ID.
    """

    def __init__(
        self,
        metric_fields: Mapping[str, str] | None = None,
    ) -> None:
        self._metric_fields = dict(metric_fields or {"adj_close": "adjusted_close"})
        if not self._metric_fields:
            raise ValueError("at least one Marketstack metric field is required")

    def normalize(
        self,
        instrument: Instrument,
        responses: tuple[RawProviderResponse, ...],
    ) -> pl.DataFrame:
        rows: list[dict[str, object]] = []
        for response in responses:
            try:
                decoded: object = json.loads(response.body)
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise ProviderNormalizationError(
                    "Marketstack response is not valid JSON"
                ) from error
            if not isinstance(decoded, dict):
                raise ProviderNormalizationError(
                    "Marketstack response must be a JSON object"
                )
            document = cast(dict[str, object], decoded)
            decoded_page = document.get("data")
            if not isinstance(decoded_page, list):
                raise ProviderNormalizationError(
                    "Marketstack response must contain a data array"
                )
            page = cast(list[object], decoded_page)
            for decoded_row in page:
                if not isinstance(decoded_row, dict):
                    raise ProviderNormalizationError(
                        "Marketstack data entries must be objects"
                    )
                provider_row = cast(dict[str, object], decoded_row)
                self._validate_provider_identity(instrument, provider_row)
                observation_date = self._parse_date(provider_row.get("date"))
                for provider_field, canonical_metric in self._metric_fields.items():
                    value = provider_row.get(provider_field)
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value)
                    ):
                        raise ProviderNormalizationError(
                            f"Marketstack field {provider_field!r} must be finite"
                        )
                    rows.append(
                        {
                            "instrument_id": instrument.instrument_id,
                            "observation_date": observation_date,
                            "metric": canonical_metric,
                            "value": float(value),
                        }
                    )
        return pl.DataFrame(rows, schema=CANONICAL_SCHEMA).sort(
            "instrument_id",
            "observation_date",
            "metric",
            "value",
        )

    @staticmethod
    def _validate_provider_identity(
        instrument: Instrument,
        row: dict[str, object],
    ) -> None:
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or symbol.upper() != instrument.provider_symbol:
            raise ProviderNormalizationError(
                "Marketstack provider symbol does not match the instrument"
            )
        exchange = row.get("exchange_code", row.get("exchange"))
        if (
            not isinstance(exchange, str)
            or exchange.upper() != instrument.exchange_code
        ):
            raise ProviderNormalizationError(
                "Marketstack exchange code does not match the instrument"
            )
        currency = row.get("price_currency")
        if currency is not None and (
            not isinstance(currency, str) or currency.upper() != instrument.currency
        ):
            raise ProviderNormalizationError(
                "Marketstack currency does not match the instrument"
            )

    @staticmethod
    def _parse_date(value: object) -> dt.date:
        if not isinstance(value, str):
            raise ProviderNormalizationError("Marketstack date must be a string")
        try:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError as error:
            raise ProviderNormalizationError(
                f"Marketstack date {value!r} is invalid"
            ) from error


class MarketstackFullHistoryProvider:
    """Marketstack implementation of the full-history provider port.

    It requests the v2 EOD endpoint for exactly one provider symbol, follows
    offset pagination until the reported total is exhausted, and yields each
    response before inspecting it further. Request metadata excludes the access
    key so retained evidence cannot leak the provider credential.
    """

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

    def fetch_full_history(
        self,
        instrument: Instrument,
    ) -> Iterable[RawProviderResponse]:
        offset = 0
        while True:
            response = self._client.get(
                self._endpoint,
                params={
                    "access_key": self._access_key,
                    "symbols": instrument.provider_symbol,
                    "limit": self._page_size,
                    "offset": offset,
                },
            )
            raw = RawProviderResponse(
                provider="marketstack",
                body=response.content,
                retrieved_at=self._clock(),
                request_metadata={
                    "endpoint": self._endpoint,
                    "provider_symbol": instrument.provider_symbol,
                    "exchange_code": instrument.exchange_code,
                    "limit": str(self._page_size),
                    "offset": str(offset),
                },
                response_metadata={
                    "status_code": str(response.status_code),
                    "content_type": response.headers.get("content-type", ""),
                },
            )
            # The caller persists each yielded response before requesting the next page.
            yield raw
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                raise ProviderResponseError(
                    f"Marketstack returned HTTP {response.status_code}"
                ) from error
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
            pagination = cast(dict[str, object], decoded_pagination)
            returned_offset = self._pagination_integer(pagination, "offset")
            count = self._pagination_integer(pagination, "count")
            total = self._pagination_integer(pagination, "total")
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

    @staticmethod
    def _pagination_integer(
        pagination: dict[str, object],
        field: str,
    ) -> int:
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
