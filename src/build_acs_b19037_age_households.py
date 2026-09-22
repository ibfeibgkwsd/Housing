# -*- coding: utf-8 -*-
"""Build long-format ACS B19037 household counts by age of householder.

Output columns are exactly: metro, year, age_bracket, households.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


API_ROOT = "https://api.census.gov/data"
DATASET = "acs/acs1"
GEO_PARAM = "metropolitan statistical area/micropolitan statistical area"
UNAVAILABLE_YEARS = {2020}
AGE_VARIABLES = {
    "B19037_002E": "under_25",
    "B19037_019E": "25_44",
    "B19037_036E": "45_64",
    "B19037_053E": "65_plus",
}


def fetch_year(year: int, api_key: str) -> pd.DataFrame:
    params = {
        "get": ",".join(["NAME", *AGE_VARIABLES]),
        "for": f"{GEO_PARAM}:*",
        "key": api_key,
    }
    url = f"{API_ROOT}/{year}/{DATASET}?{urlencode(params)}"
    with urlopen(url, timeout=60) as response:
        text = response.read().decode("utf-8", errors="replace")
    if text.lstrip().lower().startswith("<html"):
        if "invalid key" in text.lower():
            raise RuntimeError("Census rejected CENSUS_API_KEY as invalid.")
        raise RuntimeError("Census returned HTML instead of data; check CENSUS_API_KEY.")

    payload = json.loads(text)
    frame = pd.DataFrame(payload[1:], columns=payload[0]).rename(
        columns={"NAME": "metro", **AGE_VARIABLES}
    )
    for bracket in AGE_VARIABLES.values():
        frame[bracket] = pd.to_numeric(frame[bracket], errors="coerce")
    frame["year"] = year
    return frame.melt(
        id_vars=["metro", "year"],
        value_vars=list(AGE_VARIABLES.values()),
        var_name="age_bracket",
        value_name="households",
    )[["metro", "year", "age_bracket", "households"]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2005)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data") / "derived" / "acs_b19037_age_households_2005_2024.csv",
    )
    args = parser.parse_args()
    api_key = os.getenv("CENSUS_API_KEY")
    if not api_key:
        raise RuntimeError("Set CENSUS_API_KEY before running this loader.")

    frames: list[pd.DataFrame] = []
    for year in range(args.start_year, args.end_year + 1):
        if year in UNAVAILABLE_YEARS:
            print(f"{year}: skipped (ACS 1-year estimates were not released)")
            continue
        frame = fetch_year(year, api_key)
        if frame.duplicated(["metro", "year", "age_bracket"]).any():
            raise ValueError(f"Duplicate metro-year-age keys returned for {year}")
        frames.append(frame)
        print(f"{year}: {len(frame) // len(AGE_VARIABLES):,} metros")
        time.sleep(0.25)

    output = pd.concat(frames, ignore_index=True).sort_values(
        ["metro", "year", "age_bracket"]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(f"Wrote {len(output):,} rows to {args.output}")


if __name__ == "__main__":
    main()
