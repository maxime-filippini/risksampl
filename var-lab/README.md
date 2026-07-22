# var-lab

Typed, vectorized Value-at-Risk calculations. Return arrays have shape
`(time, *batch)`: every computation acts on the first axis and independently
processes all remaining batch dimensions.

## Reusing filters across models

Prepare every structurally unique filter once, then run all models against the
same prepared return batches:

```python
from var_lab import apply_filters, compute_vars, extract_unique_filters

filters = extract_unique_filters(specs)
prepared_returns = apply_filters(returns, filters)
vars_by_model_id = compute_vars(prepared_returns, specs)
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
