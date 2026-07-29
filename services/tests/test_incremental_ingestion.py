import datetime as dt
import json
from collections.abc import Iterable
from pathlib import Path

import httpx
import polars as pl
import pytest
from polars.testing import assert_frame_equal

from risksampl_services.canonical_market_data import (
    CANONICAL_SCHEMA,
    ArtifactStore,
    DirectoryArtifactStore,
    InstrumentFinding,
    load_canonical_snapshot,
    publish_canonical_snapshot,
)
from risksampl_services.incremental_ingestion import (
    ConcurrentIngestionError,
    IncrementalIngestionPolicy,
    IncrementalIngestionService,
    InMemoryIncrementalIngestionState,
    MarketstackIncrementalProvider,
)
from risksampl_services.instrument_backfill import (
    Instrument,
    RawProviderResponse,
)


def _observations(
    instrument_id: str,
    dates: list[dt.date],
    values: list[float],
) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "instrument_id": [instrument_id] * len(dates),
            "observation_date": dates,
            "metric": ["adjusted_close"] * len(dates),
            "value": values,
        },
        schema=CANONICAL_SCHEMA,
    )


def _instrument(
    instrument_id: str,
    *,
    symbol: str,
    exchange_code: str,
    first: dt.date,
    latest: dt.date,
) -> Instrument:
    return Instrument(
        instrument_id=instrument_id,
        provider_symbol=symbol,
        exchange_code=exchange_code,
        currency="USD",
        enabled=True,
        first_validated_observation_date=first,
        latest_validated_observation_date=latest,
    )


def _raw(instrument_id: str, body: bytes) -> RawProviderResponse:
    return RawProviderResponse(
        provider="marketstack",
        body=body,
        retrieved_at=dt.datetime(2026, 7, 24, 12, tzinfo=dt.UTC),
        request_metadata={
            "instrument_id": instrument_id,
            "date_from": "bounded-by-service",
        },
        response_metadata={"status_code": "200"},
    )


class RecordingIncrementalProvider:
    def __init__(
        self,
        responses: dict[str, Iterable[RawProviderResponse]],
    ) -> None:
        self._responses = {
            instrument_id: tuple(items) for instrument_id, items in responses.items()
        }
        self.requests: list[tuple[str, dt.date, dt.date]] = []

    def fetch_recent(
        self,
        instrument: Instrument,
        *,
        start_date: dt.date,
        end_date: dt.date,
    ) -> Iterable[RawProviderResponse]:
        self.requests.append((instrument.instrument_id, start_date, end_date))
        yield from self._responses[instrument.instrument_id]


class StaticNormalizer:
    def __init__(self, observations: dict[str, pl.DataFrame]) -> None:
        self._observations = observations

    def normalize(
        self,
        instrument: Instrument,
        responses: tuple[RawProviderResponse, ...],
    ) -> pl.DataFrame:
        assert responses
        return self._observations[instrument.instrument_id]


def _current_snapshot(
    tmp_path: Path,
) -> tuple[
    DirectoryArtifactStore,
    str,
    Instrument,
    Instrument,
    pl.DataFrame,
]:
    store = DirectoryArtifactStore(tmp_path)
    instrument_a = _instrument(
        "instrument-a",
        symbol="AAA",
        exchange_code="ARCX",
        first=dt.date(2026, 7, 20),
        latest=dt.date(2026, 7, 23),
    )
    instrument_b = _instrument(
        "instrument-b",
        symbol="BBB",
        exchange_code="XNAS",
        first=dt.date(2026, 7, 22),
        latest=dt.date(2026, 7, 22),
    )
    current = pl.concat(
        [
            _observations(
                instrument_a.instrument_id,
                [dt.date(2026, 7, 20), dt.date(2026, 7, 23)],
                [100.0, 103.0],
            ),
            _observations(
                instrument_b.instrument_id,
                [dt.date(2026, 7, 22)],
                [200.0],
            ),
        ],
        how="vertical",
    )
    published = publish_canonical_snapshot(
        current,
        store,
        created_at=dt.datetime(2026, 7, 23, 18, tzinfo=dt.UTC),
    )
    return store, published.manifest_key, instrument_a, instrument_b, current


