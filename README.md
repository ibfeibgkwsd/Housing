# Housing returns project

The project currently combines three compatible-but-distinct datasets:

| Dataset | Unit | Role | Join key |
| --- | --- | --- | --- |
| FHFA metro HPI | Metro-quarter | House-price outcome | `cbsa` |
| ACS 1-year | CBSA-year | Household demand and household income | `cbsa` |
| OEWS/BLS | Metro-year | Labor-market context | `AREA` / CBSA after validation |

## Layout

- `notebooks/`: the clean, output-free [analysis notebook](notebooks/housing_analysis.ipynb)
- `data/raw/`: active raw FHFA inputs
- `data/derived/`: compiled ACS and BLS analysis datasets
- `outputs/`: saved figures and diagnostics
- `archive/`: the original notebook and raw or duplicate downloads retained for reference
- `src/`: repeatable ACS loaders

The old notebook is preserved at `archive/notebooks/Untitled_before_cleanup.ipynb`.

## Household panel

Run the ACS loader from the project root:

```powershell
$env:CENSUS_API_KEY = "your Census Data API key"
.\.venv\Scripts\python.exe src\build_acs_household_panel.py
```

The Census API currently requires an API key. The key is read only from the
`CENSUS_API_KEY` environment variable and is never written into the project.

It writes `data/derived/acs_household_panel_2005_2024.csv`, with one row per CBSA-year.
The measures are:

- `households`: total households (`B11001_001E`)
- `median_household_income`: household median income (`B19013_001E`)
- `household_income_p20` through `household_income_p80`: the upper limits of the first through fourth household-income quintiles (`B19080`)

The 2020 ACS 1-year release is intentionally omitted: it was not published due to pandemic collection disruptions. The loader does not fill that gap or substitute ACS 5-year estimates, because that would mix annual and multi-year measures in the same panel.

The 2005 ACS 1-year detailed tables do not include `B19080`, so that year is
retained with `households` and `median_household_income`, while its four
income-percentile columns are missing.

ACS 1-year estimates cover qualifying geographies, so some smaller CBSAs will be absent. Keep that selection issue visible when merging to the broader FHFA panel.

The household-income columns are nominal dollars. Deflate them before comparing income levels across years; use nominal year-over-year changes only when that is the explicit question.

## Household composition and housing stock

Run the complementary market-structure loader with the same API key:

```powershell
.\.venv\Scripts\python.exe src\build_acs_market_panel.py
```

It writes `data/derived/acs_market_panel_2005_2024.csv`. It contains the full B19001
household-income-bin distribution, housing-unit counts and structure types,
vacancy, and owner/renter household counts by householder age. Its derived
fields include the share of households aged 25–44, the corresponding owner and
renter counts, detached-single-family share, 5+-unit multifamily share, and
vacancy rate.

S2501 is useful for selected descriptive cuts but has no 2005 ACS 1-year
release and does not provide one clean total-household age distribution. The
panel uses B25007 instead, which directly separates owner and renter households
by age and is available for the full working period. DP02 is similarly not
included because its broad social-profile fields duplicate less directly
interpretable detailed-table measures.

A small number of CBSA-year observations have suppressed `B25024` structure
counts, so their detached and multifamily shares remain missing rather than
being imputed. All other core count and age-composition fields are retained.

## B19037 age-of-householder extract

```powershell
.\.venv\Scripts\python.exe src\build_acs_b19037_age_households.py
```

This writes `data/derived/acs_b19037_age_households_2005_2024.csv` in long form with
exactly `metro`, `year`, `age_bracket`, and `households` columns. The brackets
are `under_25`, `25_44`, `45_64`, and `65_plus`; each is the parent total from
B19037, not a sum of reported income cells. As with the other ACS 1-year
outputs, 2020 is omitted.
