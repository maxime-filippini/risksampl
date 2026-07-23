import hashlib
import json
from collections.abc import Mapping
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Annotated
from typing import Literal
from typing import Protocol
from typing import Self

import numpy as np
import pyarrow as pa
import pyarrow.parquet as parquet
import pydantic
from var_lab import compute_var
from var_lab import var


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _definition_hash(definition: pydantic.BaseModel) -> str:
    return hashlib.sha256(_canonical_json(definition.model_dump(mode="json"))).hexdigest()


type NonEmptyString = Annotated[str, pydantic.Field(min_length=1)]
type PositiveFloat = Annotated[float, pydantic.Field(gt=0)]
type ConfidenceLevel = Annotated[float, pydantic.Field(gt=0, lt=1)]
type DecayFactor = Annotated[float, pydantic.Field(gt=0, le=1)]
type LookbackWindow = Annotated[int, pydantic.Field(gt=0)]


class _ValidatedModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        frozen=True,
    )


class HoldingDefinition(_ValidatedModel):
    symbol: NonEmptyString
    weight: PositiveFloat


class PortfolioDefinition(_ValidatedModel):
    id: NonEmptyString
    version: NonEmptyString
    holdings: Annotated[tuple[HoldingDefinition, ...], pydantic.Field(min_length=1)]

    @pydantic.model_validator(mode="after")
    def validate_holdings(self) -> Self:
        symbols = [holding.symbol for holding in self.holdings]
        if len(symbols) != len(set(symbols)):
            raise ValueError("portfolio holding symbols must be unique")
        if not np.isclose(sum(holding.weight for holding in self.holdings), 1.0):
            raise ValueError("portfolio holding weights must sum to 1")
        return self

    @property
    def hash(self) -> str:
        return _definition_hash(self)


class VarDefinition(_ValidatedModel):
    kind: Literal["historical"] = "historical"
    id: NonEmptyString
    version: NonEmptyString
    confidence_level: ConfidenceLevel
    horizon_days: Literal[1]
    lookback_window: LookbackWindow
    interpolation: var.QuantileInterpolation
    decay_factor: DecayFactor

    @property
    def hash(self) -> str:
        return _definition_hash(self)

    def to_var_spec(self) -> var.HistoricalSimulationsVarSpec:
        return var.HistoricalSimulationsVarSpec(
            id=self.id,
            confidence_level=self.confidence_level,
            lookback_window=self.lookback_window,
            interpolation=self.interpolation,
            decay_factor=self.decay_factor,
        )


class SnapshotDefinitions(_ValidatedModel):
    portfolio: PortfolioDefinition
    model: VarDefinition


class MarketDataSource(_ValidatedModel):
    name: NonEmptyString
    version: NonEmptyString


class MarketData(_ValidatedModel):
    returns_by_symbol: Mapping[str, tuple[float, ...]]
    source: MarketDataSource


class MarketDataAdapter(Protocol):
    def load_returns(self, reference_date: date, symbols: tuple[str, ...]) -> MarketData: ...


