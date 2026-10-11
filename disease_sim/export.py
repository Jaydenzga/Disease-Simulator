"""CSV export of simulation results and scenario summaries."""

import pandas as pd

from disease_sim.models import COMPARTMENTS

RESULT_COLUMNS = ["scenario", "day", *COMPARTMENTS]


def results_csv(results: pd.DataFrame) -> bytes:
    """Long-format results as UTF-8 CSV with columns scenario, day, S, E, I, R, V."""
    missing = [c for c in RESULT_COLUMNS if c not in results.columns]
    if missing:
        raise ValueError(f"results are missing columns {missing}")
    return results[RESULT_COLUMNS].to_csv(index=False).encode("utf-8")


def summary_csv(table: pd.DataFrame) -> bytes:
    """Scenario summary table (one row per scenario) as UTF-8 CSV.

    Attack rate stays a fraction (0-1), as in `metrics.Summary`.
    """
    return table.rename_axis("scenario").reset_index().to_csv(index=False).encode("utf-8")
