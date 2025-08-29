from collections.abc import Sequence

import polars as pl
from sqlalchemy import select

from worker.database import Instrument
from worker.database import MarketData
from worker.database import connect


def main(argv: Sequence[str] | None = None) -> int:
    df = pl.read_csv("/tmp/data/market_data.csv")

    with connect() as session:
        insts = session.scalars(select(Instrument)).all()
        df_insts = pl.DataFrame(
            [
                {
                    "id": str(inst.id),
                    "ticker": inst.ticker,
                }
                for inst in insts
            ]
        )

        df_data = df.join(df_insts, left_on="ticker", right_on="ticker").drop("ticker").rename({"id": "instrument_id"})

        items_to_add = df_data.to_dicts()

        print(f"DataFrame has {len(df_data)} rows")
        print("Sample data:")
        print(df_data.head())
        print(f"Columns: {df_data.columns}")
        print(f"Schema: {df_data.schema}")

        if items_to_add:
            from sqlalchemy.dialects.postgresql import insert

            try:
                stmt = insert(MarketData).values(items_to_add)
                stmt = stmt.on_conflict_do_nothing()
                result = session.execute(stmt)
                session.commit()
                print(f"Successfully inserted {result.rowcount} rows")
            except Exception as e:
                print(f"Error inserting data: {e}")
                session.rollback()
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
