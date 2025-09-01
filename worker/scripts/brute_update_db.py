#!/usr/bin/env -S uv run

import pathlib
from collections.abc import Sequence

import polars as pl

from worker.database import connect

DB_TABLES_PATH = pathlib.Path("/tmp/data/db")


def main(argv: Sequence[str] | None = None) -> int:
    with connect() as session:
        for file in DB_TABLES_PATH.glob("*.csv"):
            table_name = file.name.removesuffix(".csv")
            df = pl.read_csv(file)

            # Sanity check
            if len(df) < 50:
                print(f"{file.name} had less than 50 rows. Skipped.")
                continue

            df.write_database(table_name, session, if_table_exists="replace")

            print(f"Replaced {table_name} with {len(df)} rows.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