class ArtifactStore(Protocol):
    def exists(self, key: str) -> bool: ...

    def write(self, key: str, content: bytes) -> None: ...

    def read(self, key: str) -> bytes: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def path_for(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("artifact key must remain within the store root")
        return path

    def write(self, key: str, content: bytes) -> None:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def read(self, key: str) -> bytes:
        return self.path_for(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self.path_for(key).exists()


class ArtifactLocations(_ValidatedModel):
    analytical: str
    dashboard: str


class SnapshotManifest(_ValidatedModel):
    as_of_date: date
    published_at: pydantic.AwareDatetime
    artifacts: ArtifactLocations
    data_source: MarketDataSource
    portfolio_definition_hash: str
    model_definition_hash: str


class PublishedSnapshot(_ValidatedModel):
    var: Annotated[float, pydantic.Field(ge=0)]
    manifest: SnapshotManifest
    manifest_key: str


class PublicationValidationError(ValueError):
    pass


class PublicationAlreadyExistsError(ValueError):
    pass


def publish_daily_snapshot(
    *,
    reference_date: date,
    definitions: SnapshotDefinitions,
    market_data: MarketDataAdapter,
    artifact_store: ArtifactStore,
    clock: Clock,
) -> PublishedSnapshot:
    prefix = f"snapshots/{reference_date.isoformat()}"
    manifest_key = f"{prefix}/manifest.json"
    if artifact_store.exists(manifest_key):
        raise PublicationAlreadyExistsError(f"snapshot for {reference_date.isoformat()} is already published")

    symbols = tuple(holding.symbol for holding in definitions.portfolio.holdings)
    loaded_market_data = market_data.load_returns(reference_date, symbols)
    portfolio_returns = _portfolio_returns(loaded_market_data, definitions.portfolio)
    var_value = float(compute_var(portfolio_returns, definitions.model.to_var_spec()).item())
    if not np.isfinite(var_value) or var_value < 0:
        raise PublicationValidationError("VaR result must be finite and non-negative")

    row = {
        "as_of_date": reference_date.isoformat(),
        "model_id": definitions.model.id,
        "portfolio_id": definitions.portfolio.id,
        "var": var_value,
    }
    artifacts = ArtifactLocations(
        analytical=f"{prefix}/analytical.parquet",
        dashboard=f"{prefix}/dashboard.json",
    )
    analytical_content = _serialize_analytical(row)
    dashboard_content = _canonical_json({"results": [row]})

    artifact_store.write(artifacts.analytical, analytical_content)
    artifact_store.write(artifacts.dashboard, dashboard_content)
    _validate_stored_artifacts(artifact_store, artifacts, row)

    manifest = SnapshotManifest(
        as_of_date=reference_date,
        published_at=clock.now(),
        artifacts=artifacts,
        data_source=loaded_market_data.source,
        portfolio_definition_hash=definitions.portfolio.hash,
        model_definition_hash=definitions.model.hash,
    )
    artifact_store.write(manifest_key, _serialize_manifest(manifest))
    return PublishedSnapshot(var=var_value, manifest=manifest, manifest_key=manifest_key)


def _portfolio_returns(market_data: MarketData, portfolio: PortfolioDefinition) -> np.ndarray:
    series: list[np.ndarray] = []
    for holding in portfolio.holdings:
        if holding.symbol not in market_data.returns_by_symbol:
            raise PublicationValidationError(f"market data is missing returns for {holding.symbol!r}")
        values = np.asarray(market_data.returns_by_symbol[holding.symbol], dtype=np.float64)
        if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
            raise PublicationValidationError(f"returns for {holding.symbol!r} must be a finite non-empty series")
        series.append(values)

    lengths = {values.size for values in series}
    if len(lengths) != 1:
        raise PublicationValidationError("holding return series must have equal lengths")

    weights = np.asarray([holding.weight for holding in portfolio.holdings], dtype=np.float64)
    return np.asarray(np.stack(series, axis=1) @ weights, dtype=np.float64)


def _serialize_analytical(row: dict[str, str | float]) -> bytes:
    sink = pa.BufferOutputStream()
    parquet.write_table(pa.Table.from_pylist([row]), sink)
    return sink.getvalue().to_pybytes()


def _validate_stored_artifacts(
    store: ArtifactStore,
    artifacts: ArtifactLocations,
    expected_row: dict[str, str | float],
) -> None:
    try:
        analytical_rows = parquet.read_table(pa.BufferReader(store.read(artifacts.analytical))).to_pylist()
        dashboard = json.loads(store.read(artifacts.dashboard))
    except Exception as error:
        raise PublicationValidationError("published artifacts could not be read") from error

    if analytical_rows != [expected_row]:
        raise PublicationValidationError("analytical artifact failed validation")
    if dashboard != {"results": [expected_row]}:
        raise PublicationValidationError("dashboard artifact failed validation")


def _serialize_manifest(manifest: SnapshotManifest) -> bytes:
    return _canonical_json(manifest.model_dump(mode="json"))
