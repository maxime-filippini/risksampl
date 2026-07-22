import numpy as np
import pytest
from scipy import stats

from var_lab import var
from var_lab.compute import (
    _apply_filter,
    _estimate_volatility_series,
    _roll_along_first_axis,
    _weighted_quantile_first_axis,
    compute_var,
)


def _sample_volatility(lookback_window: int) -> var.SampleVolatilitySpec:
    return var.SampleVolatilitySpec(
        kind="sample-volatility",
        lookback_window=lookback_window,
    )


def test_roll_along_first_axis_preserves_batches_and_appends_window() -> None:
    values = np.arange(20, dtype=np.float64).reshape(5, 2, 2)

    rolled = _roll_along_first_axis(values, window_size=3)

    assert rolled.shape == (3, 2, 2, 3)
    np.testing.assert_array_equal(rolled[0, 1, 0], values[:3, 1, 0])
    np.testing.assert_array_equal(rolled[-1, 0, 1], values[-3:, 0, 1])


def test_sample_volatility_is_rolling_over_first_axis() -> None:
    returns = np.array(
        [
            [-0.04, 0.01],
            [-0.02, -0.03],
            [0.01, 0.02],
            [-0.03, 0.04],
            [0.05, -0.01],
        ],
        dtype=np.float64,
    )

    actual = _estimate_volatility_series(returns, _sample_volatility(3))
    expected = np.stack(
        [np.std(returns[offset : offset + 3], axis=0, ddof=1) for offset in range(3)]
    )

    assert actual.shape == (3, 2)
    np.testing.assert_allclose(actual, expected)


def test_ewma_volatility_is_vectorized_across_batches() -> None:
    returns = np.array(
        [
            [-0.04, 0.01],
            [-0.02, -0.03],
            [0.01, 0.02],
            [-0.03, 0.04],
            [0.05, -0.01],
        ],
        dtype=np.float64,
    )
    spec = var.EwmaVolatilitySpec(
        kind="ewma-volatility",
        lookback_window=4,
        warm_up_window=2,
        decay_factor=0.5,
    )

    actual = _estimate_volatility_series(returns, spec)
    expected = []
    for offset in range(2):
        window = returns[offset : offset + 4]
        volatility = np.std(window[:2], axis=0, ddof=1)
        for observation in window[2:]:
            volatility = np.sqrt(0.5 * volatility**2 + 0.5 * observation**2)
        expected.append(volatility)

    assert actual.shape == (2, 2)
    np.testing.assert_allclose(actual, np.stack(expected))


def test_filter_scales_aligned_returns_by_latest_volatility() -> None:
    returns = np.array(
        [
            [-0.04, 0.01],
            [-0.02, -0.03],
            [0.01, 0.02],
            [-0.03, 0.04],
            [0.05, -0.01],
        ],
        dtype=np.float64,
    )
    filter_spec = var.FilterSpec(volatility=_sample_volatility(3))
    rolling_volatility = np.stack(
        [np.std(returns[offset : offset + 3], axis=0, ddof=1) for offset in range(3)]
    )

    actual = _apply_filter(returns, filter_spec)
    expected = returns[2:] * rolling_volatility[-1] / rolling_volatility

    assert actual.shape == (3, 2)
    np.testing.assert_allclose(actual, expected)


def test_historical_var_filters_before_applying_model_lookback() -> None:
    returns = np.array(
        [-0.04, -0.02, 0.01, -0.03, 0.05, -0.01],
        dtype=np.float64,
    )
    volatility = np.array(
        [np.std(returns[offset : offset + 3], ddof=1) for offset in range(4)]
    )
    filtered_returns = returns[2:] * volatility[-1] / volatility
    expected = -np.quantile(filtered_returns[-2:], 0.25, method="linear")
    spec = var.HistoricalSimulationsVarSpec(
        id="filtered-historical",
        kind="historical",
        confidence_level=0.75,
        lookback_window=2,
        filter=var.FilterSpec(volatility=_sample_volatility(3)),
        interpolation="linear",
        decay_factor=1,
    )

    actual = compute_var(returns, spec)

    assert actual.shape == ()
    np.testing.assert_allclose(actual, expected)