def test_incremental_run_fetches_only_overlap_and_promotes_complete_snapshot(
    tmp_path: Path,
) -> None:
    store, current_key, instrument_a, instrument_b, current = _current_snapshot(
        tmp_path
    )
    incoming_a = _observations(
        instrument_a.instrument_id,
        [
            dt.date(2026, 7, 21),
            dt.date(2026, 7, 23),
            dt.date(2026, 7, 24),
        ],
        [101.0, 103.5, 104.0],
    )
    incoming_b = _observations(
        instrument_b.instrument_id,
        [dt.date(2026, 7, 23)],
        [201.0],
    )
    raw_a = _raw(instrument_a.instrument_id, b'{"instrument":"a"}')
    raw_b = _raw(instrument_b.instrument_id, b'{"instrument":"b"}')
    provider = RecordingIncrementalProvider(
        {
            instrument_a.instrument_id: [raw_a],
            instrument_b.instrument_id: [raw_b],
        }
    )
    state = InMemoryIncrementalIngestionState(
        [instrument_a, instrument_b],
        current_snapshot_manifest_key=current_key,
    )

    result = IncrementalIngestionService(
        state=state,
        provider=provider,
        normalizer=StaticNormalizer(
            {
                instrument_a.instrument_id: incoming_a,
                instrument_b.instrument_id: incoming_b,
            }
        ),
        artifact_store=store,
        policy=IncrementalIngestionPolicy(overlap_days=3),
        clock=lambda: dt.datetime(2026, 7, 24, 18, tzinfo=dt.UTC),
    ).run("daily-2026-07-24")

    assert result.status == "promoted"
    assert provider.requests == [
        (
            instrument_a.instrument_id,
            dt.date(2026, 7, 20),
            dt.date(2026, 7, 24),
        ),
        (
            instrument_b.instrument_id,
            dt.date(2026, 7, 19),
            dt.date(2026, 7, 24),
        ),
    ]
    assert [store.get(item.object_key) for item in result.raw_responses] == [
        raw_a.body,
        raw_b.body,
    ]
    assert result.snapshot is not None
    assert state.current_snapshot_manifest_key() == result.snapshot.manifest_key
    expected = pl.concat(
        [
            current.filter(
                (pl.col("instrument_id") == instrument_a.instrument_id)
                & (pl.col("observation_date") == dt.date(2026, 7, 20))
            ),
            incoming_a,
            current.filter(pl.col("instrument_id") == instrument_b.instrument_id),
            incoming_b,
        ],
        how="vertical",
    ).sort("instrument_id", "observation_date", "metric", "value")
    assert_frame_equal(
        load_canonical_snapshot(store, result.snapshot.manifest_key),
        expected,
    )
    status_by_id = {
        status.instrument_id: status
        for status in result.snapshot.manifest.instrument_status
    }
    assert status_by_id[instrument_a.instrument_id].exchange_calendar_id == "XNYS"
    assert status_by_id[instrument_a.instrument_id].eligible is True
    assert status_by_id[instrument_a.instrument_id].latest_observation_date == dt.date(
        2026, 7, 24
    )
    assert state.instrument(
        instrument_b.instrument_id
    ).latest_validated_observation_date == dt.date(2026, 7, 23)


def test_instrument_error_preserves_validated_values_while_other_instrument_advances(
    tmp_path: Path,
) -> None:
    store, current_key, instrument_a, instrument_b, current = _current_snapshot(
        tmp_path
    )
    invalid_a = _observations(
        instrument_a.instrument_id,
        [dt.date(2026, 7, 23), dt.date(2026, 7, 23)],
        [999.0, 1000.0],
    )
    valid_b = _observations(
        instrument_b.instrument_id,
        [dt.date(2026, 7, 23)],
        [201.0],
    )
    provider = RecordingIncrementalProvider(
        {
            instrument_a.instrument_id: [_raw(instrument_a.instrument_id, b"a")],
            instrument_b.instrument_id: [_raw(instrument_b.instrument_id, b"b")],
        }
    )
    state = InMemoryIncrementalIngestionState(
        [instrument_a, instrument_b],
        current_snapshot_manifest_key=current_key,
    )

    result = IncrementalIngestionService(
        state=state,
        provider=provider,
        normalizer=StaticNormalizer(
            {
                instrument_a.instrument_id: invalid_a,
                instrument_b.instrument_id: valid_b,
            }
        ),
        artifact_store=store,
        clock=lambda: dt.datetime(2026, 7, 24, 18, tzinfo=dt.UTC),
    ).run("daily-partial-success")

    assert result.snapshot is not None
    promoted = load_canonical_snapshot(store, result.snapshot.manifest_key)
    assert_frame_equal(
        promoted.filter(pl.col("instrument_id") == instrument_a.instrument_id),
        current.filter(pl.col("instrument_id") == instrument_a.instrument_id),
    )
    assert (
        promoted.filter(
            (pl.col("instrument_id") == instrument_b.instrument_id)
            & (pl.col("observation_date") == dt.date(2026, 7, 23))
        )["value"].item()
        == 201.0
    )
    statuses = {
        status.instrument_id: status
        for status in result.snapshot.manifest.instrument_status
    }
    failed = statuses[instrument_a.instrument_id]
    assert failed.eligible is False
    assert failed.latest_observation_date == dt.date(2026, 7, 23)
    assert [finding.reason_code for finding in failed.findings] == [
        "instrument.duplicate_observation"
    ]
    assert failed.findings[0].check_version == 1
    assert failed.findings[0].measured_values == {"duplicate_key_count": 1}
    assert statuses[instrument_b.instrument_id].eligible is True


