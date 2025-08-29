import json
from collections.abc import Sequence

from pydantic import BaseModel

from worker.database import Instrument
from worker.database import connect


class InstrumentSchema(BaseModel):
    name: str
    ticker: str
    currency: str


def main(argv: Sequence[str] | None = None) -> int:
    with open("data/etfs.json") as fd:
        data = json.load(fd)

    with connect() as session:
        for item in data:
            d_ = dict(name=item["Name"], ticker=item["Ticker"], currency="USD")

            InstrumentSchema.model_validate(d_)

            inst = Instrument(**d_)

            session.add(inst)

        session.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
