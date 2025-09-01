#!/usr/bin/env -S uv run

import argparse
import datetime
import os
from collections.abc import Sequence

import polars as pl

from worker.database import PortfolioComposition
from worker.database import PortfolioValue
from worker.database import connect
from worker.utils import insert_list_of_dicts


def fill_portfolio_positions_for_single_date(session, date: datetime.date):
    df_investments = pl.read_database(
        """
        SELECT 
            portfolio_id::TEXT as portfolio_id,
            instrument_id::TEXT as instrument_id,
            date,
            quantity
        FROM investments WHERE date <= :date
        """,
        session,
        execute_options={"params": {"date": date}},
    )

    df_market_data = pl.read_database(
        """
            SELECT
                date,
                instrument_id::TEXT as instrument_id,
                value
            FROM market_data
            WHERE date = :date
            AND data_type = 'adj_close'""",
        session,
        execute_options={"params": {"date": date}},
    )

    df_positions_single_date = (
        df_investments.filter(pl.col("date") <= date)
        .group_by("portfolio_id", "instrument_id")
        .agg(quantity=pl.col("quantity").sum())
        .with_columns(date=pl.lit(date))
    )

    df_values_single_date = (
        df_positions_single_date.join(df_market_data, how="left", on=["instrument_id", "date"])
        .rename({"value": "price"})
        .with_columns(value=pl.col("quantity") * pl.col("price"))
        .group_by("portfolio_id", "date")
        .agg(value=pl.col("value").sum())
    )

    insert_list_of_dicts(items=df_positions_single_date.to_dicts(), table=PortfolioComposition, session=session)
    insert_list_of_dicts(items=df_values_single_date.to_dicts(), table=PortfolioValue, session=session)

    session.commit()


def fill_portfolio_values_multiple_dates(session, date_start: datetime.date, date_end: datetime.date):
    s_cal_dates = pl.date_range(date_start, date_end, eager=True)

    df_investments = pl.read_database(
        """
        SELECT 
            portfolio_id::TEXT as portfolio_id,
            instrument_id::TEXT as instrument_id,
            date,
            quantity
        FROM investments WHERE date <= :date
        """,
        session,
        execute_options={"params": {"date": date_end}},
    )

    df_market_data = pl.read_database(
        """
            SELECT
                date,
                instrument_id::TEXT as instrument_id,
                value
            FROM market_data
            WHERE date <= :date_max 
            AND date >= :date_min 
            AND data_type = 'adj_close'""",
        session,
        execute_options={"params": {"date_min": date_start, "date_max": date_end}},
    )

    # Build portfolio compositions and values for a range of dates
    pairs = df_investments.select("portfolio_id", "instrument_id").unique()

    dfs = []
    for portfolio_id, instrument_id in pairs.iter_rows():
        df = (
            pl.DataFrame({"portfolio_id": portfolio_id, "instrument_id": instrument_id, "date": s_cal_dates})
            .join(df_investments, on=["portfolio_id", "instrument_id", "date"], how="left")
            .sort("date")
            .with_columns(quantity=pl.col("quantity").replace(None, 0).cum_sum())
            .filter((pl.col("quantity") != 0).cum_sum() > 0)
        )

        dfs.append(df)

    df_all_ptf_compositions = pl.concat(dfs)

    df_ptf_values = (
        df_all_ptf_compositions.filter(pl.col("date").dt.is_business_day())
        .join(df_market_data, on=["date", "instrument_id"], how="left")
        .group_by("portfolio_id", "instrument_id")
        .map_groups(lambda df: df.sort("date").with_columns(pl.col("value").forward_fill()))
        .filter(pl.col("value").is_not_null())
        .rename({"value": "price"})
        .with_columns(value=pl.col("quantity") * pl.col("price"))
        .group_by("portfolio_id", "date")
        .agg(value=pl.col("value").sum())
    )

    insert_list_of_dicts(items=df_ptf_values.to_dicts(), table=PortfolioValue, session=session)

    return df_ptf_values


def run_single_date(args):
    date = datetime.datetime.strptime(args.date, "%Y%m%d").date()
    with connect() as session:
        fill_portfolio_positions_for_single_date(session, date=date)


def run_multiple_dates(args):
    from_date = datetime.datetime.strptime(args.from_, "%Y%m%d").date()
    to_date = datetime.datetime.strptime(args.to_, "%Y%m%d").date()
    with connect() as session:
        fill_portfolio_values_multiple_dates(session, date_start=from_date, date_end=to_date)
        fill_portfolio_positions_for_single_date(session, date=to_date)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_single = subparsers.add_parser("single", help="run a single date")
    p_single.add_argument("date", help="the date")
    p_single.set_defaults(func=run_single_date)

    p_multiple = subparsers.add_parser("multiple", help="run multiple dates")
    p_multiple.add_argument("from_", help="the start date")
    p_multiple.add_argument("to_", help="the end date")
    p_multiple.set_defaults(func=run_multiple_dates)

    args = parser.parse_args(argv)
    args.func(args)

    return 0


if __name__ == "__main__":
    if os.getenv("WORKER_DEBUG") == "1":
        raise SystemExit(main(["single", "20250826"]))
    raise SystemExit(main())
