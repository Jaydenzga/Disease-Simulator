import pytest

from disease_sim.interventions import apply_vaccination
from disease_sim.models import simulate
from disease_sim.parameters import (
    DiseaseParams,
    ModelType,
    SimulationConfig,
    Vaccination,
    VaccineModel,
)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"population": 0, "initial_infected": 0, "days": 10}, "population"),
        ({"population": 100, "initial_infected": -1, "days": 10}, "initial_infected"),
        ({"population": 100, "initial_infected": 101, "days": 10}, "cannot exceed"),
        ({"population": 100, "initial_infected": 1, "days": 0}, "days"),
        ({"population": 100, "initial_infected": 1, "days": 2.5}, "days"),
        ({"population": 100, "initial_infected": 1, "days": 10, "steps_per_day": 0}, "steps"),
        ({"population": 100, "initial_infected": 1, "days": 10, "steps_per_day": 1.5}, "steps"),
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


NON_FINITE = [float("nan"), float("inf"), float("-inf")]


@pytest.mark.parametrize("value", NON_FINITE)
@pytest.mark.parametrize(
    "build, field",
    [
        (lambda x: SimulationConfig(x, 1, 10), "population"),
        (lambda x: SimulationConfig(100, x, 10), "initial_infected"),
        (lambda x: SimulationConfig(100, 1, x), "days"),
        (lambda x: SimulationConfig(100, 1, 10, x), "steps_per_day"),
        (lambda x: DiseaseParams(x, 0.1), "infection_rate"),
        (lambda x: DiseaseParams(0.1, x), "recovery_rate"),
        (lambda x: DiseaseParams(0.1, 0.1, x), "progression_rate"),
        (lambda x: DiseaseParams.from_r0(x, 10), "r0"),
        (lambda x: DiseaseParams.from_r0(2, x), "infectious_period"),
        (lambda x: DiseaseParams.from_r0(2, 10, x), "latent_period"),
        (lambda x: Vaccination(x, 0.5), "coverage"),
        (lambda x: Vaccination(0.5, x), "effectiveness"),
    ],
)
def test_non_finite_inputs_rejected(build, field, value):
    # NaN compares False to everything, so it must be caught explicitly rather
    # than relying on range checks; infinite days must not raise OverflowError.
    with pytest.raises(ValueError, match=f"{field} must be a finite number"):
        build(value)


def test_default_steps_per_day():
    assert SimulationConfig(100, 1, 10).steps_per_day == 4


@pytest.mark.parametrize("sigma", [0.0, -0.2])
def test_progression_rate_must_be_positive(sigma):
    with pytest.raises(ValueError, match="progression_rate must be positive"):
        DiseaseParams(0.3, 0.1, sigma)


def test_model_type_accepts_string():
    assert DiseaseParams(0.3, 0.1, model="SEIR").model is ModelType.SEIR
    assert DiseaseParams(0.3, 0.1).model is ModelType.SIR


def test_from_r0_round_trip():
    disease = DiseaseParams.from_r0(2.5, infectious_period=10, latent_period=4, model="SEIR")
    assert disease.recovery_rate == pytest.approx(0.1)
    assert disease.infection_rate == pytest.approx(0.25)
    assert disease.progression_rate == pytest.approx(0.25)
    assert disease.basic_reproduction_number == pytest.approx(2.5)
    assert disease.mean_infectious_period == pytest.approx(10)
    assert disease.mean_latent_period == pytest.approx(4)
    assert disease.model is ModelType.SEIR


@pytest.mark.parametrize("period", [0, -5])
def test_from_r0_rejects_nonpositive_periods(period):
    with pytest.raises(ValueError, match="infectious_period must be positive"):
        DiseaseParams.from_r0(2, period)


def test_integer_valued_floats_are_accepted_as_integers():
    config = SimulationConfig(1000, 2, 30.0, 4.0)
    assert (config.days, config.steps_per_day) == (30, 4)
    assert isinstance(config.days, int) and isinstance(config.steps_per_day, int)
    results = simulate(config, DiseaseParams(0.3, 0.1))
    assert len(results) == 31
