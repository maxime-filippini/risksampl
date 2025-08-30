from collections.abc import Sequence

import polars as pl
from sqlalchemy import select

from worker.database import Instrument
from worker.database import MarketData
from worker.database import connect


def main(argv: Sequence[str] | None = None) -> int:
    df = pl.read_csv("/tmp/data/market_data_clean.csv")

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

            chunk_size = 1000
            total_inserted = 0
            
            for i in range(0, len(items_to_add), chunk_size):
                chunk = items_to_add[i:i+chunk_size]
                
                try:
                    stmt = insert(MarketData).values(chunk)
                    stmt = stmt.on_conflict_do_nothing()
                    result = session.execute(stmt)
                    session.commit()
                    
                    chunk_inserted = result.rowcount
                    total_inserted += chunk_inserted
                    
                    print(f"Chunk {i//chunk_size + 1}: Inserted {chunk_inserted}/{len(chunk)} rows (Total: {total_inserted})")
                    
                except Exception as e:
                    print(f"Error inserting chunk {i//chunk_size + 1}: {e}")
                    session.rollback()
                    
            print(f"Final total: {total_inserted} rows inserted successfully")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
