# -*- coding: utf-8 -*-
"""Create the organized, output-free housing analysis notebook."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "housing_analysis.ipynb"


def markdown(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": dedent(source).lstrip().splitlines(keepends=True),
    }


cells = [
    markdown(
        "# Housing returns analysis\n\n"
        "This notebook uses the organized project layout. The pre-cleanup notebook is retained under `archive/notebooks/`. "
        "Run sections in order: imports, sources, panel construction, then exploration or models.\n"
    ),
    code(
        """
        from pathlib import Path

        import numpy as np
        import pandas as pd
        import matplotlib.pyplot as plt
        import statsmodels.formula.api as smf

        ROOT = Path.cwd()
        if not (ROOT / "data").exists():
            ROOT = ROOT.parent

        RAW = ROOT / "data" / "raw"
        DERIVED = ROOT / "data" / "derived"
        OUTPUTS = ROOT / "outputs"
        """
    ),
    markdown("## Sources and annual panel\n\nThe conservative vacancy models exclude 2010 as an estimation year while retaining its vacancy value as a valid historical lag for 2012.\n"),
    code(
        """
        hpi = pd.read_csv(
            RAW / "fhfa" / "hpi_at_metro.csv",
            header=None,
            names=["metro", "cbsa", "year", "quarter", "hpi", "se"],
            na_values="-",
        )
        hpi["cbsa"] = hpi["cbsa"].astype("Int64")
        hpi["se"] = hpi["se"].str.strip("()").astype(float)
        hpi = hpi.dropna(subset=["hpi"]).copy()

        # FHFA publishes selected large metros as metropolitan divisions.
        hpi_divisions = pd.read_excel(
            RAW / "fhfa" / "hpi_at_multid_metro.xlsx",
            header=3,
            names=["cbsa", "metro", "year", "quarter", "hpi"],
        )
        hpi_msa = hpi[~hpi["metro"].str.contains("MSAD", case=False, na=False)].copy()
        hpi_analysis = pd.concat([hpi_msa, hpi_divisions], ignore_index=True)

        hpi_annual = (
            hpi_analysis.groupby(["cbsa", "year"], as_index=False)["hpi"]
            .mean()
            .sort_values(["cbsa", "year"])
        )
        hpi_annual["hpi_yoy"] = hpi_annual.groupby("cbsa")["hpi"].pct_change(fill_method=None)
        """
    ),
    code(
        """
        acs = pd.read_csv(DERIVED / "acs_market_panel_2005_2024.csv")
        acs = acs[acs["name"].str.endswith("Metro Area")].copy()
        acs = acs.sort_values(["cbsa", "year"])
        acs["households"] = acs["occupied_housing_units"]
        acs["previous_year"] = acs.groupby("cbsa")["year"].shift()
        acs["household_growth"] = acs.groupby("cbsa")["households"].pct_change(fill_method=None)
        acs["housing_unit_growth"] = acs.groupby("cbsa")["housing_units"].pct_change(fill_method=None)

        # Do not treat gaps or CBSA delineation changes as annual growth.
        nonconsecutive = acs["year"] - acs["previous_year"] != 1
        delineation_year = acs["year"].isin([2013, 2019, 2023])
        acs.loc[nonconsecutive | delineation_year, ["household_growth", "housing_unit_growth"]] = np.nan

        bls = pd.read_csv(DERIVED / "bls_metro_wages_2005_2025.csv")
        bls["metro"] = bls["AREA_TITLE"].fillna(bls["AREA_NAME"])
        """
    ),
    code(
        """
        panel = acs.merge(
            hpi_annual[["cbsa", "year", "hpi", "hpi_yoy"]],
            on=["cbsa", "year"],
            how="left",
            validate="one_to_one",
        )
        panel_clean = panel[panel["hpi"].notna()].copy()

        print(f"ACS metro rows: {len(acs):,}")
        print(f"Matched panel rows: {len(panel_clean):,}")
        print(f"Missing HPI share: {panel['hpi'].isna().mean():.1%}")
        """
    ),
    markdown("## Exploration\n"),
    code(
        """
        def plot_metros(frame, cbsas, x, y, title, ylabel):
            subset = frame[frame["cbsa"].isin(cbsas)]
            plt.figure(figsize=(12, 7))
            for _, group in subset.groupby("cbsa"):
                plt.plot(group[x], group[y], label=group["name"].iloc[-1])
            plt.title(title)
            plt.xlabel(x.replace("_", " ").title())
            plt.ylabel(ylabel)
            plt.legend(fontsize=8)
            plt.show()


        comparison_cbsas = [31080, 41860, 35620, 14460, 16980, 26420, 19100, 12060, 38060, 42660]
        plot_metros(
            panel_clean,
            comparison_cbsas,
            "year",
            "share_sf_detached",
            "Single-family detached share",
            "Share of housing units",
        )
        """
    ),
    code(
        """
        year_df = panel_clean[panel_clean["year"] == 2024]
        plt.figure(figsize=(8, 6))
        plt.scatter(year_df["household_growth"], year_df["hpi_yoy"], alpha=0.5)
        plt.axhline(0, color="0.7", linewidth=1)
        plt.axvline(0, color="0.7", linewidth=1)
        plt.xlabel("Household growth")
        plt.ylabel("HPI growth")
        plt.title("Household growth vs. house-price growth, 2024")
        plt.show()
        """
    ),
    markdown("## Fixed-effects models\n\nThese are descriptive regressions, not causal estimates.\n"),
    code(
        """
        model_df = panel_clean.dropna(
            subset=["hpi_yoy", "household_growth", "share_sf_detached", "housing_unit_growth", "vacancy_rate"]
        ).copy()
        model_df["sf_centered"] = model_df["share_sf_detached"] - model_df["share_sf_detached"].mean()

        def compact_model_table(models, terms):
            # Show substantive coefficients only; fixed-effect dummies stay hidden.
            rows = []
            for name, model in models.items():
                for term in terms:
                    if term in model.params:
                        rows.append(
                            {
                                "model": name,
                                "term": term,
                                "coefficient": model.params[term],
                                "standard_error": model.bse[term],
                                "p_value": model.pvalues[term],
                                "r_squared": model.rsquared,
                                "n": int(model.nobs),
                            }
                        )
            return pd.DataFrame(rows)

        hpi_model = smf.ols(
            "hpi_yoy ~ household_growth * sf_centered + C(year) + C(cbsa)",
            data=model_df,
        ).fit(cov_type="cluster", cov_kwds={"groups": model_df["cbsa"]})

        supply_model = smf.ols(
            "housing_unit_growth ~ household_growth + C(year)",
            data=model_df,
        ).fit(cov_type="cluster", cov_kwds={"groups": model_df["cbsa"]})

        year_only = smf.ols("hpi_yoy ~ C(year)", data=model_df).fit()
        year_plus_x = smf.ols(
            "hpi_yoy ~ household_growth * sf_centered + C(year)", data=model_df
        ).fit()
        fe_only = smf.ols("hpi_yoy ~ C(year) + C(cbsa)", data=model_df).fit()
        fe_plus_x = smf.ols(
            "hpi_yoy ~ household_growth * sf_centered + C(year) + C(cbsa)", data=model_df
        ).fit()

        hpi_model_table = compact_model_table(
            {"fixed effects": hpi_model},
            ["household_growth", "sf_centered", "household_growth:sf_centered"],
        )
        fit_comparison = pd.DataFrame(
            {
                "model": ["year only", "year + variables", "year + metro FE", "FE + variables"],
                "r_squared": [year_only.rsquared, year_plus_x.rsquared, fe_only.rsquared, fe_plus_x.rsquared],
            }
        )
        fit_comparison["incremental_r_squared"] = fit_comparison["r_squared"].diff()

        hpi_model_table, fit_comparison
        """
    ),
    code(
        """
        hpi_supply_model = smf.ols(
            "hpi_yoy ~ household_growth + housing_unit_growth + C(year)", data=model_df
        ).fit(cov_type="cluster", cov_kwds={"groups": model_df["cbsa"]})

        compact_model_table(
            {"supply response": supply_model, "HPI with supply": hpi_supply_model},
            ["household_growth", "housing_unit_growth"],
        )
        """
    ),
    markdown("## Conservative vacancy-lag models\n\nEvery lag specification uses the same rows. The break handling below preserves the archived notebook's conservative common-sample design, with 2010 already excluded upstream.\n"),
    code(
        """
        lag_df = panel_clean.sort_values(["cbsa", "year"]).copy()
        lag_df["previous_year"] = lag_df.groupby("cbsa")["year"].shift()
        lag_df["two_years_prior"] = lag_df.groupby("cbsa")["year"].shift(2)
        lag_df["vacancy_lag1"] = lag_df.groupby("cbsa")["vacancy_rate"].shift(1)
        lag_df["vacancy_lag2"] = lag_df.groupby("cbsa")["vacancy_rate"].shift(2)

        lag_df.loc[lag_df["year"] - lag_df["previous_year"] != 1, "vacancy_lag1"] = np.nan
        lag_df.loc[lag_df["year"] - lag_df["two_years_prior"] != 2, "vacancy_lag2"] = np.nan

        delineation_breaks = {2010, 2013, 2019, 2023}
        follows_delineation_break = lag_df["previous_year"].isin(delineation_breaks)
        lag_df.loc[
            lag_df["year"].isin(delineation_breaks),
            ["household_growth", "housing_unit_growth"],
        ] = np.nan
        lag_df.loc[follows_delineation_break, "vacancy_lag2"] = np.nan

        lag_sample = lag_df.dropna(subset=["household_growth", "vacancy_lag1", "vacancy_lag2"]).copy()
        vacancy_fe_only = smf.ols("household_growth ~ C(year) + C(cbsa)", data=lag_sample).fit()
        vacancy_lag1_model = smf.ols(
            "household_growth ~ vacancy_lag1 + C(year) + C(cbsa)", data=lag_sample
        ).fit(cov_type="cluster", cov_kwds={"groups": lag_sample["cbsa"]})
        vacancy_lag2_model = smf.ols(
            "household_growth ~ vacancy_lag2 + C(year) + C(cbsa)", data=lag_sample
        ).fit(cov_type="cluster", cov_kwds={"groups": lag_sample["cbsa"]})
        vacancy_both_model = smf.ols(
            "household_growth ~ vacancy_lag1 + vacancy_lag2 + C(year) + C(cbsa)",
            data=lag_sample,
        ).fit(cov_type="cluster", cov_kwds={"groups": lag_sample["cbsa"]})

        def partial_r_squared(base, full):
            return (base.ssr - full.ssr) / base.ssr

        vacancy_table = compact_model_table(
            {"lag 1": vacancy_lag1_model, "lag 2": vacancy_lag2_model, "both lags": vacancy_both_model},
            ["vacancy_lag1", "vacancy_lag2"],
        )
        vacancy_table["partial_r_squared_vs_fe"] = [
            partial_r_squared(vacancy_fe_only, vacancy_lag1_model),
            partial_r_squared(vacancy_fe_only, vacancy_lag2_model),
            partial_r_squared(vacancy_fe_only, vacancy_both_model),
            partial_r_squared(vacancy_fe_only, vacancy_both_model),
        ]
        vacancy_table
        """
    ),
    markdown("## Vacancy reparameterization and trimming\n"),
    code(
        """
        lag_sample["vacancy_change"] = lag_sample["vacancy_lag1"] - lag_sample["vacancy_lag2"]
        vacancy_change_model = smf.ols(
            "household_growth ~ vacancy_lag2 + vacancy_change + C(year) + C(cbsa)", data=lag_sample
        ).fit(cov_type="cluster", cov_kwds={"groups": lag_sample["cbsa"]})

        vacancy_lo, vacancy_hi = lag_sample["vacancy_change"].quantile([0.01, 0.99])
        growth_lo, growth_hi = lag_sample["household_growth"].quantile([0.01, 0.99])
        trimmed_lag_sample = lag_sample[
            lag_sample["vacancy_change"].between(vacancy_lo, vacancy_hi)
            & lag_sample["household_growth"].between(growth_lo, growth_hi)
        ].copy()
        trimmed_change_model = smf.ols(
            "household_growth ~ vacancy_lag2 + vacancy_change + C(year) + C(cbsa)", data=trimmed_lag_sample
        ).fit(cov_type="cluster", cov_kwds={"groups": trimmed_lag_sample["cbsa"]})

        compact_model_table(
            {"full sample": vacancy_change_model, "trimmed sample": trimmed_change_model},
            ["vacancy_lag2", "vacancy_change"],
        )
        """
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.13"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")
print(f"Wrote {OUTPUT}")
