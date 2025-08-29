from collections.abc import Sequence

from pydantic import BaseModel

from worker.database import connect
from worker.utils import get_single_instrument_portfolio_instruments


class InstrumentSchema(BaseModel):
    name: str
    ticker: str
    currency: str


def main(argv: Sequence[str] | None = None) -> int:
    with connect() as session:
        insts = get_single_instrument_portfolio_instruments(session)

        for inst in insts:
            print(inst)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
