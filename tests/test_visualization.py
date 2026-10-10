import pytest

from disease_sim.models import simulate_sir
from disease_sim.parameters import DiseaseParams, SimulationConfig, VaccineModel
from disease_sim.visualization import compartment_figure

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
