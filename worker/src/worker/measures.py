"""Functions and classes for computing measures on portfolios."""

import datetime

import polars as pl

from worker.pl_utils import validate

POSITIONS_SCHEMA = {"portfolio_id": pl.String, "instrument_id": pl.String, "quantity": pl.Decimal, "date": pl.Date}
MARKET_DATA_SCHEMA = {"instrument_id": pl.String, "date": pl.Date, "type": pl.String, "value": pl.Float64}


def compute_measures_for_single_portfolio(
    df_positions: pl.DataFrame, df_market_data: pl.DataFrame, calc_date: datetime.date, portfolio_id: str
):
    validate(df_positions, schema=POSITIONS_SCHEMA)
    validate(df_market_data, schema=MARKET_DATA_SCHEMA)

    df_ = (
        df_positions.filter(pl.col("portfolio_id").eq(portfolio_id))
        .filter(pl.col("date").eq(calc_date))
        .drop("portfolio_id", "date")
    )

    df_prices = df_.select("instrument_id").join(df_market_data, how="right", on=["instrument_id"])