def test_historical_var_removes_time_axis_for_all_batches() -> None:
    returns = np.array(
        [
            [-0.05, -0.10],
            [-0.01, -0.02],
            [0.02, 0.01],
            [-0.03, 0.00],
            [0.01, 0.03],
        ],
        dtype=np.float64,
    )
    spec = var.HistoricalSimulationsVarSpec(
        id="historical",
        kind="historical",
        confidence_level=0.75,
        lookback_window=3,
        interpolation="linear",
        decay_factor=1,
    )

    actual = compute_var(returns, spec)
    expected = -np.quantile(returns[-3:], 0.25, axis=0, method="linear")

    assert actual.shape == (2,)
    np.testing.assert_allclose(actual, expected)


def test_compute_var_supports_multiple_batch_dimensions() -> None:
    base_returns = np.array([-0.05, -0.01, 0.02, -0.03, 0.01], dtype=np.float64)
    returns = np.stack(
        [base_returns, base_returns * 0.5, base_returns * 1.5, base_returns + 0.01],
        axis=1,
    ).reshape(5, 2, 2)
    spec = var.HistoricalSimulationsVarSpec(
        id="historical-batches",
        kind="historical",
        confidence_level=0.75,
        lookback_window=4,
        interpolation="linear",
        decay_factor=1,
    )

    actual = compute_var(returns, spec)
    expected = -np.quantile(returns[-4:], 0.25, axis=0, method="linear")

    assert actual.shape == (2, 2)
    np.testing.assert_allclose(actual, expected)


def test_decay_factor_weights_recent_observations_more_heavily() -> None:
    returns = np.array([-0.10, -0.05, 0.02], dtype=np.float64)

    actual = _weighted_quantile_first_axis(
        returns,
        q=0.25,
        decay_factor=0.5,
        interpolation="left",
    )

    assert actual.shape == ()
    assert actual == pytest.approx(-0.05)


@pytest.mark.parametrize("distribution", ["gaussian", "student-t"])
def test_parametric_var_uses_latest_volatility_for_each_batch(
    distribution: str,
) -> None:
    returns = np.array(
        [
            [-0.04, 0.01],
            [-0.02, -0.03],
            [0.01, 0.02],
            [-0.03, 0.04],
            [0.05, -0.01],
        ],
        dtype=np.float64,
    )
    volatility_spec = _sample_volatility(3)
    if distribution == "gaussian":
        distribution_spec: var.DistributionSpec = var.GaussianDistributionSpec(
            kind="gaussian",
            volatility=volatility_spec,
        )
    else:
        distribution_spec = var.StudentTDistributionSpec(
            kind="t",
            volatility=volatility_spec,
            dof=5,
        )
    spec = var.ParametricVarSpec(
        id=distribution,
        kind="parametric",
        confidence_level=0.99,
        lookback_window=5,
        dist=distribution_spec,
    )
    volatility = np.std(returns[-3:], axis=0, ddof=1)
    if distribution == "gaussian":
        expected = -stats.norm.ppf(0.01, loc=0, scale=volatility)
    else:
        expected = -stats.t.ppf(0.01, df=5, loc=0, scale=volatility)

    actual = compute_var(returns, spec)

    assert actual.shape == (2,)
    np.testing.assert_allclose(actual, expected)


def test_compute_var_rejects_non_finite_returns() -> None:
    returns = np.array([-0.01, np.nan, 0.02], dtype=np.float64)
    spec = var.HistoricalSimulationsVarSpec(
        id="historical",
        kind="historical",
        confidence_level=0.99,
        lookback_window=3,
        interpolation="left",
        decay_factor=1,
    )

    with pytest.raises(ValueError, match="finite"):
        compute_var(returns, spec)


def test_compute_var_rejects_insufficient_lookback() -> None:
    returns = np.array([-0.01, 0.02], dtype=np.float64)
    spec = var.HistoricalSimulationsVarSpec(
        id="historical",
        kind="historical",
        confidence_level=0.99,
        lookback_window=3,
        interpolation="left",
        decay_factor=1,
    )

    with pytest.raises(ValueError, match="exceeds 2 observations"):
        compute_var(returns, spec)
