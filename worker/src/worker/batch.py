"""Batch writing into DB."""

import datetime
from collections.abc import Sequence

import polars as pl
from sqlalchemy.orm import Session


def get_portfolio_positions(session: Session, max_date: datetime.date):
    # First, we load all trades up to the date
    df_investments = pl.read_database(
        """
        SELECT 
            portfolio_id::TEXT as portfolio_id,
            instrument_id::TEXT as instrument_id,
            date,
            quantity
        FROM investments WHERE date <= :max_date
        """,
        session,
        execute_options={"params": {"max_date": max_date}},
    )

    # Then, we define a range of dates to get the quantities for.
    s_cal_dates = pl.date_range(datetime.date(1900, 1, 1), max_date, eager=True)

    pairs = df_investments.select("portfolio_id", "instrument_id").unique()

    dfs = []
    for portfolio_id, instrument_id in pairs.iter_rows():
        df = (
            pl.DataFrame({"portfolio_id": portfolio_id, "instrument_id": instrument_id, "date": s_cal_dates})
            .join(df_investments, on=["portfolio_id", "instrument_id", "date"], how="left")
            .sort("date")
            .with_columns(quantity=pl.col("quantity").replace(None, 0).cum_sum())
            # Here, for the given instrument/portfolio pair, we remove dates before the first trade
            .filter((pl.col("quantity") != 0).cum_sum() > 0)
        )

        dfs.append(df)

    return (
        pl.concat(dfs)
        .filter(pl.col("date").dt.is_business_day())
        .group_by("portfolio_id", "instrument_id", "date")
        .agg(quantity=pl.col("quantity").sum())
    )


def main(argv: Sequence[str] | None = None) -> int:
    return 0
