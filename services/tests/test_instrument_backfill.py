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
    DirectoryArtifactStore,
    load_canonical_snapshot,
    publish_canonical_snapshot,
)
from risksampl_services.instrument_backfill import (
    BackfillValidationError,
    ExplicitCatchUpRequiredError,
    InMemoryBackfillState,
    Instrument,
    InstrumentBackfillPolicy,
    InstrumentBackfillService,
    MarketstackEodNormalizer,
    MarketstackFullHistoryProvider,
    ProviderNormalizationError,
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


class RecordingProvider:
    def __init__(self, responses: Iterable[RawProviderResponse]) -> None:
        self._responses = tuple(responses)
        self.requested_instrument_ids: list[str] = []

    def fetch_full_history(
        self,
        instrument: Instrument,
    ) -> Iterable[RawProviderResponse]:
        self.requested_instrument_ids.append(instrument.instrument_id)
        yield from self._responses


class StaticNormalizer:
    def __init__(
        self,
        observations: pl.DataFrame | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self._observations = observations
        self._error = error

    def normalize(
        self,
        instrument: Instrument,
        responses: tuple[RawProviderResponse, ...],
    ) -> pl.DataFrame:
        if self._error is not None:
            raise self._error
        assert self._observations is not None
        return self._observations


def _raw(body: bytes, *, page: int = 0) -> RawProviderResponse:
    return RawProviderResponse(
        provider="marketstack",
        body=body,
        retrieved_at=dt.datetime(2026, 7, 24, 12, page, tzinfo=dt.UTC),
        request_metadata={
            "endpoint": "https://api.marketstack.com/v2/eod",
            "symbol": "SPY",
            "offset": str(page * 1000),
        },
        response_metadata={"status_code": "200", "content_type": "application/json"},
    )


def _instrument() -> Instrument:
    return Instrument(
        instrument_id="instrument-spy",
        provider_symbol="SPY",
        exchange_code="ARCX",
        currency="USD",
    )


def test_backfill_retains_raw_pages_and_enables_only_the_requested_instrument(
    tmp_path: Path,
) -> None:
    store = DirectoryArtifactStore(tmp_path)
    existing = _observations(
        "instrument-qqq",
        [dt.date(2026, 7, 23)],
        [500.0],
    )
    current = publish_canonical_snapshot(
        existing,
        store,
        created_at=dt.datetime(2026, 7, 23, 18, tzinfo=dt.UTC),
    )
    target = _instrument()
    other = Instrument(
        instrument_id="instrument-qqq",
        provider_symbol="QQQ",
        exchange_code="XNAS",
        currency="USD",
        enabled=True,
        first_validated_observation_date=dt.date(2026, 7, 23),
        latest_validated_observation_date=dt.date(2026, 7, 23),
    )
    state = InMemoryBackfillState(
        [target, other],
        current_snapshot_manifest_key=current.manifest_key,
    )
    responses = (_raw(b'{"page":0}'), _raw(b'{"page":1}', page=1))
    provider = RecordingProvider(responses)
    normalized = _observations(
        target.instrument_id,
        [dt.date(2026, 7, 22), dt.date(2026, 7, 24)],
        [600.0, 605.0],
    )

    result = InstrumentBackfillService(
        state=state,
        provider=provider,
        normalizer=StaticNormalizer(normalized),
        artifact_store=store,
        clock=lambda: dt.datetime(2026, 7, 24, 13, tzinfo=dt.UTC),
    ).backfill_and_enable(target.instrument_id)

    assert provider.requested_instrument_ids == [target.instrument_id]
    assert [store.get(item.object_key) for item in result.raw_responses] == [
        response.body for response in responses
    ]
    assert all(
        "access_key" not in item.request_metadata for item in result.raw_responses
    )
    onboarded = state.get_instrument(target.instrument_id)
    assert onboarded.enabled is True
    assert onboarded.catch_up_required is False
    assert onboarded.first_validated_observation_date == dt.date(2026, 7, 22)
    assert onboarded.latest_validated_observation_date == dt.date(2026, 7, 24)
    assert result.instrument == onboarded
    assert state.get_instrument(other.instrument_id) == other

    expected = pl.concat([existing, normalized], how="vertical").sort(
        "instrument_id",
        "observation_date",
        "metric",
        "value",
    )
    assert_frame_equal(
        load_canonical_snapshot(store, state.current_snapshot_manifest_key()),
        expected,
    )


def test_raw_response_is_retained_before_normalization_failure(tmp_path: Path) -> None:
    store = DirectoryArtifactStore(tmp_path)
    target = _instrument()
    state = InMemoryBackfillState([target])
    response = _raw(b'{"provider":"evidence"}')
    service = InstrumentBackfillService(
        state=state,
        provider=RecordingProvider([response]),
        normalizer=StaticNormalizer(error=ProviderNormalizationError("bad payload")),
        artifact_store=store,
    )

    with pytest.raises(ProviderNormalizationError, match="bad payload"):
        service.backfill_and_enable(target.instrument_id)

    retained_objects = list(
        (tmp_path / "raw-provider-responses" / "v1" / "objects").iterdir()
    )
    assert len(retained_objects) == 1
    assert retained_objects[0].read_bytes() == response.body
    assert state.get_instrument(target.instrument_id) == target
    assert state.current_snapshot_manifest_key() is None


def test_validation_failure_does_not_enable_or_promote(tmp_path: Path) -> None:
    store = DirectoryArtifactStore(tmp_path)
    target = _instrument()
    state = InMemoryBackfillState([target])
    service = InstrumentBackfillService(
        state=state,
        provider=RecordingProvider([_raw(b"valid raw evidence")]),
        normalizer=StaticNormalizer(
            _observations(
                target.instrument_id,
                [dt.date(2026, 7, 24)],
                [605.0],
            )
        ),
        artifact_store=store,
        policy=InstrumentBackfillPolicy(minimum_observations_per_metric=2),
    )

    with pytest.raises(
        BackfillValidationError,
        match="requires at least 2 observations",
    ):
        service.backfill_and_enable(target.instrument_id)

    assert state.get_instrument(target.instrument_id) == target
    assert state.current_snapshot_manifest_key() is None


def test_configured_snapshot_check_runs_before_promotion(tmp_path: Path) -> None:
    target = _instrument()
    state = InMemoryBackfillState([target])
    checked: list[pl.DataFrame] = []

    def reject_snapshot(candidate: pl.DataFrame) -> None:
        checked.append(candidate)
        raise BackfillValidationError("configured snapshot check failed")

    service = InstrumentBackfillService(
        state=state,
        provider=RecordingProvider([_raw(b"raw")]),
        normalizer=StaticNormalizer(
            _observations(
                target.instrument_id,
                [dt.date(2026, 7, 24)],
                [605.0],
            )
        ),
        artifact_store=DirectoryArtifactStore(tmp_path),
        snapshot_checks=[reject_snapshot],
    )

    with pytest.raises(BackfillValidationError, match="configured snapshot"):
        service.backfill_and_enable(target.instrument_id)

    assert len(checked) == 1
    assert state.current_snapshot_manifest_key() is None
    assert state.get_instrument(target.instrument_id).enabled is False


def test_disabling_preserves_history_and_requires_explicit_catch_up(
    tmp_path: Path,
) -> None:
    store = DirectoryArtifactStore(tmp_path)
    target = _instrument()
    state = InMemoryBackfillState([target])
    initial = _observations(
        target.instrument_id,
        [dt.date(2026, 7, 22), dt.date(2026, 7, 23)],
        [600.0, 602.0],
    )
    first_provider = RecordingProvider([_raw(b"initial")])
    service = InstrumentBackfillService(
        state=state,
        provider=first_provider,
        normalizer=StaticNormalizer(initial),
        artifact_store=store,
        clock=lambda: dt.datetime(2026, 7, 23, 18, tzinfo=dt.UTC),
    )
    service.backfill_and_enable(target.instrument_id)
    snapshot_before_disable = state.current_snapshot_manifest_key()

    disabled = service.disable(target.instrument_id)

    assert disabled.enabled is False
    assert disabled.catch_up_required is True
    assert state.current_snapshot_manifest_key() == snapshot_before_disable
    assert_frame_equal(
        load_canonical_snapshot(store, snapshot_before_disable),
        initial.sort("instrument_id", "observation_date", "metric", "value"),
    )
    with pytest.raises(ExplicitCatchUpRequiredError, match="catch-up"):
        service.backfill_and_enable(target.instrument_id)
    assert first_provider.requested_instrument_ids == [target.instrument_id]

    caught_up = _observations(
        target.instrument_id,
        [dt.date(2026, 7, 22), dt.date(2026, 7, 24)],
        [600.0, 605.0],
    )
    catch_up_provider = RecordingProvider([_raw(b"catch-up")])
    catch_up_service = InstrumentBackfillService(
        state=state,
        provider=catch_up_provider,
        normalizer=StaticNormalizer(caught_up),
        artifact_store=store,
        clock=lambda: dt.datetime(2026, 7, 24, 18, tzinfo=dt.UTC),
    )

    result = catch_up_service.catch_up_and_enable(target.instrument_id)

    assert catch_up_provider.requested_instrument_ids == [target.instrument_id]
    assert result.instrument.enabled is True
    assert result.instrument.catch_up_required is False
    assert result.instrument.latest_validated_observation_date == dt.date(2026, 7, 24)
    assert_frame_equal(
        load_canonical_snapshot(store, state.current_snapshot_manifest_key()),
        caught_up.sort("instrument_id", "observation_date", "metric", "value"),
    )


def test_marketstack_normalizer_maps_exact_pages_to_canonical_observations() -> None:
    instrument = _instrument()
    first_page = {
        "pagination": {"limit": 1, "offset": 0, "count": 1, "total": 2},
        "data": [
            {
                "date": "2026-07-24T00:00:00+0000",
                "symbol": "SPY",
                "exchange": "ARCX",
                "price_currency": "USD",
                "adj_close": 605.25,
            }
        ],
    }
    second_page = {
        "pagination": {"limit": 1, "offset": 1, "count": 1, "total": 2},
        "data": [
            {
                "date": "2026-07-23T00:00:00+0000",
                "symbol": "SPY",
                "exchange_code": "ARCX",
                "price_currency": "USD",
                "adj_close": 602.5,
            }
        ],
    }

    normalized = MarketstackEodNormalizer().normalize(
        instrument,
        (
            _raw(json.dumps(first_page).encode()),
            _raw(json.dumps(second_page).encode(), page=1),
        ),
    )

    assert_frame_equal(
        normalized,
        _observations(
            instrument.instrument_id,
            [dt.date(2026, 7, 23), dt.date(2026, 7, 24)],
            [602.5, 605.25],
        ),
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("symbol", "QQQ", "provider symbol"),
        ("exchange", "XNAS", "exchange code"),
        ("price_currency", "EUR", "currency"),
    ],
)
def test_marketstack_normalizer_rejects_wrong_instrument_identity(
    field: str,
    value: str,
    message: str,
) -> None:
    row = {
        "date": "2026-07-24T00:00:00+0000",
        "symbol": "SPY",
        "exchange": "ARCX",
        "price_currency": "USD",
        "adj_close": 605.25,
    }
    row[field] = value
    response = _raw(json.dumps({"data": [row]}).encode())

    with pytest.raises(ProviderNormalizationError, match=message):
        MarketstackEodNormalizer().normalize(_instrument(), (response,))


def test_marketstack_provider_fetches_every_page_for_one_symbol() -> None:
    request_queries: list[dict[str, str]] = []
    bodies = [
        json.dumps(
            {
                "pagination": {"limit": 1, "offset": 0, "count": 1, "total": 2},
                "data": [{"symbol": "SPY"}],
            },
            separators=(",", ":"),
        ).encode(),
        json.dumps(
            {
                "pagination": {"limit": 1, "offset": 1, "count": 1, "total": 2},
                "data": [{"symbol": "SPY"}],
            },
            separators=(",", ":"),
        ).encode(),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        query = dict(request.url.params)
        request_queries.append(query)
        return httpx.Response(
            200, content=bodies[len(request_queries) - 1], request=request
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = MarketstackFullHistoryProvider(
        access_key="secret",
        client=client,
        page_size=1,
        clock=lambda: dt.datetime(2026, 7, 24, 12, tzinfo=dt.UTC),
    )

    responses = tuple(provider.fetch_full_history(_instrument()))

    assert request_queries == [
        {"access_key": "secret", "symbols": "SPY", "limit": "1", "offset": "0"},
        {"access_key": "secret", "symbols": "SPY", "limit": "1", "offset": "1"},
    ]
    assert [response.body for response in responses] == bodies
    assert [response.request_metadata["offset"] for response in responses] == [
        "0",
        "1",
    ]
    assert all("access_key" not in response.request_metadata for response in responses)


def test_instrument_requires_complete_stable_provider_identity() -> None:
    with pytest.raises(ValueError):
        Instrument(
            instrument_id="instrument-spy",
            provider_symbol="",
            exchange_code="ARCX",
            currency="USD",
        )
    with pytest.raises(ValueError):
        Instrument(
            instrument_id="instrument-spy",
            provider_symbol="SPY",
            exchange_code="",
            currency="USD",
        )
    with pytest.raises(ValueError):
        Instrument(
            instrument_id="instrument-spy",
            provider_symbol="SPY",
            exchange_code="ARCX",
            currency="US",
        )
