import datetime

import polars as pl
from sqlalchemy.orm import Session


def get_adjusted_close_up_to_date(session: Session, max_date: datetime.date):
    return pl.read_database(
        """
        SELECT
            date,
            instrument_id::TEXT as instrument_id,
            value AS price
        FROM market_data
        WHERE 
            1=1
            AND date <= :date
            AND data_type = 'adj_close'""",
        session,
        execute_options={"params": {"date": max_date}},
    )


def get_portfolio_compositions(session: Session, date: datetime.date):
    return pl.read_database(
        """
            SELECT 
                portfolio_id::TEXT,
                instrument_id::TEXT,
                date,
                quantity
            FROM ptf_comp
            WHERE 
                1=1
                AND date = :date
            """,
        session,
        execute_options={"params": {"date": date}},
    )


def get_investments_over_time_range(session: Session, date_start: datetime.date, date_end: datetime.date):
    return pl.read_database(
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
        execute_options={"params": {"max_date": date_end, "min_date": date_start}},
        schema_overrides={
            "portfolio_id": pl.String,
            "instrument_id": pl.String,
            "date": pl.Date,
            "quantity": pl.Decimal(),
        },
    )


def get_latest_compositions(session: Session):
    return pl.read_database(
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
            ON 
                ptf_comp.portfolio_id = T.portfolio_id
            WHERE 
                ptf_comp.date = T.max_date
            """,
        session,
    )


def get_latest_market_data_dates(session: Session):
    return pl.read_database(
        """
            SELECT 
                instrument_id, 
                MAX(date) AS max_date
            FROM market_data
            GROUP BY instrument_id
            """,
        session,
    )


def get_all_portfolio_ids(session: Session):
    return pl.read_database(
        """
            SELECT id::TEXT
            FROM portfolios
        """,
        session,
    )


def get_unique_instruments(session: Session):
    return pl.read_database(
        """
            SELECT DISTINCT 
                id, 
                ticker
            FROM instruments
        """,
        session,
    )


def get_all_dates(session: Session):
    return pl.read_database("SELECT * FROM dates", session)
