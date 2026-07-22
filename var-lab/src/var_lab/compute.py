from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, assert_never, cast

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy import stats

from var_lab import var

# Returns have shape (time, *batch). Every computation operates on the first
# axis, leaving the remaining axes available for vectorized batches.
type FloatArray[TShape: tuple[int, ...]] = np.ndarray[TShape, np.dtype[np.float64]]
type NonScalarShape = tuple[int, *tuple[int, ...]]
type BatchShape = tuple[int, ...]
type ReturnsArray = FloatArray[NonScalarShape]
type BatchArray = FloatArray[BatchShape]
type RolledShape = tuple[int, *tuple[int, ...], int]
type NumpyQuantileMethod = Literal["lower", "higher", "linear"]


@dataclass(frozen=True, slots=True)
class FilteredReturnSet:
    """Returns produced by one structurally unique filter specification."""

    filter_spec: var.FilterSpec
    returns: ReturnsArray


@dataclass(frozen=True, slots=True)
class PreparedReturns:
    """Original returns plus reusable outputs from a filtering step."""

    unfiltered: ReturnsArray
    filtered: tuple[FilteredReturnSet, ...]

    def _returns_for(self, spec: var.VarSpec) -> ReturnsArray:
        filter_spec = _filter_for_spec(spec)
        if filter_spec is None:
            return self.unfiltered

        for return_set in self.filtered:
            if return_set.filter_spec == filter_spec:
                return return_set.returns

        raise ValueError(f"filter for model {spec.id!r} has not been prepared")


def extract_unique_filters(
    specs: Iterable[var.VarSpec],
) -> tuple[var.FilterSpec, ...]:
    """Return structurally unique filters in first-occurrence order."""
    return _deduplicate_filters(
        filter_spec
        for spec in specs
        if (filter_spec := _filter_for_spec(spec)) is not None
    )


def apply_filters(
    returns: ReturnsArray,
    filters: Iterable[var.FilterSpec],
) -> PreparedReturns:
    """Compute each unique filter once against the same return batches."""
    validated_returns = _validate_returns(returns)
    filtered = tuple(
        FilteredReturnSet(
            filter_spec=filter_spec,
            returns=_apply_filter(validated_returns, filter_spec),
        )
        for filter_spec in _deduplicate_filters(filters)
    )
    return PreparedReturns(unfiltered=validated_returns, filtered=filtered)


def compute_vars(
    returns: ReturnsArray,
    specs: Sequence[var.VarSpec],
) -> dict[str, BatchArray]:
    """Compute multiple models, preparing every unique filter once."""
    _validate_unique_model_ids(specs)
    prepared_returns = apply_filters(returns, extract_unique_filters(specs))
    return compute_vars_from_prepared_returns(prepared_returns, specs)


def compute_vars_from_prepared_returns(
    prepared_returns: PreparedReturns,
    specs: Sequence[var.VarSpec],
) -> dict[str, BatchArray]:
    """Compute multiple models from already prepared returns.

    Results are keyed by model id. Filtering is never performed by this
    function; every referenced filter must exist in ``prepared_returns``.
    """
    _validate_unique_model_ids(specs)

    return {
        spec.id: _compute_var_from_prepared_returns(
            prepared_returns._returns_for(spec), spec
        )
        for spec in specs
    }


def compute_var(returns: ReturnsArray, spec: var.VarSpec) -> BatchArray:
    """Compute positive-loss VaR independently for every batch.

    The first input axis is time and is removed from the result. An input with
    shape ``(time, *batch)`` therefore produces an output with shape ``batch``.
    A one-dimensional input produces a zero-dimensional array. This convenience
    function prepares the model's filter, if any, before computing VaR.
    """
    return compute_vars(returns, (spec,))[spec.id]


def _compute_var_from_prepared_returns(
    returns: ReturnsArray, spec: var.VarSpec
) -> BatchArray:
    """Compute VaR from returns already selected for a model's filter."""

    match spec:
        case var.HistoricalSimulationsVarSpec():
            return _compute_historical_var(returns, spec)

        case var.ParametricVarSpec():
            return _compute_parametric_var(returns, spec)

        case _:
            assert_never(spec)


def _filter_for_spec(spec: var.VarSpec) -> var.FilterSpec | None:
    match spec:
        case var.HistoricalSimulationsVarSpec(filter=filter_spec):
            return filter_spec

        case var.ParametricVarSpec():
            return None

        case _:
            assert_never(spec)


def _deduplicate_filters(
    filters: Iterable[var.FilterSpec],
) -> tuple[var.FilterSpec, ...]:
    unique_filters: list[var.FilterSpec] = []
    for filter_spec in filters:
        if filter_spec not in unique_filters:
            unique_filters.append(filter_spec)
    return tuple(unique_filters)


