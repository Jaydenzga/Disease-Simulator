import math

import pandas as pd
import pytest

from disease_sim.metrics import initial_effective_reproduction_number, summarize
from disease_sim.models import simulate
from disease_sim.parameters import (
    ContactReduction,
    DiseaseParams,
    SimulationConfig,
    Vaccination,
    VaccineModel,
)

DISEASE = DiseaseParams(0.3, 0.1)


def hand_built(infectious, susceptible, exposed=None, vaccinated=None, n=100):
    days = len(infectious)
    exposed = exposed or [0.0] * days
    vaccinated = vaccinated or [0.0] * days
    recovered = [
        n - s - e - i - v
        for s, e, i, v in zip(susceptible, exposed, infectious, vaccinated, strict=True)
    ]
    return pd.DataFrame(
        {
            "day": range(days),
            "S": susceptible,
            "E": exposed,
            "I": infectious,
            "R": recovered,
            "V": vaccinated,
        }
    )


def test_descriptive_statistics_by_hand():
    results = hand_built([2, 6, 10, 4, 3], [98, 92, 85, 85, 85])
    summary = summarize(results, DISEASE)
    assert summary.peak_infectious == 10
    assert summary.peak_day == 2
    assert summary.mean_infectious == pytest.approx(25 / 5)
    assert summary.median_infectious == 4
    # Deviations from the mean 5: -3, 1, 5, -1, -2; squares sum to 40; divide by n = 5.
    assert summary.sd_infectious == pytest.approx(math.sqrt(40 / 5))


def test_median_of_even_length_series_averages_the_middle_two():
    summary = summarize(hand_built([1, 2, 6, 9], [99, 98, 94, 91]), DISEASE)
    assert summary.median_infectious == pytest.approx(4)


def test_peak_day_is_the_first_day_of_a_tied_maximum():
    summary = summarize(hand_built([2, 7, 7, 3], [98, 93, 93, 93]), DISEASE)
    assert summary.peak_day == 1


def test_constant_series_has_zero_spread():
    summary = summarize(hand_built([5, 5, 5], [95, 95, 95]), DISEASE)
    assert summary.sd_infectious == 0
    assert summary.mean_infectious == summary.median_infectious == 5


def test_infection_counts_distinguish_initial_cases():
    results = hand_built([2, 6, 10, 4, 3], [98, 92, 85, 85, 85])
    summary = summarize(results, DISEASE)
    assert summary.infections_during_simulation == pytest.approx(13)
    assert summary.cumulative_infections == pytest.approx(15)  # 2 initially infected + 13
    assert summary.attack_rate == pytest.approx(15 / 100)


def test_breakthrough_infections_and_exposed_are_counted():
    # 4 leave S and 3 leave V (breakthrough); 5 of them are still in E at the end.
    results = hand_built(
        infectious=[1, 2],
        susceptible=[50, 46],
        exposed=[0, 5],
        vaccinated=[40, 37],
    )
    summary = summarize(results, DISEASE)
    assert summary.infections_during_simulation == pytest.approx(7)
    assert summary.cumulative_infections == pytest.approx(8)


@pytest.mark.parametrize(
    "infectious, exposed, expected",
    [([5, 0.4], [0, 0.5], False), ([5, 0.6], [0, 0.5], True), ([5, 3], None, True)],
)
def test_still_infected_at_end(infectious, exposed, expected):
    results = hand_built(infectious, [95, 95], exposed=exposed)
    assert summarize(results, DISEASE).still_infected_at_end is expected


@pytest.mark.parametrize(
    "vaccination, contact_reduction, expected",
    [
        (Vaccination(), ContactReduction(), 3 * 998 / 1000),
        (Vaccination(0.5, 0.8), ContactReduction(), 3 * (998 - 0.4 * 998) / 1000),
        # Leaky: all 998 vaccinated, each with a 20% relative risk.
        (Vaccination(1.0, 0.8, VaccineModel.LEAKY), ContactReduction(), 3 * 0.2 * 998 / 1000),
        (Vaccination(), ContactReduction(0.5), 3 * 0.5 * 998 / 1000),
        # A reduction that starts later does not change R_e at day 0.
        (Vaccination(), ContactReduction(0.5, start_day=10), 3 * 998 / 1000),
    ],
)
def test_initial_effective_reproduction_number(vaccination, contact_reduction, expected):
    results = simulate(SimulationConfig(1000, 2, 5), DISEASE, vaccination, contact_reduction)
    re = initial_effective_reproduction_number(results, DISEASE, vaccination, contact_reduction)
    assert re == pytest.approx(expected)


def test_initial_re_handles_no_recovery():
    no_recovery = DiseaseParams(0.3, 0.0)
    results = simulate(SimulationConfig(1000, 2, 5), no_recovery)
    assert initial_effective_reproduction_number(results, no_recovery) == math.inf
    immune = simulate(SimulationConfig(1000, 2, 5), no_recovery, Vaccination(1.0, 1.0))
    assert initial_effective_reproduction_number(immune, no_recovery, Vaccination(1.0, 1.0)) == 0


@pytest.mark.parametrize("beta, grows", [(0.08, False), (0.3, True)])
def test_initial_re_predicts_whether_infections_grow(beta, grows):
    disease = DiseaseParams(beta, 0.1)
    summary = summarize(simulate(SimulationConfig(1000, 2, 200), disease), disease)
    assert (summary.initial_effective_reproduction_number > 1) is grows
    assert (summary.peak_day > 0) is grows


def test_summary_of_a_simulation_is_consistent():
    results = simulate(SimulationConfig(1000, 2, 400), DISEASE)
    summary = summarize(results, DISEASE)
    last = results.iloc[-1]
    # At the end of a finished epidemic, everyone ever infected has recovered.
    assert not summary.still_infected_at_end
    assert summary.cumulative_infections == pytest.approx(last["R"] + last["I"], abs=1e-6)
    assert summary.basic_reproduction_number == pytest.approx(3)
