import datetime
import math
from typing import cast

import httpx
import polars as pl
from scipy import stats
from sqlalchemy.orm import Session

from worker.database import connect
from worker.database import market_data
from worker.database import measurements
from worker.database import ptf_comp
from worker.readers import get_adjusted_close_up_to_date
from worker.readers import get_all_dates
from worker.readers import get_all_portfolio_ids
from worker.readers import get_investments_over_time_range
from worker.readers import get_latest_compositions
from worker.readers import get_latest_market_data_dates
from worker.readers import get_portfolio_compositions
from worker.readers import get_unique_instruments
from worker.settings import settings
from worker.utils import insert_list_of_dicts

# Constants
ROOT_URL = "https://api.marketstack.com/v2"
EOD_URL = f"{ROOT_URL}/eod"


def _update_dates_table(session: Session, current_date: datetime.date):
    df_dates = (
        get_all_dates(session)
        .pipe(lambda df: pl.concat([df, pl.DataFrame([{"date": current_date, "type": "history"}])]))
        .with_columns(type=pl.lit("history"))
        .unique()
        .with_columns(type=pl.when(pl.col("date") == current_date).then(pl.lit("current")).otherwise(pl.col("type")))
        .sort("date", descending=True)
    )

    df_dates.write_database("dates", session, if_table_exists="replace")


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


def _load_market_data(
    session, batches: list[str], min_date: datetime.date, max_date: datetime.date, df_insts: pl.DataFrame
):
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
                    "date_from": min_date.strftime("%Y-%m-%d"),
                    "date_to": max_date.strftime("%Y-%m-%d"),
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
                insert_list_of_dicts(items_to_add, market_data, session=session)

            offset += LIMIT

            if len(df) < LIMIT or offset > pagination["total"]:
                break


def _single_measure_loop(
    df_positions: pl.DataFrame, df_market_data: pl.DataFrame, ptf_id: str, calc_date: datetime.date
):
    df_ = (
        df_positions.filter(pl.col("portfolio_id").eq(ptf_id))
        .filter(pl.col("date").eq(calc_date))
        .drop("portfolio_id", "date")
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
            "portfolio_value": value,
            "hist_var": hist_var,
            "ewma_var": ewma_var,
            "param_var": param_var,
            "ex_ante_volatility": annualized_vol,
        }
    )


def daily_run(ref_date: datetime.date):
    with connect() as session:
        # We start by loading the database tables we will need
        df_insts = get_unique_instruments(session)
        df_latest_comps = get_latest_compositions(session)
        df_market_data_dates = get_latest_market_data_dates(session)
        df_ptfs = get_all_portfolio_ids(session)

        # We determine the last investment date, i.e. our starting point
        # TODO: Determine what happens if we have a portfolio that doesn't have a single record in the investments table
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

        # This is the oldest of the latest composition dates for all portfolios
        min_date = cast(datetime.date, df_latest_date["date"].min())

        # Only load investments within the time range where they will be needed
        # NOTE: This is rough, and we should technically be more granular, i.e. use dates on a per-investment basis
        df_investments = get_investments_over_time_range(session, date_start=min_date, date_end=ref_date)

        tickers = df_insts["ticker"].to_list()

    with connect() as session:
        # Loading market data
        batches = _build_ticker_batches(tickers, max_tickers=1000)
        date_from = cast(datetime.date, df_market_data_dates["max_date"].min())

        if date_from >= ref_date:
            print("Not adding market data.")
        else:
            # For now let's assume we only have one batch of tickers
            assert len(batches) == 1
            _load_market_data(session, batches, min_date=date_from, max_date=ref_date, df_insts=df_insts)

        # Once data has been loaded and written to the database, we reload all
        # the data we need. For now, we only need adjusted close prices
        df_market_data = (
            get_adjusted_close_up_to_date(session, max_date=ref_date)
            .group_by("instrument_id")
            .map_groups(lambda df: (df.sort("date").with_columns(price=pl.col("price").forward_fill())))
        )

        # Here, our calculation dates will be all dates from our latest composition to now
        calculation_dates = pl.date_range(min_date, ref_date, eager=True)

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
                    {"portfolio_id": str(portfolio_id), "instrument_id": str(instrument_id), "date": calculation_dates},
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
            insert_list_of_dicts(items_to_add, table=ptf_comp, session=session)
        else:
            print("No compositions to add!")

        df_comps = get_portfolio_compositions(session, date=ref_date)

    combinations_for_measures = df_comps.select("portfolio_id", "date").unique()

    dfs = []
    for i, (ptf_id, calc_date) in enumerate(combinations_for_measures.rows()):
        print(f"{i} / {len(combinations_for_measures)}")
        dfs.append(_single_measure_loop(df_comps, df_market_data, ptf_id, calc_date))

    df_measures = (
        pl.concat(dfs).unpivot(index=["portfolio_id", "calc_date"]).rename({"variable": "measure", "calc_date": "date"})
    )

    items_to_add = df_measures.to_dicts()

    with connect() as session:
        if items_to_add:
            insert_list_of_dicts(items=items_to_add, table=measurements, session=session)

        # Finally, update the dates table
        _update_dates_table(session, current_date=ref_date)
