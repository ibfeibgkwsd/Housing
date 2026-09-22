# -*- coding: utf-8 -*-
"""Build a CBSA-year panel of household demand and income from ACS 1-year data.

The resulting table is deliberately household-level.  It should be joined to
FHFA HPI using ``cbsa`` rather than metro names, which change over time.

Usage:
    python src/build_acs_household_panel.py
    python src/build_acs_household_panel.py --start-year 2005 --end-year 2024

An API key is optional for the small queries made here.  Set CENSUS_API_KEY if
the Census API asks for one or if the workflow is expanded later.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


API_ROOT = "https://api.census.gov/data"
DATASET = "acs/acs1"
# 2020 ACS 1-year estimates were not released because of pandemic collection
# disruptions; retaining it as a missing year is more honest than substituting
# a multi-year estimate in an annual panel.
UNAVAILABLE_YEARS = {2020}

# B11001 and B19013 are household-universe tables. B19080 provides the upper
# limit of quintiles 1 through 4; the fifth published value is the lower limit
# of the top 5 percent, so it is intentionally not treated as an income P100.
VARIABLES = {
    "B11001_001E": "households",
    "B19013_001E": "median_household_income",
    "B19080_001E": "household_income_p20",
    "B19080_002E": "household_income_p40",
    "B19080_003E": "household_income_p60",
    "B19080_004E": "household_income_p80",
}
GEO_PARAM = "metropolitan statistical area/micropolitan statistical area"


def request_payload(
    year: int, variable_codes: list[str], api_key: str | None = None
) -> list[list[str]]:
    """Request a set of ACS estimate variables for every metro/micro CBSA."""
    params = {
        "get": ",".join(["NAME", *variable_codes]),
        "for": f"{GEO_PARAM}:*",
    }
    if api_key:
        params["key"] = api_key

    url = f"{API_ROOT}/{year}/{DATASET}?{urlencode(params)}"
    with urlopen(url, timeout=60) as response:
        body = response.read()
    text = body.decode("utf-8", errors="replace")
    if text.lstrip().lower().startswith("<html"):
        if "invalid key" in text.lower():
            raise RuntimeError(
                "Census rejected CENSUS_API_KEY as invalid. Obtain or verify "
                "a Census Data API key and retry."
            )
        raise RuntimeError(
            "Census returned an HTML page instead of data. Set CENSUS_API_KEY "
            "to a Census Data API key and retry."
        )
    payload = json.loads(text)

    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError(f"Unexpected ACS response for {year}: {payload!r}")
    return payload


def fetch_year(year: int, api_key: str | None = None) -> pd.DataFrame:
    """Fetch one ACS 1-year vintage for every metro/micro CBSA."""
    variable_codes = list(VARIABLES)
    unavailable_variables: list[str] = []
    try:
        payload = request_payload(year, variable_codes, api_key)
    except HTTPError as error:
        # B19080 is absent from the 2005 ACS 1-year detailed tables. Retain
        # the otherwise usable household count and median-income observation
        # rather than dropping an entire baseline year.
        base_codes = ["B11001_001E", "B19013_001E"]
        payload = request_payload(year, base_codes, api_key)
        variable_codes = base_codes
        unavailable_variables = [code for code in VARIABLES if code not in base_codes]
        print(f"{year}: detailed income-percentile fields unavailable ({error.code}); using base measures")

    frame = pd.DataFrame(payload[1:], columns=payload[0])
    frame = frame.rename(columns={"NAME": "name", GEO_PARAM: "cbsa", **VARIABLES})
    frame["year"] = year
    frame["cbsa"] = frame["cbsa"].astype(str).str.zfill(5)
    for code in unavailable_variables:
        frame[VARIABLES[code]] = pd.NA
    for column in VARIABLES.values():
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    return frame[["cbsa", "name", "year", *VARIABLES.values()]]


def build_panel(start_year: int, end_year: int, api_key: str | None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    failed_years: dict[int, str] = {}

    for year in range(start_year, end_year + 1):
        if year in UNAVAILABLE_YEARS:
            print(f"{year}: skipped (ACS 1-year estimates were not released)")
            continue
        try:
            frame = fetch_year(year, api_key)
        except Exception as error:  # identify the broken vintage before stopping
            failed_years[year] = str(error)
            print(f"{year}: FAILED - {error}")
            continue
        frames.append(frame)
        print(f"{year}: {len(frame):,} CBSAs")
        time.sleep(0.25)

    if not frames:
        detail = "; ".join(f"{year}: {error}" for year, error in failed_years.items())
        raise RuntimeError(f"No ACS data were downloaded. {detail}")

    panel = pd.concat(frames, ignore_index=True)
    if panel.duplicated(["cbsa", "year"]).any():
        raise ValueError("ACS response contains duplicate CBSA-year keys")
    panel = panel.sort_values(["cbsa", "year"]).reset_index(drop=True)
    panel.attrs["failed_years"] = failed_years
    return panel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2005)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data") / "derived" / "acs_household_panel_2005_2024.csv",
    )
    args = parser.parse_args()

    if args.start_year > args.end_year:
        raise ValueError("start year must not be after end year")

    panel = build_panel(args.start_year, args.end_year, os.getenv("CENSUS_API_KEY"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.output, index=False)

    missing = panel.isna().mean().sort_values(ascending=False)
    print(f"Wrote {len(panel):,} rows to {args.output}")
    print("Missing-value share:")
    print(missing.to_string())
    if panel.attrs["failed_years"]:
        print("Failed years:", ", ".join(map(str, panel.attrs["failed_years"])))


if __name__ == "__main__":
    main()
