import polars as pl

from worker.pl_utils import TypeMismatch
from worker.pl_utils import lazy_validate


def test_simple():
    df = pl.DataFrame({"a": [1, 2, 3]})
    assert lazy_validate(df=df, schema={"a": pl.Int64})


def test_not_ok():
    df = pl.DataFrame({"a": [1, 2, 3]})
    errors = lazy_validate(df=df, schema={"a": pl.Float64})

    assert not errors.missing_columns
    assert errors.mismatched_types == {"a": TypeMismatch(expected=pl.Float64, got=pl.Int64)}
