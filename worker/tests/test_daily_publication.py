import json
from collections.abc import Mapping
from datetime import date
from datetime import datetime
from datetime import timezone

import pyarrow.parquet as parquet
import pydantic
import pytest

from worker.value_at_risk.publication import HoldingDefinition
from worker.value_at_risk.publication import LocalArtifactStore
from worker.value_at_risk.publication import MarketData
from worker.value_at_risk.publication import MarketDataSource
from worker.value_at_risk.publication import PortfolioDefinition
from worker.value_at_risk.publication import PublicationAlreadyExistsError
from worker.value_at_risk.publication import PublicationValidationError
from worker.value_at_risk.publication import SnapshotDefinitions
from worker.value_at_risk.publication import VarDefinition
from worker.value_at_risk.publication import publish_daily_snapshot


class DeterministicMarketData:
    def __init__(self, returns_by_symbol: Mapping[str, tuple[float, ...]]) -> None:
        self._returns_by_symbol = returns_by_symbol

    def load_returns(self, reference_date: date, symbols: tuple[str, ...]) -> MarketData:
        return MarketData(
            returns_by_symbol={symbol: self._returns_by_symbol[symbol] for symbol in symbols},
            source=MarketDataSource(name="deterministic-fixture", version="v1"),
        )


class FixedClock:
    def __init__(self, timestamp: datetime) -> None:
        self._timestamp = timestamp

    def now(self) -> datetime:
        return self._timestamp


class CorruptingDashboardStore(LocalArtifactStore):
    def write(self, key: str, content: bytes) -> None:
        if key.endswith("dashboard.json"):
            content = b'{"results":[]}'
        super().write(key, content)


def snapshot_definitions() -> SnapshotDefinitions:
    return SnapshotDefinitions(
        portfolio=PortfolioDefinition(
            id="diversified-equity",
            version="1",
            holdings=(
                HoldingDefinition(symbol="SPY", weight=0.6),
                HoldingDefinition(symbol="EFA", weight=0.4),
            ),
        ),
        model=VarDefinition(
            id="historical-99",
            version="1",
            confidence_level=0.99,
            horizon_days=1,
            lookback_window=4,
            interpolation="left",
            decay_factor=1.0,
        ),
    )


def deterministic_returns() -> dict[str, tuple[float, ...]]:
    return {
        "SPY": (-0.05, -0.01, 0.02, -0.02),
        "EFA": (-0.025, -0.035, -0.005, -0.045),
    }


def test_snapshot_definitions_validate_serialized_json() -> None:
    serialized = json.dumps(
        {
            "portfolio": {
                "id": "diversified-equity",
                "version": "1",
                "holdings": [
                    {"symbol": "SPY", "weight": 0.6},
                    {"symbol": "EFA", "weight": 0.4},
                ],
            },
            "model": {
                "kind": "historical",
                "id": "historical-99",
                "version": "1",
                "confidence_level": 0.99,
                "horizon_days": 1,
                "lookback_window": 4,
                "interpolation": "left",
                "decay_factor": 1.0,
            },
        }
    )

    assert SnapshotDefinitions.model_validate_json(serialized) == snapshot_definitions()


def test_snapshot_definitions_reject_invalid_serialized_json() -> None:
    serialized = json.dumps(
        {
            "portfolio": {
                "id": "diversified-equity",
                "version": "1",
                "holdings": [
                    {"symbol": "SPY", "weight": 0.7},
                    {"symbol": "EFA", "weight": 0.4},
                ],
            },
            "model": {
                "kind": "historical",
                "id": "historical-99",
                "version": "1",
                "confidence_level": 0.99,
                "horizon_days": 1,
                "lookback_window": 4,
                "interpolation": "left",
                "decay_factor": 1.0,
            },
        }
    )

    with pytest.raises(pydantic.ValidationError, match="holding weights must sum to 1"):
        SnapshotDefinitions.model_validate_json(serialized)


def test_publish_one_historical_var_snapshot(tmp_path) -> None:
    reference_date = date(2026, 7, 21)
    publication_time = datetime(2026, 7, 22, 7, 0, tzinfo=timezone.utc)
    definitions = snapshot_definitions()
    store = LocalArtifactStore(tmp_path)

    published = publish_daily_snapshot(
        reference_date=reference_date,
        definitions=definitions,
        market_data=DeterministicMarketData(deterministic_returns()),
        artifact_store=store,
        clock=FixedClock(publication_time),
    )

    assert published.var == 0.04
    assert published.manifest.as_of_date == reference_date
    assert published.manifest.published_at == publication_time
    assert published.manifest.data_source == MarketDataSource(name="deterministic-fixture", version="v1")
    assert published.manifest.portfolio_definition_hash == definitions.portfolio.hash
    assert published.manifest.model_definition_hash == definitions.model.hash

    manifest = json.loads(store.read(published.manifest_key))
    dashboard = json.loads(store.read(manifest["artifacts"]["dashboard"]))
    analytical = parquet.read_table(store.path_for(manifest["artifacts"]["analytical"]))

    assert manifest == {
        "artifacts": {
            "analytical": "snapshots/2026-07-21/analytical.parquet",
            "dashboard": "snapshots/2026-07-21/dashboard.json",
        },
        "as_of_date": "2026-07-21",
        "data_source": {"name": "deterministic-fixture", "version": "v1"},
        "model_definition_hash": definitions.model.hash,
        "portfolio_definition_hash": definitions.portfolio.hash,
        "published_at": "2026-07-22T07:00:00Z",
    }
    assert dashboard["results"] == [
        {
            "as_of_date": "2026-07-21",
            "model_id": "historical-99",
            "portfolio_id": "diversified-equity",
            "var": 0.04,
        }
    ]
    assert analytical.to_pylist() == dashboard["results"]


def test_validation_failure_does_not_publish_a_manifest(tmp_path) -> None:
    reference_date = date(2026, 7, 21)
    store = CorruptingDashboardStore(tmp_path)

    with pytest.raises(PublicationValidationError, match="dashboard artifact failed validation"):
        publish_daily_snapshot(
            reference_date=reference_date,
            definitions=snapshot_definitions(),
            market_data=DeterministicMarketData(deterministic_returns()),
            artifact_store=store,
            clock=FixedClock(datetime(2026, 7, 22, 7, 0, tzinfo=timezone.utc)),
        )

    assert not store.path_for("snapshots/2026-07-21/manifest.json").exists()


def test_existing_publication_is_not_overwritten(tmp_path) -> None:
    reference_date = date(2026, 7, 21)
    store = LocalArtifactStore(tmp_path)
    publication = {
        "reference_date": reference_date,
        "definitions": snapshot_definitions(),
        "artifact_store": store,
        "clock": FixedClock(datetime(2026, 7, 22, 7, 0, tzinfo=timezone.utc)),
    }
    published = publish_daily_snapshot(market_data=DeterministicMarketData(deterministic_returns()), **publication)
    original_manifest = store.read(published.manifest_key)
    original_analytical = store.read(published.manifest.artifacts.analytical)
    original_dashboard = store.read(published.manifest.artifacts.dashboard)

    with pytest.raises(PublicationAlreadyExistsError):
        publish_daily_snapshot(
            market_data=DeterministicMarketData(
                {
                    "SPY": (-0.10, -0.08, -0.06, -0.04),
                    "EFA": (-0.05, -0.03, -0.01, 0.01),
                }
            ),
            **publication,
        )

    assert store.read(published.manifest_key) == original_manifest
    assert store.read(published.manifest.artifacts.analytical) == original_analytical
    assert store.read(published.manifest.artifacts.dashboard) == original_dashboard
