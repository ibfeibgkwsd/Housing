# -*- coding: utf-8 -*-
"""Build a CBSA-year ACS panel for household composition and housing supply.

This complements build_acs_household_panel.py. It keeps counts as counts and
adds a small set of transparent, reproducible derived shares.
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

INCOME_BINS = {
    "B19001_002E": "households_income_lt_10k",
    "B19001_003E": "households_income_10k_15k",
    "B19001_004E": "households_income_15k_20k",
    "B19001_005E": "households_income_20k_25k",
    "B19001_006E": "households_income_25k_30k",
    "B19001_007E": "households_income_30k_35k",
    "B19001_008E": "households_income_35k_40k",
    "B19001_009E": "households_income_40k_45k",
    "B19001_010E": "households_income_45k_50k",
    "B19001_011E": "households_income_50k_60k",
    "B19001_012E": "households_income_60k_75k",
    "B19001_013E": "households_income_75k_100k",
    "B19001_014E": "households_income_100k_125k",
    "B19001_015E": "households_income_125k_150k",
    "B19001_016E": "households_income_150k_200k",
    "B19001_017E": "households_income_200k_plus",
}
HOUSING_STOCK = {
    "B25001_001E": "housing_units",
    "B25002_002E": "occupied_housing_units",
    "B25002_003E": "vacant_housing_units",
    "B25024_002E": "housing_units_1_detached",
    "B25024_003E": "housing_units_1_attached",
    "B25024_004E": "housing_units_2",
    "B25024_005E": "housing_units_3_4",
    "B25024_006E": "housing_units_5_9",
    "B25024_007E": "housing_units_10_19",
    "B25024_008E": "housing_units_20_49",
    "B25024_009E": "housing_units_50_plus",
    "B25024_010E": "housing_units_mobile_home",
    "B25024_011E": "housing_units_other",
}
TENURE_BY_AGE = {
    "B25007_002E": "owner_households",
    "B25007_003E": "owner_households_15_24",
    "B25007_004E": "owner_households_25_34",
    "B25007_005E": "owner_households_35_44",
    "B25007_006E": "owner_households_45_54",
    "B25007_007E": "owner_households_55_59",
    "B25007_008E": "owner_households_60_64",
    "B25007_009E": "owner_households_65_74",
    "B25007_010E": "owner_households_75_84",
    "B25007_011E": "owner_households_85_plus",
    "B25007_012E": "renter_households",
    "B25007_013E": "renter_households_15_24",
    "B25007_014E": "renter_households_25_34",
    "B25007_015E": "renter_households_35_44",
    "B25007_016E": "renter_households_45_54",
    "B25007_017E": "renter_households_55_59",
    "B25007_018E": "renter_households_60_64",
    "B25007_019E": "renter_households_65_74",
    "B25007_020E": "renter_households_75_84",
    "B25007_021E": "renter_households_85_plus",
}
TABLES = (INCOME_BINS, HOUSING_STOCK, TENURE_BY_AGE)


def request_table(year: int, variables: dict[str, str], api_key: str) -> pd.DataFrame:
    params = {
        "get": ",".join(["NAME", *variables]),
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
        columns={"NAME": "name", GEO_PARAM: "cbsa", **variables}
    )
    frame["cbsa"] = frame["cbsa"].astype(str).str.zfill(5)
    for column in variables.values():
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame[["cbsa", "name", *variables.values()]]


def derive_features(frame: pd.DataFrame) -> pd.DataFrame:
    frame["households_income_50k_to_100k"] = frame[
        ["households_income_50k_60k", "households_income_60k_75k", "households_income_75k_100k"]
    ].sum(axis=1, min_count=3)
    frame["housing_units_multifamily_5plus"] = frame[
        ["housing_units_5_9", "housing_units_10_19", "housing_units_20_49", "housing_units_50_plus"]
    ].sum(axis=1, min_count=4)
    frame["share_sf_detached"] = frame["housing_units_1_detached"] / frame["housing_units"]
    frame["share_multifamily_5plus"] = frame["housing_units_multifamily_5plus"] / frame["housing_units"]
    frame["vacancy_rate"] = frame["vacant_housing_units"] / frame["housing_units"]
    frame["households_25_44"] = frame[
        [
            "owner_households_25_34",
            "owner_households_35_44",
            "renter_households_25_34",
            "renter_households_35_44",
        ]
    ].sum(axis=1, min_count=4)
    frame["owner_households_25_44"] = frame[
        ["owner_households_25_34", "owner_households_35_44"]
    ].sum(axis=1, min_count=2)
    frame["renter_households_25_44"] = frame[
        ["renter_households_25_34", "renter_households_35_44"]
    ].sum(axis=1, min_count=2)
    frame["share_households_25_44"] = frame["households_25_44"] / (
        frame["owner_households"] + frame["renter_households"]
    )
    return frame


def build_panel(start_year: int, end_year: int, api_key: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year in range(start_year, end_year + 1):
        if year in UNAVAILABLE_YEARS:
            print(f"{year}: skipped (ACS 1-year estimates were not released)")
            continue
        tables = [request_table(year, variables, api_key) for variables in TABLES]
        frame = tables[0]
        for table in tables[1:]:
            frame = frame.merge(table.drop(columns="name"), on="cbsa", how="inner", validate="one_to_one")
        frame["year"] = year
        frames.append(derive_features(frame))
        print(f"{year}: {len(frame):,} CBSAs")
        time.sleep(0.25)
    panel = pd.concat(frames, ignore_index=True).sort_values(["cbsa", "year"]).reset_index(drop=True)
    if panel.duplicated(["cbsa", "year"]).any():
        raise ValueError("Duplicate CBSA-year keys in output")
    return panel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2005)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--output", type=Path, default=Path("data") / "derived" / "acs_market_panel_2005_2024.csv")
    args = parser.parse_args()
    api_key = os.getenv("CENSUS_API_KEY")
    if not api_key:
        raise RuntimeError("Set CENSUS_API_KEY before running this loader.")
    panel = build_panel(args.start_year, args.end_year, api_key)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.output, index=False)
    print(f"Wrote {len(panel):,} rows to {args.output}")


if __name__ == "__main__":
    main()
