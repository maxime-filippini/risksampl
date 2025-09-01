#!/usr/bin/env -S uv run

import pathlib
from collections.abc import Sequence

import polars as pl

from worker.database import connect

DB_TABLES_PATH = pathlib.Path("/tmp/data/db")


def load_data(root_path: pathlib.Path):
    out = {}
    for file in root_path.glob("*.csv"):
        table_name = file.name.removesuffix(".csv")
        df = pl.read_csv(file)
        out[table_name] = df

    return out


def _write_data(session, df: pl.DataFrame, table_name: str):
    if len(df) < 50:
        print(f"Dataframe for {table_name} had less than 50 rows. Skipped.")
        return

    df.write_database(table_name, session)


def main(argv: Sequence[str] | None = None) -> int:
    with connect() as session:
        dfs = load_data(DB_TABLES_PATH)

        _write_data(session, dfs["instruments"], "instruments")
        _write_data(session, dfs["portfolios"], "portfolios")
        _write_data(session, dfs["investments"], "investments")
        _write_data(session, dfs["market_data"], "market_data")
        _write_data(session, dfs["ptf_comp"], "ptf_comp")
        _write_data(session, dfs["ptf_values"], "ptf_values")
        _write_data(session, dfs["measures"], "measures")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
