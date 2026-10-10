import pytest

from disease_sim.interventions import apply_vaccination
from disease_sim.parameters import DiseaseParams, SimulationConfig, Vaccination, VaccineModel


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"population": 0, "initial_infected": 0, "days": 10}, "population"),
        ({"population": 100, "initial_infected": -1, "days": 10}, "initial_infected"),
        ({"population": 100, "initial_infected": 101, "days": 10}, "cannot exceed"),
        ({"population": 100, "initial_infected": 1, "days": 0}, "days"),
        ({"population": 100, "initial_infected": 1, "days": 2.5}, "days"),
    ],
)
def test_invalid_config(kwargs, message):
    with pytest.raises(ValueError, match=message):
        SimulationConfig(**kwargs)


@pytest.mark.parametrize("beta, gamma", [(-0.1, 0.1), (0.1, -0.1)])
def test_negative_rates_rejected(beta, gamma):
    with pytest.raises(ValueError, match="nonnegative"):
        DiseaseParams(beta, gamma)


@pytest.mark.parametrize("coverage, effectiveness", [(-0.1, 0.5), (1.1, 0.5), (0.5, 1.5)])
def test_vaccination_fractions_validated(coverage, effectiveness):
    with pytest.raises(ValueError, match="between 0 and 1"):
        Vaccination(coverage, effectiveness)


def test_vaccine_model_accepts_string():
    assert Vaccination(model="leaky").model is VaccineModel.LEAKY
    with pytest.raises(ValueError):
        Vaccination(model="nonsense")


def test_r0():
    assert DiseaseParams(0.3, 0.1).basic_reproduction_number == pytest.approx(3.0)
    assert DiseaseParams(0.3, 0.0).basic_reproduction_number == float("inf")


def test_apply_vaccination_susceptibility():
    aon = apply_vaccination(100, Vaccination(0.5, 0.8, VaccineModel.ALL_OR_NOTHING))
    leaky = apply_vaccination(100, Vaccination(0.5, 0.8, VaccineModel.LEAKY))
    assert (aon.susceptible, aon.vaccinated, aon.susceptibility) == pytest.approx((60, 40, 0))
    assert (leaky.susceptible, leaky.vaccinated, leaky.susceptibility) == pytest.approx(
        (50, 50, 0.2)
    )
