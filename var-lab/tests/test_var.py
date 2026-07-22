import pytest
from pydantic import ValidationError

from var_lab import var


def test_windows_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        var.HistoricalSimulationsVarSpec(
            id="historical",
            confidence_level=0.99,
            lookback_window=0,
            interpolation="left",
            decay_factor=1,
        )


def test_ewma_warm_up_must_contain_multiple_observations() -> None:
    with pytest.raises(ValidationError):
        var.EwmaVolatilitySpec(
            warm_up_window=1,
            decay_factor=0.94,
        )


def test_student_t_degrees_of_freedom_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        var.StudentTDistributionSpec(
            volatility=var.SampleVolatilitySpec(
                lookback_window=20,
            ),
            dof=0,
        )
