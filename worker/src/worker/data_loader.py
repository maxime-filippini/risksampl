import datetime

ROOT_URL = "https://api.marketstack.com/v2"
EOD_URL = f"{ROOT_URL}/eod"


def _build_ticker_lists(tickers: list[str], max_tickers: int) -> list[str]:
    out = []

    while True:
        batch = tickers[:max_tickers]
        out.append(",".join(batch))

        n = len(batch)

        if n < max_tickers:
            break

        tickers = tickers[n:]

    return out


def load_batch(tickers: list[str], date_start: datetime.date, date_end: datetime.date):
    pass


# async def load_single_date(tickers: list[str], date: datetime.date):
#     batches = _build_ticker_lists(tickers, max_tickers=100)

#     async with httpx.AsyncClient() as client:
#         for batch
#         resp = client.get(EOD_URL, params={
#             "symbols":
#         })
