# var-lab

Typed, vectorized Value-at-Risk calculations. Return arrays have shape
`(time, *batch)`: every computation acts on the first axis and independently
processes all remaining batch dimensions.

## Reusing filters across models

For the common end-to-end path, every structurally unique filter is prepared
once automatically:

```python
from var_lab import compute_vars

vars_by_model_id = compute_vars(returns, specs)
```

To run filtering and VaR computation as separate steps:

```python
from var_lab import (
    apply_filters,
    compute_vars_from_prepared_returns,
    extract_unique_filters,
)

filters = extract_unique_filters(specs)
prepared_returns = apply_filters(returns, filters)
vars_by_model_id = compute_vars_from_prepared_returns(prepared_returns, specs)
```

`compute_var(returns, spec)` remains available as a convenience for a single
model.

## Verification

Run from this directory:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest
npx --no-install pyright --pythonpath .venv/bin/python src tests
uv build
```
