import plotly.graph_objects as go
import pytest

from disease_sim.metrics import summarize
from disease_sim.models import simulate, simulate_sir
from disease_sim.parameters import (
    ContactReduction,
    DiseaseParams,
    ModelType,
    SimulationConfig,
    Vaccination,
    VaccineModel,
)
from disease_sim.scenarios import default_scenarios, run_scenarios, summarize_scenarios
from disease_sim.visualization import (
    LOG_FLOOR,
    SCENARIO_STYLES,
    compartment_figure,
    daily_infected_distribution_figure,
    infected_statistics_figure,
    scenario_bar_figure,
    scenario_comparison_figure,
    scenario_style,
)

DISEASE = DiseaseParams(0.3, 0.1)
RESULTS = simulate_sir(SimulationConfig(1000, 2, 30), DISEASE)
SCENARIOS = default_scenarios(Vaccination(0.5, 0.9), ContactReduction(0.3))
SCENARIO_RESULTS = run_scenarios(SimulationConfig(1000, 2, 120), DISEASE, SCENARIOS)
TABLE = summarize_scenarios(SCENARIO_RESULTS, DISEASE, SCENARIOS)


def _traces(fig):
    return {trace.name: trace for trace in fig.data}


@pytest.mark.parametrize(
    "model, vaccinated_label",
    [
        (VaccineModel.ALL_OR_NOTHING, "Vaccinated (immune)"),
        (VaccineModel.LEAKY, "Vaccinated (not yet infected)"),
    ],
)
def test_legend_labels(model, vaccinated_label):
    fig = compartment_figure(RESULTS, model)
    assert [t.name for t in fig.data] == ["Infected", "Recovered", "Susceptible", vaccinated_label]


def test_each_line_plots_its_compartment():
    traces = _traces(compartment_figure(RESULTS))
    for column, label in [
        ("I", "Infected"),
        ("R", "Recovered"),
        ("S", "Susceptible"),
        ("V", "Vaccinated (immune)"),
    ]:
        assert list(traces[label].y) == list(RESULTS[column])
        assert list(traces[label].x) == list(RESULTS["day"])


def test_compartment_axes_and_hover():
    fig = compartment_figure(RESULTS)
    assert fig.layout.xaxis.title.text == "Day"
    assert fig.layout.yaxis.title.text == "People"
    assert fig.layout.yaxis.type == "linear"
    assert fig.layout.hovermode == "x unified"


def test_sir_chart_has_no_exposed_line():
    fig = compartment_figure(RESULTS)
    assert fig.layout.title.text == "Disease spread (SIR model)"
    assert not any(t.name.startswith("Exposed") for t in fig.data)


def test_seir_chart_shows_exposed():
    results = simulate(SimulationConfig(1000, 2, 30), DiseaseParams(0.3, 0.1, 0.2, "SEIR"))
    fig = compartment_figure(results, model=ModelType.SEIR)
    assert fig.layout.title.text == "Disease spread (SEIR model)"
    assert list(_traces(fig)["Exposed (not yet infectious)"].y) == list(results["E"])


def test_every_series_has_its_own_line_pattern_and_color():
    results = simulate(SimulationConfig(1000, 2, 30), DiseaseParams(0.3, 0.1, 0.2, "SEIR"))
    for fig in (
        compartment_figure(results, model=ModelType.SEIR),
        scenario_comparison_figure(SCENARIO_RESULTS),
    ):
        styles = [(t.line.color, t.line.dash) for t in fig.data]
        assert len({color for color, _ in styles}) == len(styles)
        assert len({dash for _, dash in styles}) >= len(styles) - 1  # S and I are both solid
    scenario_dashes = [t.line.dash for t in scenario_comparison_figure(SCENARIO_RESULTS).data]
    assert len(set(scenario_dashes)) == len(scenario_dashes)


def test_scenario_colors_follow_the_scenario_not_its_position():
    reordered = run_scenarios(SimulationConfig(1000, 2, 30), DISEASE, SCENARIOS[::-1])
    for fig in (
        scenario_comparison_figure(SCENARIO_RESULTS),
        scenario_comparison_figure(reordered),
    ):
        for trace in fig.data:
            assert (trace.line.color, trace.line.dash) == SCENARIO_STYLES[trace.name]


