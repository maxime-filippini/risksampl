import json
from collections.abc import Mapping
from datetime import date
from datetime import datetime
from datetime import timezone

import pyarrow.parquet as parquet
import pytest

from worker.value_at_risk.publication import BenchmarkDefinitions
from worker.value_at_risk.publication import HistoricalVarDefinition
from worker.value_at_risk.publication import HoldingDefinition
from worker.value_at_risk.publication import LocalArtifactStore
from worker.value_at_risk.publication import MarketData
from worker.value_at_risk.publication import MarketDataSource
from worker.value_at_risk.publication import PortfolioDefinition
from worker.value_at_risk.publication import PublicationValidationError
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


def historical_definitions() -> BenchmarkDefinitions:
    return BenchmarkDefinitions(
        portfolio=PortfolioDefinition(
            id="diversified-equity",
            version="1",
            holdings=(
                HoldingDefinition(symbol="SPY", weight=0.6),
                HoldingDefinition(symbol="EFA", weight=0.4),
            ),
        ),
        model=HistoricalVarDefinition(
            id="historical-99",
            version="1",
            confidence_level=0.99,
            horizon_days=1,
            lookback_window=4,
            interpolation="left",
            decay_factor=1.0,
        ),
    )


def test_publish_one_historical_var_snapshot(tmp_path) -> None:
    reference_date = date(2026, 7, 21)
    publication_time = datetime(2026, 7, 22, 7, 0, tzinfo=timezone.utc)
    definitions = historical_definitions()
    store = LocalArtifactStore(tmp_path)

    published = publish_daily_snapshot(
        reference_date=reference_date,
        definitions=definitions,
        market_data=DeterministicMarketData(
            {
                "SPY": (-0.05, -0.01, 0.02, -0.02),
                "EFA": (-0.025, -0.035, -0.005, -0.045),
            }
        ),
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
        "published_at": "2026-07-22T07:00:00+00:00",
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
            definitions=historical_definitions(),
            market_data=DeterministicMarketData(
                {
                    "SPY": (-0.05, -0.01, 0.02, -0.02),
                    "EFA": (-0.025, -0.035, -0.005, -0.045),
                }
            ),
            artifact_store=store,
            clock=FixedClock(datetime(2026, 7, 22, 7, 0, tzinfo=timezone.utc)),
        )

    assert not store.path_for("snapshots/2026-07-21/manifest.json").exists()
