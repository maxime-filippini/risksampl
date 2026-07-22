import numpy as np
import pytest

from var_lab import (
    apply_filters,
    compute_var,
    compute_vars,
    extract_unique_filters,
    var,
)


def _sample_filter(lookback_window: int = 3) -> var.FilterSpec:
    return var.FilterSpec(
        volatility=var.SampleVolatilitySpec(lookback_window=lookback_window)
    )


def _historical_spec(
    model_id: str,
    *,
    filter_spec: var.FilterSpec | None = None,
    confidence_level: float = 0.75,
) -> var.HistoricalSimulationsVarSpec:
    return var.HistoricalSimulationsVarSpec(
        id=model_id,
        confidence_level=confidence_level,
        lookback_window=3,
        filter=filter_spec,
        interpolation="linear",
        decay_factor=1,
    )


def test_extract_unique_filters_uses_structural_equality_and_stable_order() -> None:
    sample_filter = _sample_filter()
    equivalent_sample_filter = _sample_filter()
    ewma_filter = var.FilterSpec(
        volatility=var.EwmaVolatilitySpec(
            decay_factor=0.94,
            warm_up_window=2,
        )
    )
    specs: list[var.VarSpec] = [
        _historical_spec("sample-a", filter_spec=sample_filter),
        _historical_spec("unfiltered"),
        _historical_spec("sample-b", filter_spec=equivalent_sample_filter),
        _historical_spec("ewma", filter_spec=ewma_filter),
        var.ParametricVarSpec(
            id="parametric",
            confidence_level=0.99,
            lookback_window=3,
            dist=var.GaussianDistributionSpec(
                volatility=var.SampleVolatilitySpec(lookback_window=3)
            ),
        ),
    ]

    filters = extract_unique_filters(specs)

    assert filters == (sample_filter, ewma_filter)


def test_apply_filters_deduplicates_equivalent_filters() -> None:
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
    sample_filter = _sample_filter()

    prepared = apply_filters(returns, (sample_filter, _sample_filter()))

    assert prepared.unfiltered is returns
    assert len(prepared.filtered) == 1
    assert prepared.filtered[0].filter_spec == sample_filter
    assert prepared.filtered[0].returns.shape == (3, 2)


def test_compute_vars_reuses_prepared_filters_and_preserves_model_order() -> None:
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
    shared_filter = _sample_filter()
    specs: list[var.VarSpec] = [
        _historical_spec("filtered-75", filter_spec=shared_filter),
        _historical_spec(
            "filtered-90",
            filter_spec=_sample_filter(),
            confidence_level=0.90,
        ),
        _historical_spec("unfiltered"),
    ]
    prepared = apply_filters(returns, extract_unique_filters(specs))

    results = compute_vars(prepared, specs)

    assert list(results) == ["filtered-75", "filtered-90", "unfiltered"]
    assert len(prepared.filtered) == 1
    for spec in specs:
        np.testing.assert_allclose(results[spec.id], compute_var(returns, spec))


def test_compute_vars_requires_every_referenced_filter_to_be_prepared() -> None:
    returns = np.array([-0.04, -0.02, 0.01, -0.03], dtype=np.float64)
    spec = _historical_spec("filtered", filter_spec=_sample_filter())
    prepared = apply_filters(returns, ())

    with pytest.raises(ValueError, match="has not been prepared"):
        compute_vars(prepared, [spec])


def test_compute_vars_requires_unique_model_ids() -> None:
    returns = np.array([-0.04, -0.02, 0.01, -0.03], dtype=np.float64)
    specs = [
        _historical_spec("duplicate"),
        _historical_spec("duplicate", confidence_level=0.90),
    ]
    prepared = apply_filters(returns, ())

    with pytest.raises(ValueError, match="model ids must be unique"):
        compute_vars(prepared, specs)