def test_unknown_scenario_names_get_distinct_styles():
    first, second = scenario_style("Custom A", 0), scenario_style("Custom B", 1)
    assert first != second
    assert first not in SCENARIO_STYLES.values()


def test_scenario_comparison_plots_infected_for_each_scenario():
    fig = scenario_comparison_figure(SCENARIO_RESULTS)
    assert [t.name for t in fig.data] == [s.name for s in SCENARIOS]
    for s in SCENARIOS:
        expected = SCENARIO_RESULTS.loc[SCENARIO_RESULTS["scenario"] == s.name, "I"].tolist()
        assert list(_traces(fig)[s.name].y) == expected
    assert fig.layout.yaxis.title.text == "People infected"
    assert fig.layout.xaxis.title.text == "Day"


def test_log_scale_hides_values_it_cannot_draw_and_says_so():
    # No vaccination: V is 0 every day. R is 0 on day 0.
    fig = compartment_figure(RESULTS, log_y=True)
    assert fig.layout.yaxis.type == "log"
    vaccinated = _traces(fig)["Vaccinated (immune)"]
    assert all(v is None for v in vaccinated.y)
    hidden = sum(v is None for t in fig.data for v in t.y)
    assert hidden == (RESULTS[["S", "I", "R", "V"]] < LOG_FLOOR).sum().sum() == len(RESULTS) + 1
    assert _traces(fig)["Recovered"].y[0] is None
    (note,) = fig.layout.annotations
    assert f"{hidden} daily values below {LOG_FLOOR} people (including zeros)" in note.text
    # Values at or above the floor are drawn unchanged.
    assert list(_traces(fig)["Infected"].y) == list(RESULTS["I"])


def test_log_scale_without_hidden_values_has_no_note():
    fig = scenario_comparison_figure(SCENARIO_RESULTS.query("day <= 20"), log_y=True)
    assert fig.layout.yaxis.type == "log"
    assert not fig.layout.annotations


def test_linear_scale_draws_zeros():
    fig = compartment_figure(RESULTS)
    assert list(_traces(fig)["Vaccinated (immune)"].y) == [0.0] * len(RESULTS)
    assert not fig.layout.annotations


@pytest.mark.parametrize("percent", [False, True])
def test_scenario_bar_figure(percent):
    column = "attack_rate" if percent else "peak_infectious"
    fig = scenario_bar_figure(TABLE, column, "Title", "Axis", percent=percent)
    (bar,) = fig.data
    assert isinstance(bar, go.Bar)
    assert list(bar.y) == list(TABLE.index)
    scale = 100 if percent else 1
    assert list(bar.x) == pytest.approx(list(TABLE[column] * scale))
    assert bar.text[0].endswith("%") == percent
    assert list(bar.marker.color) == [SCENARIO_STYLES[name][0] for name in TABLE.index]
    assert fig.layout.xaxis.title.text == "Axis"
    assert fig.layout.yaxis.type == "category"  # scenario names, not numbers


def test_infected_statistics_figure_draws_mean_and_median():
    summary = summarize(RESULTS, DISEASE)
    fig = infected_statistics_figure(RESULTS, summary)
    assert list(fig.data[0].y) == list(RESULTS["I"])
    lines = [shape.y0 for shape in fig.layout.shapes]
    assert lines == pytest.approx([summary.mean_infectious, summary.median_infectious])
    labels = [a.text for a in fig.layout.annotations]
    assert labels == [
        f"Mean: {summary.mean_infectious:,.1f}",
        f"Median: {summary.median_infectious:,.1f}",
    ]


def test_distribution_figure_has_one_box_per_scenario():
    fig = daily_infected_distribution_figure(SCENARIO_RESULTS)
    assert [t.name for t in fig.data] == [s.name for s in SCENARIOS]
    for trace in fig.data:
        assert isinstance(trace, go.Box)
        expected = SCENARIO_RESULTS.loc[SCENARIO_RESULTS["scenario"] == trace.name, "I"]
        assert list(trace.x) == expected.tolist()
        assert trace.boxmean is True
    assert fig.layout.yaxis.type == "category"
