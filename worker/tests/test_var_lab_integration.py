import numpy as np

from var_lab import compute_var
from var_lab import var


def test_worker_can_calculate_var_through_workspace_library() -> None:
    returns = np.array([-0.04, -0.02, 0.01, -0.03], dtype=np.float64)
    model = var.HistoricalSimulationsVarSpec(
        id="historical-99",
        confidence_level=0.99,
        lookback_window=4,
        interpolation="left",
        decay_factor=1,
    )

    result = compute_var(returns, model)

    assert result.shape == ()
    assert result.item() == 0.04