def _validate_unique_model_ids(specs: Sequence[var.VarSpec]) -> None:
    model_ids = [spec.id for spec in specs]
    if len(model_ids) != len(set(model_ids)):
        raise ValueError("model ids must be unique")


def _validate_returns[TShape: NonScalarShape](
    returns: FloatArray[TShape],
) -> FloatArray[TShape]:
    values = np.asarray(returns, dtype=np.float64)
    if values.ndim == 0:
        raise ValueError("returns must have a time axis")
    if values.shape[0] == 0:
        raise ValueError("returns must contain at least one observation")
    if not np.all(np.isfinite(values)):
        raise ValueError("returns must contain only finite values")
    return cast(FloatArray[TShape], values)


def _tail_along_first_axis[TShape: NonScalarShape](
    arr: FloatArray[TShape], window_size: int
) -> FloatArray[TShape]:
    if window_size <= 0:
        raise ValueError("window size must be positive")
    if window_size > arr.shape[0]:
        raise ValueError(
            f"window size {window_size} exceeds {arr.shape[0]} observations"
        )
    return cast(FloatArray[TShape], arr[-window_size:])


def _roll_along_first_axis[TDtype: np.dtype](
    arr: np.ndarray[NonScalarShape, TDtype],
    window_size: int,
) -> np.ndarray[RolledShape, TDtype]:
    """Append a rolling-window axis while preserving all batch axes."""
    if window_size <= 0:
        raise ValueError("window size must be positive")
    if window_size > arr.shape[0]:
        raise ValueError(
            f"window size {window_size} exceeds {arr.shape[0]} observations"
        )
    return cast(
        np.ndarray[RolledShape, TDtype],
        sliding_window_view(arr, window_shape=window_size, axis=0),
    )


def _estimate_volatility_series[TShape: NonScalarShape](
    returns: FloatArray[TShape], spec: var.VolatilitySpec
) -> FloatArray[TShape]:
    """Estimate rolling volatility along time for every batch.

    Sample volatility uses overlapping windows. EWMA is initialized once from
    its warm-up sample and then recurses continuously along axis 0. NumPy's
    shape types cannot express the changed first-axis length precisely.
    """
    match spec:
        case var.SampleVolatilitySpec(lookback_window=lookback_window):
            windows = _roll_along_first_axis(returns, lookback_window)
            volatilities = np.std(windows, axis=-1, ddof=1, dtype=np.float64)

        case var.EwmaVolatilitySpec(
            decay_factor=decay_factor,
            warm_up_window=warm_up_window,
        ):
            if warm_up_window > returns.shape[0]:
                raise ValueError(
                    f"warm-up window {warm_up_window} exceeds "
                    f"{returns.shape[0]} observations"
                )
            current = np.std(
                returns[:warm_up_window],
                axis=0,
                ddof=1,
                dtype=np.float64,
            )
            estimates = [current]
            for timestamp in range(warm_up_window, returns.shape[0]):
                current = np.sqrt(
                    decay_factor * np.square(current)
                    + (1 - decay_factor) * np.square(returns[timestamp])
                )
                estimates.append(current)
            volatilities = np.stack(estimates, axis=0)

        case _:
            assert_never(spec)

    return cast(FloatArray[TShape], np.asarray(volatilities, dtype=np.float64))


def _volatility_start_index(spec: var.VolatilitySpec) -> int:
    match spec:
        case var.SampleVolatilitySpec(lookback_window=lookback_window):
            return lookback_window - 1

        case var.EwmaVolatilitySpec(warm_up_window=warm_up_window):
            return warm_up_window - 1

        case _:
            assert_never(spec)


def _estimate_volatility(returns: ReturnsArray, spec: var.VolatilitySpec) -> BatchArray:
    """Return the latest volatility estimate for every batch."""
    series = _estimate_volatility_series(returns, spec)
    return cast(BatchArray, np.asarray(series[-1], dtype=np.float64))


def _apply_filter[TShape: NonScalarShape](
    returns: FloatArray[TShape],
    filter_spec: var.FilterSpec,
) -> FloatArray[TShape]:
    """Apply filtered historical simulation along the first axis.

    Observations before the estimator's first volatility value are removed.
    The array rank and all batch axes are retained.
    """
    volatilities = _estimate_volatility_series(returns, filter_spec.volatility)
    if np.any(~np.isfinite(volatilities)) or np.any(volatilities <= 0):
        raise ValueError("filter volatility estimates must be finite and positive")

    aligned_returns = returns[_volatility_start_index(filter_spec.volatility) :]
    latest_volatility = volatilities[-1]
    filtered = aligned_returns * latest_volatility / volatilities
    return cast(FloatArray[TShape], np.asarray(filtered, dtype=np.float64))


