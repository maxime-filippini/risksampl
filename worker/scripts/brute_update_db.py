#!/usr/bin/env -S uv run

# NOTE: Right now this script kind of expects tables to be cleaned so the relationships are honored.

import pathlib
from collections.abc import Sequence

import polars as pl

from worker.database import Base
from worker.database import Instrument
from worker.database import Investment
from worker.database import Measure
from worker.database import Portfolio
from worker.database import PortfolioComposition
from worker.database import PortfolioValue
from worker.database import connect
from worker.utils import insert_list_of_dicts

DB_TABLES_PATH = pathlib.Path("/tmp/data/db")

TABLE_MAP = {
    "instruments": Instrument,
    "portfolios": Portfolio,
    "measures": Measure,
    "ptf_comp": PortfolioComposition,
    "ptf_values": PortfolioValue,
    "investments": Investment,
}


def load_data(root_path: pathlib.Path):
    out = {}
    for file in root_path.glob("*.csv"):
        table_name = file.name.removesuffix(".csv")
        df = pl.read_csv(file)
        out[table_name] = df

    return out


def _write_data(session, df: pl.DataFrame, table_name: str, table: type[Base]):
    if len(df) < 50:
        print(f"Dataframe for {table_name} had less than 50 rows. Skipped.")
        return

    items = df.to_dicts()
    insert_list_of_dicts(items, table=table, session=session)


def main(argv: Sequence[str] | None = None) -> int:
    with connect() as session:
        dfs = load_data(DB_TABLES_PATH)

        _write_data(session, dfs["instruments"], "instruments", table=TABLE_MAP["instruments"])
        _write_data(session, dfs["portfolios"], "portfolios", table=TABLE_MAP["portfolios"])
        _write_data(session, dfs["investments"], "investments", table=TABLE_MAP["investments"])
        _write_data(session, dfs["market_data"], "market_data", table=TABLE_MAP["market_data"])
        _write_data(session, dfs["ptf_comp"], "ptf_comp", table=TABLE_MAP["ptf_comp"])
        _write_data(session, dfs["ptf_values"], "ptf_values", table=TABLE_MAP["ptf_values"])
        _write_data(session, dfs["measures"], "measures", table=TABLE_MAP["measures"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
