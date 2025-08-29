from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from worker.database import Holding
from worker.database import Instrument


def get_single_instrument_portfolio_instruments(db: Session):
    # Get instruments that are the sole holding in any portfolio
    instrument_count_subq = (
        select(Holding.portfolio_id, func.count(func.distinct(Holding.instrument_id)).label("instrument_count"))
        .group_by(Holding.portfolio_id)
        .subquery()
    )

    res = db.scalars(
        select(Instrument)
        .join(Holding, Instrument.id == Holding.instrument_id)
        .join(instrument_count_subq, Holding.portfolio_id == instrument_count_subq.c.portfolio_id)
        .filter(instrument_count_subq.c.instrument_count == 1)
        .distinct()
    )
    return res.all()


def get_all_instruments(db: Session):
    return db.scalars(select(Instrument)).all()
