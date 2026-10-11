import io
from dataclasses import replace

import pandas as pd
import pytest

from disease_sim import explain
from disease_sim.export import RESULT_COLUMNS, results_csv, summary_csv
from disease_sim.metrics import summarize
from disease_sim.models import STEP_ERROR_TOLERANCE, simulate
from disease_sim.parameters import (
    ContactReduction,
    DiseaseParams,
    SimulationConfig,
    Vaccination,
    VaccineModel,
)
from disease_sim.scenarios import default_scenarios, run_scenarios, summarize_scenarios

DISEASE = DiseaseParams.from_r0(2.5, 7.0)
CONFIG = SimulationConfig(10_000, 10, 365)
SCENARIOS = default_scenarios(Vaccination(0.3, 0.9), ContactReduction(0.3, 14))
RESULTS = run_scenarios(CONFIG, DISEASE, SCENARIOS)
TABLE = summarize_scenarios(RESULTS, DISEASE, SCENARIOS)


# --- CSV export ---------------------------------------------------------------


def test_results_csv_round_trips_through_pandas():
    data = results_csv(RESULTS)
    assert data.decode("utf-8").splitlines()[0] == "scenario,day,S,E,I,R,V"
    loaded = pd.read_csv(io.BytesIO(data))
    assert list(loaded.columns) == RESULT_COLUMNS
    pd.testing.assert_frame_equal(loaded, RESULTS[RESULT_COLUMNS], check_exact=False, rtol=1e-12)


def test_results_csv_of_one_scenario():
    one = RESULTS[RESULTS["scenario"] == SCENARIOS[0].name]
    loaded = pd.read_csv(io.BytesIO(results_csv(one)))
    assert len(loaded) == CONFIG.days + 1
    assert set(loaded["scenario"]) == {SCENARIOS[0].name}


def test_results_csv_requires_the_scenario_column():
    with pytest.raises(ValueError, match="scenario"):
        results_csv(simulate(CONFIG, DISEASE))


def test_summary_csv_has_one_row_per_scenario():
    loaded = pd.read_csv(io.BytesIO(summary_csv(TABLE)))
    assert loaded.columns[0] == "scenario"
    assert list(loaded["scenario"]) == [s.name for s in SCENARIOS]
    assert loaded["attack_rate"].between(0, 1).all()
    assert list(loaded["peak_infectious"]) == pytest.approx(list(TABLE["peak_infectious"]))


# --- Run summary ---------------------------------------------------------------


def _summary(**changes):
    base = summarize(RESULTS[RESULTS["scenario"] == SCENARIOS[0].name], DISEASE)
    return replace(base, **changes)


def test_run_summary_reports_peak_and_total():
    summary = _summary(
        peak_infectious=2364.6,
        peak_day=35,
        cumulative_infections=8930.2,
        attack_rate=0.89302,
        still_infected_at_end=False,
    )
    text = explain.run_summary(summary, 10_000, 365)
    assert "peak on day 35, when 2,365 people (23.6% of the population)" in text
    assert "By day 365, 8,930 people (89.3% of the population) have been infected" in text
    assert text.endswith("The outbreak is over by day 365.")


def test_run_summary_warns_when_unfinished():
    text = explain.run_summary(_summary(still_infected_at_end=True), 10_000, 100)
    assert "not over by day 100" in text
    assert "final total will be higher" in text


def test_run_summary_when_infections_only_fall():
    summary = _summary(peak_infectious=10.0, peak_day=0, cumulative_infections=12.4)
    text = explain.run_summary(summary, 10_000, 365)
    assert "never rises above the starting 10 people" in text
    assert "12 people" in text


def test_run_summary_tiny_counts():
    summary = _summary(peak_infectious=0.3, peak_day=0, cumulative_infections=1.0)
    text = explain.run_summary(summary, 100, 10)
    assert "fewer than 1 person" in text
    assert "1 person (" in text


# --- Status messages -------------------------------------------------------------


def test_step_error_within_tolerance():
    ok, text = explain.step_error_message(0.039, 4, [1, 4, 10, 20, 50])
    assert ok
    assert "about 3.9% of the peak" in text
    assert f"{STEP_ERROR_TOLERANCE:.0%} limit" in text


@pytest.mark.parametrize(
    "error, steps, advice",
    [
        (0.20, 4, "choose at least 20 steps per day"),
        (2.00, 4, "choose the most accurate setting"),
        (0.20, 50, "Even the most accurate setting is approximate"),
    ],
)
def test_step_error_advice(error, steps, advice):
    ok, text = explain.step_error_message(error, steps, [1, 4, 10, 20, 50])
    assert not ok
    assert advice in text


def test_outbreak_status():
    ok, text = explain.outbreak_status_message([], 365)
    assert ok and "over by day 365" in text
    ok, text = explain.outbreak_status_message(["A", "B"], 200)
    assert not ok
    assert "day 200 in: A, B." in text


# --- Text coverage -----------------------------------------------------------------


def test_every_vaccine_model_has_a_caption():
    assert set(explain.VACCINATED_CAPTIONS) == set(VaccineModel)


def test_statistics_text_rules_out_uncertainty():
    assert "not uncertainty across possible outbreaks" in explain.STATISTICS_SCOPE
    titles = [title for title, _ in explain.THREE_KINDS]
    assert titles == [
        "Model results: deterministic",
        "Numerical error: estimated",
        "Statistical uncertainty: not modeled",
    ]


def test_every_summary_metric_shown_has_help():
    shown = set(TABLE.columns) - {
        "basic_reproduction_number",
        "initial_effective_reproduction_number",
    }
    assert shown <= set(explain.METRIC_HELP)
