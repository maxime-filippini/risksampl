from typing import assert_never, cast

import numpy as np
import numpy.typing as npt
from numpy.lib.stride_tricks import sliding_window_view
from scipy import stats

from var_lab import var

# Convention: Returns are N-dimensional arrays, where the first dimension is
# time. The rest of the dimensions are arbitrary batches. If returns are of
# dimension (T,M,N,Q), then the associated volatility and VaR calculations will
# be arrays of dimensions (M,N,Q).

type FloatArray[TShape: tuple[int, ...]] = np.ndarray[TShape, np.dtype[np.float64]]
type NonScalarShape = tuple[int, *tuple[int, ...]]
type RolledShape = tuple[int, *tuple[int, ...], int]


def compute_var(returns: npt.NDArray[np.float64], spec: var.VarSpec):
    match spec:
        case var.HistoricalSimulationsVarSpec():
            return _compute_historical_var(
                returns=returns,
                confidence_level=spec.confidence_level,
                filter=spec.filter,
            )

        case var.ParametricVarSpec():
            return _compute_parametric_var(returns=returns, spec=spec)

        case _:
            _ = assert_never(spec)


def _roll_along_first_axis[TDtype: np.dtype](
    arr: np.ndarray[NonScalarShape, TDtype],
    window_size: int,
) -> np.ndarray[RolledShape, TDtype]:
    return cast(
        np.ndarray[RolledShape, TDtype],
        sliding_window_view(arr, window_shape=window_size, axis=0),
    )


def _apply_filter[TShape: NonScalarShape](
    returns: FloatArray[TShape],
    filter: var.FilterSpec,
) -> FloatArray[TShape]:
    """Applies a filter to returns.

    While the size of the first dimension may change depending on the lookback
    window needed for volatility estimation, the number of dimensions remain
    unchanged.
    """
    match filter.volatility:
        case var.SampleVolatilitySpec(lookback_window=lookback_window):
            _rolling = _roll_along_first_axis(returns, window_size=lookback_window)

        case var.EwmaVolatilitySpec():
            pass

        case _:
            assert_never(filter.volatility)
    return returns


def _compute_historical_var(
    returns: npt.NDArray[np.float64],
    confidence_level: var.ConfidenceLevel,
    filter: var.FilterSpec | None,
):
    if filter is not None:
        returns = _apply_filter(returns, filter)
    return np.quantile(returns, q=1 - confidence_level)


def _estimate_vol(
    returns: npt.NDArray[np.float64], spec: var.VolatilitySpec
) -> npt.NDArray[np.float64]:
    return np.array([1.1])


def _compute_gaussian_quantile(
    returns: npt.NDArray[np.float64],
    vol_spec: var.VolatilitySpec,
    p: float,
) -> float:
    vols = _estimate_vol(returns=returns, spec=vol_spec)
    _qs = stats.norm.ppf(p, loc=0, scale=vols)
    return 1.1


def _compute_parametric_var(
    returns: npt.NDArray[np.float64],
    spec: var.ParametricVarSpec,
):
    match spec.dist:
        case var.GaussianDistributionSpec(volatility=vol_spec):
            return _compute_gaussian_quantile(
                returns, vol_spec=vol_spec, p=spec.confidence_level
            )

        case var.StudentTDistributionSpec():
            pass

        case _:
            assert_never(spec.dist)
