from collections.abc import Sequence

import polars as pl

from worker.database import MarketData
from worker.database import connect


def main(argv: Sequence[str] | None = None) -> int:
    df = pl.read_csv("/tmp/data/market_data.csv")
    items_to_add = df.to_dicts()

    print(len(df))

    with connect() as session:
        if items_to_add:
            from sqlalchemy.dialects.postgresql import insert

            stmt = insert(MarketData).values(items_to_add)
            stmt = stmt.on_conflict_do_nothing(index_elements=["instrument_id", "date", "data_type"])
            session.execute(stmt)
            session.commit()
            print(f"Processed {len(items_to_add)} items")

        session.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
