# -*- coding: utf-8 -*-
"""Insert compact incremental/partial R-squared cells into the active notebook.

The script intentionally preserves existing cells, outputs, and user edits.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent


NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "housing_analysis.ipynb"


def source(cell: dict) -> str:
    return "".join(cell.get("source", []))


def code_cell(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": dedent(text).lstrip().splitlines(keepends=True),
    }


def insert_after(cells: list[dict], marker: str, sentinel: str, new_cell: dict) -> None:
    if any(marker in source(cell) for cell in cells):
        if any(sentinel in source(cell) for cell in cells):
            return
        for index, cell in enumerate(cells):
            if marker in source(cell):
                cells.insert(index + 1, new_cell)
                return
    raise ValueError(f"Could not find notebook cell containing {marker!r}")


def replace_cell(cells: list[dict], marker: str, new_cell: dict) -> None:
    for index, cell in enumerate(cells):
        if marker in source(cell):
            cells[index] = new_cell
            return
    raise ValueError(f"Could not find notebook cell containing {marker!r}")


notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
cells = notebook["cells"]

insert_after(
    cells,
    'supply_table = compact_model_table(',
    "# Added R-squared comparison: housing-unit response",
    code_cell(
        """
        # Added R-squared comparison: housing-unit response
        housing_unit_year_only = smf.ols(
            "housing_unit_growth ~ C(year)", data=model_df
        ).fit()
        housing_unit_incremental_r2 = supply_model.rsquared - housing_unit_year_only.rsquared
        housing_unit_partial_r2 = (
            housing_unit_year_only.ssr - supply_model.ssr
        ) / housing_unit_year_only.ssr

        pd.DataFrame(
            {
                "year_only_r_squared": [housing_unit_year_only.rsquared],
                "full_r_squared": [supply_model.rsquared],
                "incremental_r_squared": [housing_unit_incremental_r2],
                "partial_r_squared": [housing_unit_partial_r2],
                "n": [int(supply_model.nobs)],
            },
            index=["housing_unit_growth ~ household_growth + C(year)"],
        )
        """
    ),
)

insert_after(
    cells,
    'vacancy_table = compact_model_table(',
    "# Added R-squared comparison: vacancy-lag specifications",
    code_cell(
        """
        # Added R-squared comparison: vacancy-lag specifications
        vacancy_fit_comparison = pd.DataFrame(
            {
                "model": ["FE only", "lag 1", "lag 2", "both lags"],
                "r_squared": [
                    vacancy_fe_only.rsquared,
                    vacancy_lag1_model.rsquared,
                    vacancy_lag2_model.rsquared,
                    vacancy_both_model.rsquared,
                ],
                "incremental_r_squared_vs_fe": [
                    0.0,
                    vacancy_lag1_model.rsquared - vacancy_fe_only.rsquared,
                    vacancy_lag2_model.rsquared - vacancy_fe_only.rsquared,
                    vacancy_both_model.rsquared - vacancy_fe_only.rsquared,
                ],
                "partial_r_squared_vs_fe": [
                    0.0,
                    partial_r_squared(vacancy_fe_only, vacancy_lag1_model),
                    partial_r_squared(vacancy_fe_only, vacancy_lag2_model),
                    partial_r_squared(vacancy_fe_only, vacancy_both_model),
                ],
                "n": [int(vacancy_fe_only.nobs)] * 4,
            }
        )
        vacancy_fit_comparison
        """
    ),
)

insert_after(
    cells,
    'trimmed_change_model = smf.ols(',
    "# Added R-squared comparison: vacancy reparameterization",
    code_cell(
        """
        # Added R-squared comparison: vacancy reparameterization
        trimmed_lag2_model = smf.ols(
            "household_growth ~ vacancy_lag2 + C(year) + C(cbsa)", data=trimmed_lag_sample
        ).fit(cov_type="cluster", cov_kwds={"groups": trimmed_lag_sample["cbsa"]})

        vacancy_change_fit_comparison = pd.DataFrame(
            {
                "sample": ["full", "trimmed"],
                "baseline_r_squared": [vacancy_lag2_model.rsquared, trimmed_lag2_model.rsquared],
                "full_r_squared": [vacancy_change_model.rsquared, trimmed_change_model.rsquared],
                "incremental_r_squared": [
                    vacancy_change_model.rsquared - vacancy_lag2_model.rsquared,
                    trimmed_change_model.rsquared - trimmed_lag2_model.rsquared,
                ],
                "partial_r_squared": [
                    partial_r_squared(vacancy_lag2_model, vacancy_change_model),
                    partial_r_squared(trimmed_lag2_model, trimmed_change_model),
                ],
                "n": [int(vacancy_change_model.nobs), int(trimmed_change_model.nobs)],
            }
        )
        vacancy_change_fit_comparison
        """
    ),
)

replace_cell(
    cells,
    'hpi_hh_only = smf.ols(',
    code_cell(
        """
        # HPI fit gained by adding housing-unit growth to household growth
        hpi_hh_only = smf.ols(
            "hpi_yoy ~ household_growth + C(year)", data=model_df
        ).fit()
        hpi_housing_unit_fit = pd.DataFrame(
            {
                "baseline_r_squared": [hpi_hh_only.rsquared],
                "full_r_squared": [hpi_supply_model.rsquared],
                "incremental_r_squared": [hpi_supply_model.rsquared - hpi_hh_only.rsquared],
                "partial_r_squared": [
                    (hpi_hh_only.ssr - hpi_supply_model.ssr) / hpi_hh_only.ssr
                ],
                "n": [int(hpi_supply_model.nobs)],
            },
            index=["HPI: add housing-unit growth given household growth"],
        )
        hpi_housing_unit_fit
        """
    ),
)

NOTEBOOK.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")
print(f"Updated {NOTEBOOK}")