def test_warnings_are_non_blocking_and_recorded_in_manifest(
    tmp_path: Path,
) -> None:
    store, current_key, instrument_a, _, _ = _current_snapshot(tmp_path)
    incoming = _observations(
        instrument_a.instrument_id,
        [dt.date(2026, 7, 24)],
        [104.0],
    )
    provider = RecordingIncrementalProvider(
        {instrument_a.instrument_id: [_raw(instrument_a.instrument_id, b"a")]}
    )
    state = InMemoryIncrementalIngestionState(
        [instrument_a],
        current_snapshot_manifest_key=current_key,
    )

    def warning_check(
        instrument: Instrument,
        observations: pl.DataFrame,
        policy: IncrementalIngestionPolicy,
        as_of_date: dt.date,
    ) -> Iterable[InstrumentFinding]:
        del observations, policy, as_of_date
        return (
            InstrumentFinding(
                instrument_id=instrument.instrument_id,
                severity="warning",
                reason_code="instrument.large_price_move",
                check_version=7,
                message="daily move exceeds review threshold",
                measured_values={"move_percent": 12.5},
            ),
        )

    result = IncrementalIngestionService(
        state=state,
        provider=provider,
        normalizer=StaticNormalizer({instrument_a.instrument_id: incoming}),
        artifact_store=store,
        instrument_checks=[warning_check],
        clock=lambda: dt.datetime(2026, 7, 24, 18, tzinfo=dt.UTC),
    ).run("daily-warning")

    assert result.status == "promoted"
    assert result.snapshot is not None
    status = result.snapshot.manifest.instrument_status[0]
    assert status.eligible is True
    assert [finding.reason_code for finding in status.findings] == [
        "instrument.large_price_move"
    ]


def test_no_change_creates_no_snapshot_and_retry_is_idempotent(
    tmp_path: Path,
) -> None:
    store, current_key, instrument_a, _, _ = _current_snapshot(tmp_path)
    unchanged = _observations(
        instrument_a.instrument_id,
        [dt.date(2026, 7, 23)],
        [103.0],
    )
    provider = RecordingIncrementalProvider(
        {instrument_a.instrument_id: [_raw(instrument_a.instrument_id, b"same")]}
    )
    state = InMemoryIncrementalIngestionState(
        [instrument_a],
        current_snapshot_manifest_key=current_key,
    )
    service = IncrementalIngestionService(
        state=state,
        provider=provider,
        normalizer=StaticNormalizer({instrument_a.instrument_id: unchanged}),
        artifact_store=store,
        clock=lambda: dt.datetime(2026, 7, 24, 18, tzinfo=dt.UTC),
    )
    manifests = tmp_path / "canonical-market-data" / "v1" / "manifests"
    before = set(manifests.iterdir())

    first = service.run("daily-no-change")
    second = service.run("daily-no-change")

    assert first.status == "no_change"
    assert first.snapshot is None
    assert second == first
    assert len(provider.requests) == 1
    assert set(manifests.iterdir()) == before
    assert state.current_snapshot_manifest_key() == current_key
    assert state.run_state("daily-no-change") == "no_change"


