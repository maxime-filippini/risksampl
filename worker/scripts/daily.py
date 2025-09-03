#!/usr/bin/env -S uv run

"""Daily operation."""

import argparse
import datetime
import math
from typing import cast

import httpx
import polars as pl
from scipy import stats

from worker.database import MarketData
from worker.database import Measure
from worker.database import PortfolioComposition
from worker.database import connect
from worker.settings import settings
from worker.utils import insert_list_of_dicts

# Constants
ROOT_URL = "https://api.marketstack.com/v2"
EOD_URL = f"{ROOT_URL}/eod"


# Before we do anything, we load data from our database
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("date")
    args = parser.parse_args()

    args.date = datetime.datetime.strptime(args.date, "%Y%m%d").date()

    with connect() as session:
        df_insts = pl.read_database("SELECT DISTINCT id, ticker FROM instruments", session)

        df_latest_comps = pl.read_database(
            """
            SELECT 
                ptf_comp.portfolio_id::TEXT,
                ptf_comp.instrument_id::TEXT,
                ptf_comp.quantity,
                ptf_comp.date
            FROM ptf_comp
            LEFT JOIN (
                SELECT portfolio_id, MAX(date) AS max_date
                FROM ptf_comp
                GROUP BY portfolio_id
            ) AS T
            ON ptf_comp.portfolio_id = T.portfolio_id
            WHERE ptf_comp.date = T.max_date
            """,
            session,
        )

        df_market_data_dates = pl.read_database(
            "SELECT instrument_id, MAX(date) AS max_date FROM market_data GROUP BY instrument_id", session
        )

        df_ptfs = pl.read_database("SELECT id::TEXT FROM portfolios", session)

        df_latest_date = (
            pl.concat(
                [
                    df_ptfs.select(portfolio_id=pl.col("id"), date=pl.lit(datetime.date(1900, 1, 1))),
                    df_latest_comps.select("portfolio_id", "date").unique(),
                ]
            )
            .group_by("portfolio_id")
            .agg(date=pl.col("date").max())
        )

        min_date = cast(datetime.date, df_latest_date["date"].min())

        df_investments = pl.read_database(
            """
            SELECT 
                portfolio_id::TEXT as portfolio_id,
                instrument_id::TEXT as instrument_id,
                date,
                quantity
            FROM investments
            WHERE 
                1=1
                AND date <= :max_date
                AND date >= :min_date
            """,
            session,
            execute_options={"params": {"max_date": args.date, "min_date": min_date}},
            schema_overrides={
                "portfolio_id": pl.String,
                "instrument_id": pl.String,
                "date": pl.Date,
                "quantity": pl.Decimal(),
            },
        )

        tickers = df_insts["ticker"].to_list()

    # Then, we can define the batches for loading market data

    def _build_ticker_batches(tickers: list[str], max_tickers: int) -> list[str]:
        out = []

        while True:
            batch = tickers[:max_tickers]
            out.append(",".join(batch))

            n = len(batch)

            if n < max_tickers:
                break

            tickers = tickers[n:]

        return out

    batches = _build_ticker_batches(tickers, max_tickers=1000)

    # First, we need to get the necessary market data
    # This means first getting the latest market data for all instruments, and then
    # getting the data from the oldest day. Admittedly this is a little bit
    # wasteful, but simpler than batching batches...

    with connect() as session:
        date_from = cast(datetime.date, df_market_data_dates["max_date"].min())

    # Now we can call our endpoints. For now let's assume we only have one batch of
    # tickers

    def _load_market_data(session, batches: list[str]):
        assert len(batches) == 1

        # We start with a synchronous http client so we dont have to wrap it in an async
        # functions and deal with an event loop.

        batch = batches[0]
        offset = 0
        LIMIT = 1000

        with httpx.Client(timeout=30.0) as client:
            while True:
                print("Loading data from Marketstack...")

                resp = client.get(
                    EOD_URL,
                    params={
                        "access_key": settings.MARKETSTACK_API_KEY,
                        "symbols": batch,
                        "date_from": date_from.strftime("%Y-%m-%d"),
                        "date_to": args.date.strftime("%Y-%m-%d"),
                        "offset": offset,
                        "limit": LIMIT,
                    },
                )

                json = resp.json()
                print(json)
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

                print(f"About to add {len(df_with_ids)} to the database...")

                items_to_add = df_with_ids.to_dicts()

                if items_to_add:
                    insert_list_of_dicts(items_to_add, MarketData, session=session)

                offset += 1000

                if len(df) < 1000 or offset > pagination["total"]:
                    break

    if date_from >= args.date:
        print("Not adding market data.")
    else:
        with connect() as session:
            _load_market_data(session, batches)

    # Ok - Data loading works, now we need to compute the portfolio compositions
    # based on latest portfolio composition

    with connect() as session:
        df_market_data = (
            pl.read_database(
                """
                SELECT
                    date,
                    instrument_id::TEXT as instrument_id,
                    value AS price
                FROM market_data
                WHERE date <= :date
                AND data_type = 'adj_close'""",
                session,
                execute_options={"params": {"date": args.date}},
            )
            .group_by("instrument_id")
            .map_groups(lambda df: (df.sort("date").with_columns(price=pl.col("price").forward_fill())))
        )

        s_cal_dates = pl.date_range(min_date, args.date, eager=True)

        pairs = pl.concat(
            [
                df_investments.select("portfolio_id", "instrument_id"),
                df_latest_comps.select("portfolio_id", "instrument_id"),
            ],
            how="vertical_relaxed",
        ).unique()

        dfs: list[pl.DataFrame] = []

        # For each pair, compute the new quantities
        for portfolio_id, instrument_id in pairs.iter_rows():
            df_comp = df_latest_comps.filter(
                pl.col("portfolio_id").eq(portfolio_id).and_(pl.col("instrument_id").eq(instrument_id))
            )

            df = (
                pl.DataFrame(
                    {"portfolio_id": str(portfolio_id), "instrument_id": str(instrument_id), "date": s_cal_dates},
                    schema={"portfolio_id": pl.String, "instrument_id": pl.String, "date": pl.Date},
                )
                .join(
                    pl.concat([df_investments, df_comp], how="diagonal"),
                    on=["portfolio_id", "instrument_id", "date"],
                    how="left",
                )
                .sort("date")
                .with_columns(quantity=pl.col("quantity").replace(None, 0).cum_sum())
                # Here, for the given instrument/portfolio pair, we remove dates before the first trade
                .filter((pl.col("quantity") != 0).cum_sum() > 0)
                # Remove the rows for the latest comp
                .filter(pl.col("date") > df_comp["date"].max())
            )

            dfs.append(df)

        df_new_comps = (
            pl.concat(dfs)
            .filter(pl.col("date").dt.is_business_day())
            .group_by("portfolio_id", "instrument_id", "date")
            .agg(quantity=pl.col("quantity").sum())
        )

        items_to_add = df_new_comps.to_dicts()

        if items_to_add:
            insert_list_of_dicts(items_to_add, table=PortfolioComposition, session=session)
        else:
            print("No compositions to add!")

        df_comps = pl.read_database(
            "SELECT portfolio_id::TEXT, instrument_id::TEXT, date, quantity FROM ptf_comp WHERE date = :date",
            session,
            execute_options={"params": {"date": args.date}},
        )

    def _single_measure_loop(
        df_positions: pl.DataFrame, df_market_data: pl.DataFrame, ptf_id: str, calc_date: datetime.date
    ):
        df_ = (df_positions.filter(pl.col("portfolio_id").eq(ptf_id)).filter(pl.col("date").eq(calc_date))).drop(
            "portfolio_id", "date"
        )

        df_prices = df_.select("instrument_id").join(df_market_data, how="right", on=["instrument_id"])

        df_ = (
            df_.join(df_prices, on=["instrument_id"])
            .filter(pl.col("date") <= calc_date)
            .with_columns(value=pl.col("quantity") * pl.col("price"))
            .group_by("date")
            .agg(value=pl.col("value").sum())
            .sort("date")
            .with_columns(returns=pl.col("value").pct_change())
        )

        rets = df_["returns"]
        value = df_["value"][-1]

        assert len(rets) > 60

        vol = rets.tail(60).std()

        assert isinstance(vol, float)

        annualized_vol = vol * math.sqrt(250)
        longer_vol = rets.tail(250).std()

        hist_var = rets.tail(500).quantile(1 - 0.99)
        assert hist_var is not None

        hist_var = -hist_var

        ewma_backcast_window = 60
        ewma_backcast_vol = rets[:ewma_backcast_window].std()
        curr = ewma_backcast_vol
        ewma_vols = [curr]

        for ret in rets[ewma_backcast_window:]:
            assert isinstance(curr, float)
            curr = math.sqrt(0.94 * curr**2 + 0.06 * ret**2)
            ewma_vols.append(curr)

        ewma_vol = ewma_vols[-1]
        assert isinstance(ewma_vol, float)
        assert isinstance(longer_vol, float)

        ewma_var = float(-ewma_vol * stats.norm.ppf(1 - 0.99))
        param_var = float(-longer_vol * stats.norm.ppf(1 - 0.99))

        # Put it all together
        return pl.DataFrame(
            {
                "portfolio_id": ptf_id,
                "calc_date": calc_date,
                "ptf_value": value,
                "hist_var": hist_var,
                "ewma_var": ewma_var,
                "param_var": param_var,
                "ex_ante_vol": annualized_vol,
            }
        )

    combinations_for_measures = df_comps.select("portfolio_id", "date").unique()

    dfs = []
    for i, (ptf_id, calc_date) in enumerate(combinations_for_measures.rows()):
        print(f"{i} / {len(combinations_for_measures)}")
        dfs.append(_single_measure_loop(df_comps, df_market_data, ptf_id, calc_date))

    df_measures = (
        pl.concat(dfs).unpivot(index=["portfolio_id", "calc_date"]).rename({"variable": "measure", "calc_date": "date"})
    )

    items_to_add = df_measures.to_dicts()

    if items_to_add:
        insert_list_of_dicts(items=items_to_add, table=Measure, session=session)

    # Finally, update the date

    with connect() as session:
        df_dates = (
            pl.read_database("SELECT * FROM dates", session)
            .pipe(lambda df: pl.concat([df, pl.DataFrame([{"date": args.date, "type": "history"}])]))
            .with_columns(type=pl.lit("history"))
            .unique()
            .with_columns(type=pl.when(pl.col("date") == args.date).then(pl.lit("current")).otherwise(pl.col("type")))
            .sort("date", descending=True)
        )

        print(df_dates)
        df_dates.write_database("dates", session, if_table_exists="replace")

        session.commit()


if __name__ == "__main__":
    raise SystemExit(main())
