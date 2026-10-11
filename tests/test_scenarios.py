import pytest

from disease_sim.models import COMPARTMENTS, simulate
from disease_sim.parameters import ContactReduction, DiseaseParams, SimulationConfig, Vaccination
from disease_sim.scenarios import (
    COMBINED,
    CONTACT_REDUCTION_ONLY,
    NO_INTERVENTION,
    VACCINATION_ONLY,
    Scenario,
    default_scenarios,
    run_scenarios,
    summarize_scenarios,
)

CONFIG = SimulationConfig(1000, 2, 300)
DISEASE = DiseaseParams(0.3, 0.1, 0.2, "SEIR")
VACCINATION = Vaccination(0.4, 0.9)
CONTACT = ContactReduction(0.3, start_day=10)
SCENARIOS = default_scenarios(VACCINATION, CONTACT)


@pytest.fixture(scope="module")
def results():
    return run_scenarios(CONFIG, DISEASE, SCENARIOS)


@pytest.fixture(scope="module")
def table(results):
    return summarize_scenarios(results, DISEASE, SCENARIOS)


def test_default_scenarios():
    by_name = {s.name: s for s in SCENARIOS}
    assert list(by_name) == [NO_INTERVENTION, VACCINATION_ONLY, CONTACT_REDUCTION_ONLY, COMBINED]
    assert by_name[NO_INTERVENTION] == Scenario(NO_INTERVENTION)
    assert by_name[VACCINATION_ONLY].contact_reduction == ContactReduction()
    assert by_name[CONTACT_REDUCTION_ONLY].vaccination == Vaccination()
    assert by_name[COMBINED] == Scenario(COMBINED, VACCINATION, CONTACT)


def test_long_format(results):
    assert list(results.columns) == ["scenario", "day", *COMPARTMENTS]
    assert results["scenario"].unique().tolist() == [s.name for s in SCENARIOS]
    assert len(results) == len(SCENARIOS) * (CONFIG.days + 1)


def test_each_scenario_matches_a_direct_simulation(results):
    for s in SCENARIOS:
        direct = simulate(CONFIG, DISEASE, s.vaccination, s.contact_reduction)
        mine = results[results["scenario"] == s.name].drop(columns="scenario")
        assert mine.reset_index(drop=True).equals(direct)


def test_interventions_reduce_infections(table):
    infections = table["infections_during_simulation"]
    for name in (VACCINATION_ONLY, CONTACT_REDUCTION_ONLY):
        assert infections[name] < infections[NO_INTERVENTION]
        assert table.loc[name, "peak_infectious"] <= table.loc[NO_INTERVENTION, "peak_infectious"]
    assert infections[COMBINED] < min(
        infections[VACCINATION_ONLY], infections[CONTACT_REDUCTION_ONLY]
    )


def test_infections_averted_is_relative_to_baseline(table):
    assert table.loc[NO_INTERVENTION, "infections_averted"] == 0
    for name in table.index:
        assert table.loc[name, "infections_averted"] == pytest.approx(
            table.loc[NO_INTERVENTION, "cumulative_infections"]
            - table.loc[name, "cumulative_infections"]
        )


def test_shared_disease_means_shared_r0(table):
    assert table["basic_reproduction_number"].tolist() == pytest.approx([3] * len(SCENARIOS))
    assert table.loc[VACCINATION_ONLY, "initial_effective_reproduction_number"] < 3
    # The contact reduction starts on day 10, so it does not lower R_e at day 0.
    assert (
        table.loc[CONTACT_REDUCTION_ONLY, "initial_effective_reproduction_number"]
        == (table.loc[NO_INTERVENTION, "initial_effective_reproduction_number"])
    )


@pytest.mark.parametrize(
    "scenarios, message",
    [([], "at least one"), ([Scenario("a"), Scenario("a")], "unique")],
)
def test_scenario_names_validated(scenarios, message):
    with pytest.raises(ValueError, match=message):
        run_scenarios(CONFIG, DISEASE, scenarios)
