#!/usr/bin/env -S uv run

import datetime
from collections.abc import Sequence

from pydantic import BaseModel

from worker.database import Holding
from worker.database import Portfolio
from worker.database import connect
from worker.utils import get_all_instruments
from worker.utils import get_single_instrument_portfolio_instruments


class InstrumentSchema(BaseModel):
    name: str
    ticker: str
    currency: str


def main(argv: Sequence[str] | None = None) -> int:
    with connect() as session:
        # Instruments who are already in a single-instrument portfolio
        insts = get_single_instrument_portfolio_instruments(session)
        inst_ids = set([inst.id for inst in insts])

        all_insts = get_all_instruments(session)

        for inst in all_insts:
            if inst.id in inst_ids:
                continue

            ptf = Portfolio(name=inst.name, currency=inst.currency)

            session.add(ptf)
            session.flush()

            holding = Holding(
                as_of=datetime.date.today(),
                portfolio_id=ptf.id,
                instrument_id=inst.id,
                quantity=1,
            )

            session.add(holding)

        session.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
