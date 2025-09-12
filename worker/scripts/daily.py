#!/usr/bin/env -S uv run

"""Daily operation."""

import argparse
import datetime

from worker.processes import daily_run

# Constants
ROOT_URL = "https://api.marketstack.com/v2"
EOD_URL = f"{ROOT_URL}/eod"


# Before we do anything, we load data from our database
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("date")
    args = parser.parse_args()

    ref_date = datetime.datetime.strptime(args.date, "%Y%m%d").date()
    daily_run(ref_date=ref_date)


if __name__ == "__main__":
    raise SystemExit(main())
