from typing import Annotated, Literal, Self

import pydantic

type ConfidenceLevel = Annotated[float, pydantic.Field(lt=1, gt=0)]
type QuantileInterpolation = Literal["left", "right", "linear"]


class BaseVarSpec(pydantic.BaseModel):
    id: str
    confidence_level: ConfidenceLevel
    lookback_window: int = pydantic.Field(gt=0)


class BaseVolatilitySpec(pydantic.BaseModel):
    lookback_window: int = pydantic.Field(gt=1)


class SampleVolatilitySpec(BaseVolatilitySpec):
    kind: Literal["sample-volatility"]


class EwmaVolatilitySpec(BaseVolatilitySpec):
    kind: Literal["ewma-volatility"]
    decay_factor: float = pydantic.Field(lt=1, gt=0)
    warm_up_window: int = pydantic.Field(gt=1)

    @pydantic.model_validator(mode="after")
    def validate_warm_up_window(self) -> Self:
        if self.warm_up_window > self.lookback_window:
            raise ValueError("warm-up window cannot exceed lookback window")
        return self


type VolatilitySpec = SampleVolatilitySpec | EwmaVolatilitySpec


class FilterSpec(pydantic.BaseModel):
    volatility: VolatilitySpec = pydantic.Field(discriminator="kind")


class HistoricalSimulationsVarSpec(BaseVarSpec):
    kind: Literal["historical"]
    filter: FilterSpec | None = pydantic.Field(default=None)
    interpolation: QuantileInterpolation
    decay_factor: float = pydantic.Field(le=1, gt=0)


class BaseDistributionSpec(pydantic.BaseModel):
    pass


class GaussianDistributionSpec(BaseDistributionSpec):
    kind: Literal["gaussian"]
    volatility: VolatilitySpec = pydantic.Field(discriminator="kind")


class StudentTDistributionSpec(BaseDistributionSpec):
    kind: Literal["t"]
    volatility: VolatilitySpec = pydantic.Field(discriminator="kind")
    dof: int = pydantic.Field(gt=0)


type DistributionSpec = GaussianDistributionSpec | StudentTDistributionSpec


class ParametricVarSpec(BaseVarSpec):
    kind: Literal["parametric"]
    dist: DistributionSpec = pydantic.Field(discriminator="kind")


type VarSpec = Annotated[
    HistoricalSimulationsVarSpec | ParametricVarSpec,
    pydantic.Field(discriminator="kind"),
]

var_spec_adapter: pydantic.TypeAdapter[VarSpec] = pydantic.TypeAdapter(VarSpec)
