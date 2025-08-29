from collections.abc import Sequence

import polars as pl

from worker.database import MarketData
from worker.database import connect


def main(argv: Sequence[str] | None = None) -> int:
    df = pl.read_csv("/tmp/data/market_data.csv")
    items_to_add = df.to_dicts()

    print(f"DataFrame has {len(df)} rows")
    print("Sample data:")
    print(df.head())
    print(f"Columns: {df.columns}")
    print(f"Schema: {df.schema}")

    with connect() as session:
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
