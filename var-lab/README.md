# var-lab

Typed, vectorized Value-at-Risk calculations. Return arrays have shape
`(time, *batch)`: every computation acts on the first axis and independently
processes all remaining batch dimensions.

## Verification

Run from this directory:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest
npx --no-install pyright --pythonpath .venv/bin/python src tests
uv build
```
