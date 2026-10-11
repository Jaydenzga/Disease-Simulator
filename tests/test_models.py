import itertools
import math

import pytest

from disease_sim.models import (
    COMPARTMENTS,
    estimate_step_error,
    simulate,
    simulate_sir,
    steps_for_tolerance,
)
from disease_sim.parameters import (
    LEGACY_STEPS_PER_DAY,
    DiseaseParams,
    ModelType,
    SimulationConfig,
    Vaccination,
    VaccineModel,
)


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
    config = SimulationConfig(population, infected, days, steps_per_day=LEGACY_STEPS_PER_DAY)
    results = simulate_sir(config, DiseaseParams(beta, gamma))
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
    assert results.iloc[0][["S", "E", "I", "R", "V"]].tolist() == [998, 0, 2, 0, 0]
    assert (results["E"] == 0).all()  # SIR has no latent stage


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


def _all_vaccinated_leaky(days):
    """Everyone susceptible is vaccinated, so every new infection is a breakthrough."""
    return simulate_sir(
        SimulationConfig(1000, 10, days, steps_per_day=LEGACY_STEPS_PER_DAY),
        DiseaseParams(0.4, 0.1),
        Vaccination(1.0, 0.5, VaccineModel.LEAKY),
    )


def test_breakthrough_infections_enter_infected():
    results = _all_vaccinated_leaky(1)
    day0, day1 = results.iloc[0], results.iloc[1]
    assert day0["S"] == 0 and day0["V"] == 990

    breakthrough = 0.4 * 10 / 1000 * (1 - 0.5) * 990
    assert day0["V"] - day1["V"] == pytest.approx(breakthrough)
    assert day1["I"] == pytest.approx(10 + breakthrough - 0.1 * 10)
    # Only people who were already infectious can have recovered.
    assert day1["R"] == pytest.approx(0.1 * 10)


def test_breakthrough_infections_can_drive_an_outbreak():
    # beta * (1 - e) = 0.2 > gamma = 0.1, so infections grow with no unvaccinated people.
    results = _all_vaccinated_leaky(200)
    assert results["I"].max() > results["I"].iloc[0]
    assert (results["S"] == 0).all()
    # Everyone who left V was infected and is now in I or R.
    left_v = results["V"].iloc[0] - results["V"].iloc[-1]
    infected_ever = results["I"].iloc[-1] + results["R"].iloc[-1] - results["I"].iloc[0]
    assert left_v == pytest.approx(infected_ever)


