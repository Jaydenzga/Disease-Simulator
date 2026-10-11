import pytest

from disease_sim.models import simulate, simulate_sir
from disease_sim.parameters import (
    ContactReduction,
    DiseaseParams,
    ModelType,
    SimulationConfig,
    Vaccination,
    VaccineModel,
)
from disease_sim.scenarios import default_scenarios, run_scenarios
from disease_sim.visualization import compartment_figure, scenario_comparison_figure

RESULTS = simulate_sir(SimulationConfig(1000, 2, 30), DiseaseParams(0.3, 0.1))


@pytest.mark.parametrize(
    "model, vaccinated_label",
    [
        (VaccineModel.ALL_OR_NOTHING, "Vaccinated (immune)"),
        (VaccineModel.LEAKY, "Vaccinated (not yet infected)"),
    ],
)
def test_legend_labels(model, vaccinated_label):
    ax = compartment_figure(RESULTS, model).axes[0]
    labels = [text.get_text() for text in ax.get_legend().get_texts()]
    assert labels == ["Infected", "Recovered", "Susceptible", vaccinated_label]


def test_each_line_plots_its_compartment():
    ax = compartment_figure(RESULTS).axes[0]
    by_label = {line.get_label(): line.get_ydata() for line in ax.get_lines()}
    for column, label in [("I", "Infected"), ("R", "Recovered"), ("S", "Susceptible")]:
        assert list(by_label[label]) == list(RESULTS[column])
    assert list(by_label["Vaccinated (immune)"]) == list(RESULTS["V"])


def test_sir_chart_has_no_exposed_line():
    ax = compartment_figure(RESULTS).axes[0]
    assert ax.get_title() == "Disease Spread (SIR Model)"
    assert not any(line.get_label().startswith("Exposed") for line in ax.get_lines())


def test_seir_chart_shows_exposed():
    results = simulate(SimulationConfig(1000, 2, 30), DiseaseParams(0.3, 0.1, 0.2, "SEIR"))
    ax = compartment_figure(results, model=ModelType.SEIR).axes[0]
    by_label = {line.get_label(): line.get_ydata() for line in ax.get_lines()}
    assert ax.get_title() == "Disease Spread (SEIR Model)"
    assert list(by_label["Exposed (not yet infectious)"]) == list(results["E"])


def test_scenario_comparison_plots_infected_for_each_scenario():
    scenarios = default_scenarios(Vaccination(0.5, 0.9), ContactReduction(0.3))
    results = run_scenarios(SimulationConfig(1000, 2, 60), DiseaseParams(0.3, 0.1), scenarios)
    ax = scenario_comparison_figure(results).axes[0]
    by_label = {line.get_label(): list(line.get_ydata()) for line in ax.get_lines()}
    assert list(by_label) == [s.name for s in scenarios]
    for s in scenarios:
        assert by_label[s.name] == results.loc[results["scenario"] == s.name, "I"].tolist()
    assert ax.get_ylabel() == "People infected"
