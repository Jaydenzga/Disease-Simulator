import itertools

import pytest

from disease_sim.models import COMPARTMENTS, simulate_sir
from disease_sim.parameters import DiseaseParams, SimulationConfig, Vaccination, VaccineModel


def original_main_py(population, infected, infection_rate, recovery_rate, days):
    """The simulation loop from the original single-file main.py, verbatim in behavior."""
    recovered = 0
    suseptible = population - infected
    infected_list, suseptible_list, recovered_list = [], [], []
    for _ in range(days):
        new_infections = (infected * infection_rate) * (suseptible / population)
        new_recoveries = infected * recovery_rate
        suseptible -= new_infections
        infected = infected + new_infections - new_recoveries
        recovered += new_recoveries
        infected_list.append(infected)
        suseptible_list.append(suseptible)
        recovered_list.append(recovered)
    return suseptible_list, infected_list, recovered_list


@pytest.mark.parametrize(
    "population, infected, beta, gamma, days",
    [
        (1000, 2, 0.05, 0.03, 30),  # original defaults
        (10000, 100, 0.5, 0.01, 200),
        (100, 1, 0.3, 0.1, 100),
    ],
)
def test_matches_original_main_py(population, infected, beta, gamma, days):
    results = simulate_sir(SimulationConfig(population, infected, days), DiseaseParams(beta, gamma))
    s, i, r = original_main_py(population, infected, beta, gamma, days)
    after_day_0 = results.iloc[1:]
    assert after_day_0["S"].tolist() == pytest.approx(s, abs=1e-9)
    assert after_day_0["I"].tolist() == pytest.approx(i, abs=1e-9)
    assert after_day_0["R"].tolist() == pytest.approx(r, abs=1e-9)
    assert (results["V"] == 0).all()


def test_output_shape():
    results = simulate_sir(SimulationConfig(1000, 2, 30), DiseaseParams(0.05, 0.03))
    assert list(results.columns) == ["day", *COMPARTMENTS]
    assert results["day"].tolist() == list(range(31))
    assert results.iloc[0][["S", "I", "R", "V"]].tolist() == [998, 2, 0, 0]


# Includes rates far beyond the slider maxima, where an uncapped Euler step
# would overshoot below zero.
GRID = list(
    itertools.product(
        [100, 10000],  # population
        [1, 50],  # initial infected
        [0.0, 0.05, 0.5, 3.0],  # infection rate
        [0.0, 0.03, 0.5, 1.5],  # recovery rate
        [0.0, 0.6, 1.0],  # coverage
        [0.0, 0.5, 1.0],  # effectiveness
        list(VaccineModel),
    )
)


@pytest.mark.parametrize("n, i0, beta, gamma, coverage, effectiveness, model", GRID)
def test_conservation_and_nonnegativity(n, i0, beta, gamma, coverage, effectiveness, model):
    results = simulate_sir(
        SimulationConfig(n, i0, 200),
        DiseaseParams(beta, gamma),
        Vaccination(coverage, effectiveness, model),
    )
    totals = results[COMPARTMENTS].sum(axis=1)
    assert (abs(totals - n) < 1e-9 * n).all()
    assert (results[COMPARTMENTS] >= 0).all().all()


def test_no_infected_means_nothing_changes():
    results = simulate_sir(SimulationConfig(1000, 0, 50), DiseaseParams(0.5, 0.1))
    assert (results["S"] == 1000).all()
    assert (results["I"] == 0).all()


def test_zero_infection_rate_only_recovers():
    results = simulate_sir(SimulationConfig(1000, 10, 50), DiseaseParams(0.0, 0.1))
    assert (results["S"] == 990).all()
    assert results["I"].is_monotonic_decreasing


@pytest.mark.parametrize("model", list(VaccineModel))
def test_vaccination_reduces_outbreak(model):
    config, disease = SimulationConfig(1000, 2, 200), DiseaseParams(0.3, 0.1)
    baseline = simulate_sir(config, disease)
    vaccinated = simulate_sir(config, disease, Vaccination(0.5, 0.8, model))
    assert vaccinated["I"].max() <= baseline["I"].max()
    assert vaccinated["R"].iloc[-1] <= baseline["R"].iloc[-1]


def test_all_or_nothing_initial_state():
    results = simulate_sir(
        SimulationConfig(1000, 2, 10),
        DiseaseParams(0.3, 0.1),
        Vaccination(0.5, 0.8, VaccineModel.ALL_OR_NOTHING),
    )
    day0 = results.iloc[0]
    assert day0["V"] == pytest.approx(0.5 * 0.8 * 998)
    assert day0["S"] == pytest.approx(998 - 0.5 * 0.8 * 998)
    # Immune people are never infected.
    assert (results["V"] == day0["V"]).all()


def test_leaky_initial_state_and_breakthrough():
    results = simulate_sir(
        SimulationConfig(1000, 2, 100),
        DiseaseParams(0.3, 0.1),
        Vaccination(0.5, 0.8, VaccineModel.LEAKY),
    )
    day0 = results.iloc[0]
    assert day0["V"] == pytest.approx(0.5 * 998)
    assert day0["S"] == pytest.approx(0.5 * 998)
    # Partially protected people can still be infected.
    assert results["V"].iloc[-1] < day0["V"]


def test_vaccine_models_agree_at_full_effectiveness():
    config, disease = SimulationConfig(1000, 2, 200), DiseaseParams(0.3, 0.1)
    a = simulate_sir(config, disease, Vaccination(0.4, 1.0, VaccineModel.ALL_OR_NOTHING))
    b = simulate_sir(config, disease, Vaccination(0.4, 1.0, VaccineModel.LEAKY))
    assert a.equals(b)


def test_full_vaccination_with_immunity_stops_spread():
    results = simulate_sir(
        SimulationConfig(1000, 2, 100),
        DiseaseParams(0.5, 0.1),
        Vaccination(1.0, 1.0),
    )
    assert (results["S"] == 0).all()
    assert results["I"].is_monotonic_decreasing