@pytest.mark.parametrize("model", list(VaccineModel))
def test_higher_effectiveness_means_fewer_infections(model):
    config, disease = SimulationConfig(1000, 2, 300), DiseaseParams(0.3, 0.1)
    ever_infected = [
        simulate_sir(config, disease, Vaccination(0.6, e, model))[["I", "R"]].iloc[-1].sum()
        for e in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    assert all(a > b for a, b in itertools.pairwise(ever_infected))


def final_size_fraction(r0, initial_susceptible_fraction):
    """Fraction of N ever infected, from the Kermack-McKendrick final-size relation.

    With no one recovered at the start, S_inf satisfies
    S_inf / N = (S0 / N) * exp(-R0 * (1 - S_inf / N)). Fixed-point iteration
    converges to the epidemic root because R0 * S_inf / N < 1 there.
    """
    s = 0.0
    for _ in range(10_000):
        s = initial_susceptible_fraction * math.exp(-r0 * (1 - s))
    return 1 - s


def _final_size_error(beta, gamma, steps_per_day):
    n, i0 = 1000, 1
    results = simulate(SimulationConfig(n, i0, 600, steps_per_day), DiseaseParams(beta, gamma))
    exact = final_size_fraction(beta / gamma, (n - i0) / n)
    simulated = 1 - results["S"].iloc[-1] / n
    return abs(simulated - exact) / exact


@pytest.mark.parametrize("beta, gamma", [(0.3, 0.1), (0.5, 0.25), (0.05, 0.03)])
def test_final_size_matches_kermack_mckendrick(beta, gamma):
    assert _final_size_error(beta, gamma, steps_per_day=10) < 0.01


def test_more_steps_per_day_is_more_accurate():
    # Forward Euler is first order: error shrinks roughly in proportion to dt.
    errors = [_final_size_error(0.5, 0.25, k) for k in (1, 4, 10)]
    assert errors[0] > errors[1] > errors[2]


@pytest.mark.parametrize("steps_per_day", [1, 4, 10])
def test_output_is_daily_whatever_the_step_size(steps_per_day):
    results = simulate(SimulationConfig(1000, 2, 30, steps_per_day), DiseaseParams(0.3, 0.1))
    assert results["day"].tolist() == list(range(31))
    assert results.iloc[0][["S", "I"]].tolist() == [998, 2]


def test_one_step_per_day_and_four_differ_but_agree_closely():
    disease = DiseaseParams(0.3, 0.1)
    legacy = simulate(SimulationConfig(1000, 2, 100, 1), disease)
    default = simulate(SimulationConfig(1000, 2, 100), disease)
    assert not legacy.equals(default)
    assert (abs(legacy["I"] - default["I"]) < 0.05 * 1000).all()


# --- SEIR ---------------------------------------------------------------


def seir(beta, gamma, latent_period):
    return DiseaseParams(beta, gamma, 1 / latent_period, ModelType.SEIR)


SEIR_GRID = list(
    itertools.product(
        [0.0, 0.3, 3.0],  # infection rate
        [0.0, 0.1, 1.5],  # recovery rate
        [0.1, 5.0, 21.0],  # mean latent period (days); 0.1 makes sigma * dt > 1
        [(0.0, 1.0, VaccineModel.ALL_OR_NOTHING), (0.6, 0.5, VaccineModel.LEAKY)],
        [1, 4, 10],  # steps per day
    )
)


@pytest.mark.parametrize("beta, gamma, latent, vaccine, steps", SEIR_GRID)
def test_seir_conservation_and_nonnegativity(beta, gamma, latent, vaccine, steps):
    n = 1000
    results = simulate(
        SimulationConfig(n, 5, 150, steps), seir(beta, gamma, latent), Vaccination(*vaccine)
    )
    totals = results[COMPARTMENTS].sum(axis=1)
    assert (abs(totals - n) < 1e-9 * n).all()
    assert (results[COMPARTMENTS] >= 0).all().all()


def test_seir_starts_with_nobody_exposed():
    results = simulate(SimulationConfig(1000, 2, 10), seir(0.3, 0.1, 5))
    assert results.iloc[0][["S", "E", "I", "R", "V"]].tolist() == [998, 0, 2, 0, 0]
    assert results["E"].iloc[1:].gt(0).all()


def test_seir_one_step_by_hand():
    s0, e0, i0 = 998, 0, 2
    results = simulate(SimulationConfig(1000, i0, 2, 1), seir(0.3, 0.1, 5))
    infections = 0.3 * i0 / 1000 * s0
    day1 = results.iloc[1]
    assert day1["S"] == pytest.approx(s0 - infections)
    assert day1["E"] == pytest.approx(e0 + infections)  # nobody was exposed to progress yet
    assert day1["I"] == pytest.approx(i0 - 0.1 * i0)
    assert day1["R"] == pytest.approx(0.1 * i0)
    # Day 2: a fifth of the exposed become infectious.
    day2 = results.iloc[2]
    assert day2["I"] == pytest.approx(day1["I"] + 0.2 * day1["E"] - 0.1 * day1["I"])


def test_seir_leaky_breakthrough_enters_exposed():
    results = simulate(
        SimulationConfig(1000, 10, 1, 1), seir(0.4, 0.1, 5), Vaccination(1.0, 0.5, "leaky")
    )
    day0, day1 = results.iloc[0], results.iloc[1]
    breakthrough = 0.4 * 10 / 1000 * (1 - 0.5) * 990
    assert day0["V"] - day1["V"] == pytest.approx(breakthrough)
    assert day1["E"] == pytest.approx(breakthrough)
    assert day1["I"] == pytest.approx(10 - 0.1 * 10)


@pytest.mark.parametrize("beta, gamma", [(0.3, 0.1), (0.5, 0.25)])
def test_seir_final_size_matches_kermack_mckendrick(beta, gamma):
    # The latent stage delays infections but does not change who is eventually infected.
    n, i0 = 1000, 1
    results = simulate(SimulationConfig(n, i0, 800, 10), seir(beta, gamma, 5))
    exact = final_size_fraction(beta / gamma, (n - i0) / n)
    assert abs(1 - results["S"].iloc[-1] / n - exact) / exact < 0.01


def test_latent_period_delays_and_flattens_the_peak():
    config = SimulationConfig(1000, 2, 300)
    sir = simulate(config, DiseaseParams(0.3, 0.1))
    delayed = simulate(config, seir(0.3, 0.1, 5))
    assert delayed["I"].idxmax() > sir["I"].idxmax()
    assert delayed["I"].max() < sir["I"].max()


def test_seir_approaches_sir_as_latent_period_shrinks():
    config = SimulationConfig(1000, 2, 300, 10)
    sir = simulate(config, DiseaseParams(0.3, 0.1))
    gaps = [
        (simulate(config, seir(0.3, 0.1, latent))["I"] - sir["I"]).abs().max()
        for latent in (4, 2, 1, 0.5, 0.25, 0.1)
    ]
    assert all(a > b for a, b in itertools.pairwise(gaps))
    assert gaps[-1] < 0.025 * 1000


# --- Threshold behavior (R_e < 1) ----------------------------------------

SUBCRITICAL = [
    # (disease, vaccination) with R_e(0) = R0 * (S0 + m * V0) / N below 1
    (DiseaseParams(0.08, 0.1), Vaccination()),
    (DiseaseParams(0.3, 0.1), Vaccination(0.8, 1.0)),
    (DiseaseParams(0.3, 0.1), Vaccination(1.0, 0.8, VaccineModel.LEAKY)),
]


def _initial_re(disease, results, vaccination):
    day0 = results.iloc[0]
    m = 0.0 if vaccination.model is VaccineModel.ALL_OR_NOTHING else 1 - vaccination.effectiveness
    n = day0[COMPARTMENTS].sum()
    return disease.basic_reproduction_number * (day0["S"] + m * day0["V"]) / n


@pytest.mark.parametrize("disease, vaccination", SUBCRITICAL)
def test_sir_infections_fall_from_day_0_when_re_below_1(disease, vaccination):
    results = simulate(SimulationConfig(1000, 10, 200), disease, vaccination)
    assert _initial_re(disease, results, vaccination) < 1
    assert results["I"].is_monotonic_decreasing


@pytest.mark.parametrize("model", list(ModelType))
@pytest.mark.parametrize("disease, vaccination", SUBCRITICAL)
def test_no_outbreak_when_re_below_1(disease, vaccination, model):
    # Each infected person causes fewer than one new infection on average, so
    # the outbreak dies out: summing the generations, total new infections
    # cannot exceed I0 * Re / (1 - Re). This holds for SEIR too, even though
    # SEIR's E + I is not guaranteed to fall at every instant.
    disease = DiseaseParams(disease.infection_rate, disease.recovery_rate, 0.2, model)
    i0 = 10
    results = simulate(SimulationConfig(1000, i0, 400), disease, vaccination)
    re = _initial_re(disease, results, vaccination)
    first, last = results.iloc[0], results.iloc[-1]
    new_infections = (first["S"] - last["S"]) + (first["V"] - last["V"])
    assert new_infections <= i0 * re / (1 - re) + 1e-9


# --- Step-size error estimate ---------------------------------------------


def _infected_curve_error(disease, steps):
    """True error of the infected curve vs. a near-exact run, relative to the peak."""
    reference = simulate(SimulationConfig(1000, 2, 200, 800), disease)
    coarse = simulate(SimulationConfig(1000, 2, 200, steps), disease)
    return (coarse["I"] - reference["I"]).abs().max() / reference["I"].max()


@pytest.mark.parametrize(
    "disease, steps",
    [
        (DiseaseParams(0.05, 0.03), 4),
        (DiseaseParams(0.5, 0.03), 4),
        (DiseaseParams.from_r0(3, 2), 10),
        (DiseaseParams.from_r0(4, 1), 20),
        (DiseaseParams(0.3, 0.1, 0.2, ModelType.SEIR), 1),
    ],
)
def test_step_doubling_estimate_tracks_true_error(disease, steps):
    coarse = simulate(SimulationConfig(1000, 2, 200, steps), disease)
    fine = simulate(SimulationConfig(1000, 2, 200, 2 * steps), disease)
    true_error = _infected_curve_error(disease, steps)
    assert estimate_step_error(coarse, fine) == pytest.approx(true_error, rel=0.15, abs=0.002)


@pytest.mark.parametrize(
    "disease",
    [DiseaseParams.from_r0(4, 1), DiseaseParams.from_r0(10, 1), DiseaseParams(0.5, 0.03)],
)
def test_recommended_steps_reach_the_tolerance(disease):
    # Fast rates at 4 steps/day give a large error; the recommended step count
    # (rounded up to a step count the app offers) brings it within 5%.
    coarse = simulate(SimulationConfig(1000, 2, 200, 4), disease)
    fine = simulate(SimulationConfig(1000, 2, 200, 8), disease)
    error = estimate_step_error(coarse, fine)
    assert error > 0.05
    needed = steps_for_tolerance(4, error)
    offered = min(k for k in (1, 4, 10, 20, 50) if k >= min(needed, 50))
    assert _infected_curve_error(disease, offered) < 0.05


def test_step_error_is_zero_without_infection():
    flat = simulate(SimulationConfig(1000, 0, 10), DiseaseParams(0.3, 0.1))
    assert estimate_step_error(flat, flat) == 0.0


def test_steps_for_tolerance():
    assert steps_for_tolerance(4, 0.075) == 6
    assert steps_for_tolerance(4, 0.01) == 1
