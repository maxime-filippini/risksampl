#!/usr/bin/env -S uv run

import asyncio

import httpx
import polars as pl
from sqlalchemy import select

from worker.data_loader import _build_ticker_lists
from worker.database import connect
from worker.database import instruments
from worker.database import market_data
from worker.settings import Settings

ROOT_URL = "https://api.marketstack.com/v2"
EOD_URL = f"{ROOT_URL}/eod"

settings = Settings()


with connect() as session:
    insts = session.scalars(select(instruments)).all()
    symbols = [inst.ticker for inst in insts]
    df_insts = pl.DataFrame(
        [
            {
                "id": str(inst.id),
                "ticker": inst.ticker,
            }
            for inst in insts
        ]
    )


batches = _build_ticker_lists(symbols, max_tickers=100)

# Download 10 years of data


async def load_data():
    offset = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            print(f"Processing {offset=}")
            resp = await client.get(
                EOD_URL,
                params={
                    "access_key": settings.MARKETSTACK_API_KEY,
                    "symbols": batches[0],
                    "date_from": "2015-09-01",
                    "date_to": "2021-04-16",
                    "offset": offset,
                    "limit": 1000,
                },
            )

            json = resp.json()
            pagination = json["pagination"]

            df = (
                pl.DataFrame(
                    json["data"],
                    schema={
                        "date": pl.String,
                        "symbol": pl.String,
                        "name": pl.String,
                        "exchange_code": pl.String,
                        "asset_type": pl.String,
                        "price_currency": pl.String,
                        "exchange": pl.String,
                        "open": pl.Float64,
                        "high": pl.Float64,
                        "low": pl.Float64,
                        "close": pl.Float64,
                        "volume": pl.Float64,
                        "adj_open": pl.Float64,
                        "adj_high": pl.Float64,
                        "adj_low": pl.Float64,
                        "adj_close": pl.Float64,
                        "adj_volume": pl.Float64,
                    },
                )
                .drop("name", "exchange_code", "asset_type", "price_currency", "exchange")
                .with_columns(date=pl.col("date").str.to_datetime("%Y-%m-%dT%H:%M:%S+%Z").dt.date())
                .unpivot(index=["date", "symbol"])
                .rename({"variable": "data_type"})
            )

            df_with_ids = (
                df.join(df_insts, left_on="symbol", right_on="ticker")
                .rename(
                    {
                        "id": "instrument_id",
                    }
                )
                .drop("symbol")
            )

            items_to_add = df_with_ids.to_dicts()

            if items_to_add:
                from sqlalchemy.dialects.postgresql import insert

                stmt = insert(market_data).values(items_to_add)
                stmt = stmt.on_conflict_do_nothing(index_elements=["instrument_id", "date", "data_type"])
                session.execute(stmt)
                session.commit()
                print(f"Processed {len(items_to_add)} items")

            offset += 1000

            if len(df) < 1000 or offset > pagination["total"]:
                break


if __name__ == "__main__":
    asyncio.run(load_data())