def test_overlap_lock_prevents_concurrent_promotion(tmp_path: Path) -> None:
    store, current_key, instrument_a, _, _ = _current_snapshot(tmp_path)
    state = InMemoryIncrementalIngestionState(
        [instrument_a],
        current_snapshot_manifest_key=current_key,
    )
    state.begin_ingestion(
        "daily-held",
        dt.datetime(2026, 7, 24, 17, tzinfo=dt.UTC),
    )
    service = IncrementalIngestionService(
        state=state,
        provider=RecordingIncrementalProvider(
            {instrument_a.instrument_id: [_raw(instrument_a.instrument_id, b"a")]}
        ),
        normalizer=StaticNormalizer(
            {
                instrument_a.instrument_id: _observations(
                    instrument_a.instrument_id,
                    [dt.date(2026, 7, 24)],
                    [104.0],
                )
            }
        ),
        artifact_store=store,
    )

    with pytest.raises(ConcurrentIngestionError, match="daily-held"):
        service.run("daily-overlap")


class CorruptingStore:
    def __init__(self, store: ArtifactStore, base_object_key: str) -> None:
        self._store = store
        self._base_object_key = base_object_key

    def put_if_absent(self, key: str, data: bytes) -> None:
        self._store.put_if_absent(key, data)

    def get(self, key: str) -> bytes:
        data = self._store.get(key)
        if key.endswith(".parquet") and key != self._base_object_key:
            return b"corrupt after write"
        return data


def test_checksum_failure_prevents_authoritative_pointer_update(
    tmp_path: Path,
) -> None:
    store, current_key, instrument_a, _, _ = _current_snapshot(tmp_path)
    base_manifest = json.loads(store.get(current_key))
    corrupting_store = CorruptingStore(store, base_manifest["object_key"])
    state = InMemoryIncrementalIngestionState(
        [instrument_a],
        current_snapshot_manifest_key=current_key,
    )
    service = IncrementalIngestionService(
        state=state,
        provider=RecordingIncrementalProvider(
            {instrument_a.instrument_id: [_raw(instrument_a.instrument_id, b"a")]}
        ),
        normalizer=StaticNormalizer(
            {
                instrument_a.instrument_id: _observations(
                    instrument_a.instrument_id,
                    [dt.date(2026, 7, 24)],
                    [104.0],
                )
            }
        ),
        artifact_store=corrupting_store,
        clock=lambda: dt.datetime(2026, 7, 24, 18, tzinfo=dt.UTC),
    )

    with pytest.raises(Exception, match="checksum mismatch"):
        service.run("daily-corrupt")

    assert state.current_snapshot_manifest_key() == current_key
    assert state.run_state("daily-corrupt") == "failed"


def test_marketstack_incremental_provider_sends_only_bounded_date_window() -> None:
    requests: list[dict[str, str]] = []
    bodies = [
        json.dumps(
            {
                "pagination": {"limit": 1, "offset": 0, "count": 1, "total": 2},
                "data": [{"symbol": "AAA"}],
            }
        ).encode(),
        json.dumps(
            {
                "pagination": {"limit": 1, "offset": 1, "count": 1, "total": 2},
                "data": [{"symbol": "AAA"}],
            }
        ).encode(),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(dict(request.url.params))
        return httpx.Response(
            200,
            content=bodies[len(requests) - 1],
            request=request,
        )

    instrument = _instrument(
        "instrument-a",
        symbol="AAA",
        exchange_code="ARCX",
        first=dt.date(2026, 7, 20),
        latest=dt.date(2026, 7, 23),
    )
    provider = MarketstackIncrementalProvider(
        access_key="secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        page_size=1,
        clock=lambda: dt.datetime(2026, 7, 24, 12, tzinfo=dt.UTC),
    )

    responses = tuple(
        provider.fetch_recent(
            instrument,
            start_date=dt.date(2026, 7, 20),
            end_date=dt.date(2026, 7, 24),
        )
    )

    assert requests == [
        {
            "access_key": "secret",
            "symbols": "AAA",
            "date_from": "2026-07-20",
            "date_to": "2026-07-24",
            "limit": "1",
            "offset": "0",
        },
        {
            "access_key": "secret",
            "symbols": "AAA",
            "date_from": "2026-07-20",
            "date_to": "2026-07-24",
            "limit": "1",
            "offset": "1",
        },
    ]
    assert [response.body for response in responses] == bodies
    assert all("access_key" not in response.request_metadata for response in responses)
