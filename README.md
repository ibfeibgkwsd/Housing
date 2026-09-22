# Metro housing growth and returns

[Read the report (PDF)](housing.pdf) · [View the analysis notebook](notebooks/housing_analysis.ipynb)

This project studies annual house-price growth across U.S. metropolitan areas from 2005 through 2024. It asks how house-price appreciation relates to household growth, the composition of the existing housing stock, housing-unit growth, and lagged vacancy.

The analysis is descriptive rather than causal. In particular, household formation, construction, vacancy, and house prices can all affect one another; the regressions therefore document conditional associations, not the effects of a policy intervention.

## Data used in the report

- **FHFA All-Transactions House Price Index:** quarterly metropolitan HPI observations are averaged to annual values, and annual HPI growth is calculated within each metro.
- **American Community Survey (ACS) 1-year detailed tables:** metro-level estimates of occupied households, housing units, occupancy, structure type, and vacancy. The active extract is [`data/derived/acs_market_panel_2005_2024.csv`](data/derived/acs_market_panel_2005_2024.csv).

The sample is restricted to metropolitan statistical areas, which matches the FHFA geography. For metros that FHFA also reports as metropolitan divisions, the MSA HPI series is retained for geographic consistency with the ACS.

## Comparability rules

- **2020:** excluded because standard ACS 1-year estimates were not released.
- **2010, 2013, 2019, and 2023:** growth calculations that cross these ACS population-control or CBSA-delineation transitions are excluded.
- **Annual HPI:** calculated as the mean of quarterly FHFA index values; annual growth is the within-metro percent change.

## Analyses

The notebook estimates fixed-effects regressions with year and, where noted, metro fixed effects. It covers:

1. HPI growth, household growth, detached single-family share, and their interaction.
2. The relationship between household growth and housing-unit growth, plus the incremental fit of housing-unit growth in an HPI model.
3. Whether one- and two-year lagged vacancy rates predict subsequent household growth, including a reparameterization in terms of older vacancy levels and vacancy change, and a 1% trimmed robustness check.

The report presents the full estimates and fit comparisons, including incremental and partial $R^2$ measures. The notebook is the reproducible source for the reported tables and exploratory figures.

## Repository layout

- [`housing.pdf`](housing.pdf): concise written report.
- [`housing.tex`](housing.tex): report source.
- [`notebooks/housing_analysis.ipynb`](notebooks/housing_analysis.ipynb): data preparation, exploration, and regression analysis.
- [`data/raw/fhfa/`](data/raw/fhfa): FHFA inputs used by the notebook.
- [`data/derived/`](data/derived): prepared ACS panel and supporting extracts.
- [`src/`](src): Census ACS extraction scripts.
- [`outputs/`](outputs): saved figures and diagnostics.

Some supplementary extracts remain in `data/derived/` from exploratory work; they are not inputs to the report unless referenced by the notebook. The local `archive/` folder and virtual environment are intentionally excluded from the public repository.

## Reproducing the analysis

Open and run [`notebooks/housing_analysis.ipynb`](notebooks/housing_analysis.ipynb) from the project root. The committed FHFA and prepared ACS inputs are sufficient for the current notebook. Rebuilding ACS source extracts requires a Census API key supplied through the `CENSUS_API_KEY` environment variable; no key is stored in this repository.
