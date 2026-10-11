import itertools

import pytest

from disease_sim.interventions import contact_multiplier
from disease_sim.models import COMPARTMENTS, simulate
from disease_sim.parameters import (
    ContactReduction,
    DiseaseParams,
    ModelType,
    SimulationConfig,
    Vaccination,
)


def test_contact_multiplier_window():
    cr = ContactReduction(0.4, start_day=10, end_day=20)
    assert contact_multiplier(9.75, cr) == 1.0
    assert contact_multiplier(10, cr) == pytest.approx(0.6)
    assert contact_multiplier(19.75, cr) == pytest.approx(0.6)
    assert contact_multiplier(20, cr) == 1.0  # the end day itself is unrestricted


def test_contact_reduction_without_end_never_lifts():
    assert contact_multiplier(1e6, ContactReduction(0.5, start_day=3)) == 0.5


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"reduction": 1.2}, "between 0 and 1"),
        ({"reduction": float("nan")}, "reduction must be a finite number"),
        ({"reduction": 0.5, "start_day": -1}, "nonnegative"),
        ({"reduction": 0.5, "start_day": float("inf")}, "start_day must be a finite number"),
        ({"reduction": 0.5, "start_day": 10, "end_day": 10}, "must be after"),
        ({"reduction": 0.5, "end_day": float("nan")}, "end_day must be a finite number"),
    ],
)
def test_contact_reduction_validation(kwargs, message):
    with pytest.raises(ValueError, match=message):
        ContactReduction(**kwargs)


@pytest.mark.parametrize("model", list(ModelType))
def test_permanent_reduction_from_day_0_equals_lower_beta(model):
    config = SimulationConfig(1000, 2, 200)
    reduced = simulate(
        config, DiseaseParams(0.3, 0.1, 0.2, model), contact_reduction=ContactReduction(0.4)
    )
    lower_beta = simulate(config, DiseaseParams(0.3 * (1 - 0.4), 0.1, 0.2, model))
    assert reduced.equals(lower_beta)


@pytest.mark.parametrize("steps", [1, 4])
def test_results_match_baseline_until_reduction_starts(steps):
    config, disease = SimulationConfig(1000, 2, 100, steps), DiseaseParams(0.3, 0.1)
    baseline = simulate(config, disease)
    reduced = simulate(config, disease, contact_reduction=ContactReduction(0.5, start_day=30))
    assert reduced.iloc[:31].equals(baseline.iloc[:31])
    assert reduced["S"].iloc[31] > baseline["S"].iloc[31]


@pytest.mark.parametrize("model", list(ModelType))
@pytest.mark.parametrize("start_day", [0, 20])
def test_unending_reduction_never_worsens_the_outbreak(model, start_day):
    config, disease = SimulationConfig(1000, 2, 400), DiseaseParams(0.3, 0.1, 0.2, model)
    baseline = simulate(config, disease)
    reduced = simulate(config, disease, contact_reduction=ContactReduction(0.3, start_day))
    assert reduced["I"].max() <= baseline["I"].max()
    assert reduced["S"].iloc[-1] >= baseline["S"].iloc[-1]


def test_lifting_restrictions_early_causes_a_rebound():
    # During the reduction R_e = 3 * 0.3 = 0.9 < 1, so infections shrink while
    # nearly everyone stays susceptible; once lifted, R_e is back near 3.
    results = simulate(
        SimulationConfig(1000, 10, 300),
        DiseaseParams(0.3, 0.1),
        contact_reduction=ContactReduction(0.7, start_day=0, end_day=60),
    )
    infectious = results["I"]
    assert infectious.iloc[60] < infectious.iloc[0]
    assert infectious.iloc[60:].max() > 10 * infectious.iloc[60]
    totals = results[COMPARTMENTS].sum(axis=1)
    assert (abs(totals - 1000) < 1e-9 * 1000).all()


GRID = list(
    itertools.product(
        list(ModelType),
        [0.3, 3.0],  # infection rate
        [0.0, 0.5, 1.0],  # reduction
        [(0, None), (5, 40)],  # (start_day, end_day)
        [1, 4],  # steps per day
    )
)


@pytest.mark.parametrize("model, beta, reduction, window, steps", GRID)
def test_conservation_with_contact_reduction(model, beta, reduction, window, steps):
    results = simulate(
        SimulationConfig(1000, 5, 100, steps),
        DiseaseParams(beta, 0.5, 0.5, model),
        Vaccination(0.5, 0.5, "leaky"),
        ContactReduction(reduction, *window),
    )
    totals = results[COMPARTMENTS].sum(axis=1)
    assert (abs(totals - 1000) < 1e-9 * 1000).all()
    assert (results[COMPARTMENTS] >= 0).all().all()