def _weighted_quantile_first_axis(
    returns: ReturnsArray,
    q: float,
    *,
    decay_factor: float,
    interpolation: var.QuantileInterpolation,
) -> BatchArray:
    """Compute an age-weighted quantile independently for every batch.

    The newest observation has weight 1 and each preceding observation's
    weight is multiplied by ``decay_factor``. Equal weights delegate to NumPy
    so left, right, and linear interpolation match its quantile definitions.
    For decayed weights, interpolation is performed on the normalized weighted
    empirical CDF.
    """
    method: dict[var.QuantileInterpolation, NumpyQuantileMethod] = {
        "left": "lower",
        "right": "higher",
        "linear": "linear",
    }
    if decay_factor == 1:
        quantile = np.quantile(returns, q=q, axis=0, method=method[interpolation])
        return cast(BatchArray, np.asarray(quantile, dtype=np.float64))

    observation_count = returns.shape[0]
    batch_shape = returns.shape[1:]
    flat_returns = returns.reshape(observation_count, -1)

    ages = np.arange(observation_count - 1, -1, -1, dtype=np.float64)
    chronological_weights = np.power(decay_factor, ages)
    weights = np.broadcast_to(chronological_weights[:, None], flat_returns.shape)

    order = np.argsort(flat_returns, axis=0)
    sorted_returns = np.take_along_axis(flat_returns, order, axis=0)
    sorted_weights = np.take_along_axis(weights, order, axis=0)
    cumulative_weights = np.cumsum(sorted_weights, axis=0)
    cumulative_weights /= cumulative_weights[-1]

    if interpolation == "left":
        indices = np.argmax(cumulative_weights >= q, axis=0)
        quantile = sorted_returns[indices, np.arange(flat_returns.shape[1])]
    elif interpolation == "right":
        indices = np.argmax(cumulative_weights > q, axis=0)
        quantile = sorted_returns[indices, np.arange(flat_returns.shape[1])]
    else:
        upper_indices = np.argmax(cumulative_weights >= q, axis=0)
        lower_indices = np.maximum(upper_indices - 1, 0)
        columns = np.arange(flat_returns.shape[1])

        upper_weights = cumulative_weights[upper_indices, columns]
        lower_weights = np.where(
            upper_indices == 0,
            0,
            cumulative_weights[lower_indices, columns],
        )
        upper_returns = sorted_returns[upper_indices, columns]
        lower_returns = np.where(
            upper_indices == 0,
            upper_returns,
            sorted_returns[lower_indices, columns],
        )
        fractions = np.divide(
            q - lower_weights,
            upper_weights - lower_weights,
            out=np.zeros_like(upper_weights),
            where=upper_weights != lower_weights,
        )
        quantile = lower_returns + fractions * (upper_returns - lower_returns)

    return cast(
        BatchArray,
        np.asarray(quantile.reshape(batch_shape), dtype=np.float64),
    )


def _compute_historical_var(
    returns: ReturnsArray,
    spec: var.HistoricalSimulationsVarSpec,
) -> BatchArray:
    sample = _tail_along_first_axis(returns, spec.lookback_window)
    lower_tail_quantile = _weighted_quantile_first_axis(
        sample,
        q=1 - spec.confidence_level,
        decay_factor=spec.decay_factor,
        interpolation=spec.interpolation,
    )
    return cast(BatchArray, np.asarray(-lower_tail_quantile, dtype=np.float64))


def _compute_gaussian_var(
    volatility: BatchArray,
    confidence_level: var.ConfidenceLevel,
) -> BatchArray:
    scale = np.where(volatility == 0, 1, volatility)
    lower_tail = stats.norm.ppf(
        1 - confidence_level,
        loc=0,
        scale=scale,
    )
    result = np.where(volatility == 0, 0, -lower_tail)
    return cast(BatchArray, np.asarray(result, dtype=np.float64))


def _compute_student_t_var(
    volatility: BatchArray,
    confidence_level: var.ConfidenceLevel,
    dof: int,
) -> BatchArray:
    scale = np.where(volatility == 0, 1, volatility)
    lower_tail = stats.t.ppf(
        1 - confidence_level,
        df=dof,
        loc=0,
        scale=scale,
    )
    result = np.where(volatility == 0, 0, -lower_tail)
    return cast(BatchArray, np.asarray(result, dtype=np.float64))


def _compute_parametric_var(
    returns: ReturnsArray,
    spec: var.ParametricVarSpec,
) -> BatchArray:
    sample = _tail_along_first_axis(returns, spec.lookback_window)

    match spec.dist:
        case var.GaussianDistributionSpec(volatility=volatility_spec):
            volatility = _estimate_volatility(sample, volatility_spec)
            return _compute_gaussian_var(volatility, spec.confidence_level)

        case var.StudentTDistributionSpec(
            volatility=volatility_spec,
            dof=dof,
        ):
            volatility = _estimate_volatility(sample, volatility_spec)
            return _compute_student_t_var(volatility, spec.confidence_level, dof)

        case _:
            assert_never(spec.dist)
