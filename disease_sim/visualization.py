"""Figure builders. Each takes a results DataFrame and returns a figure."""

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from disease_sim.parameters import ModelType, VaccineModel

SERIES = [
    ("E", "Exposed (not yet infectious)", "orange"),  # SEIR only
    ("I", "Infected", "red"),
    ("R", "Recovered", "green"),
    ("S", "Susceptible", "blue"),
    ("V", None, "purple"),  # label depends on the vaccine model
]

# What the V compartment holds differs by vaccine model, so its label does too.
# All-or-nothing: only the people the vaccine protected (vaccine failures are in S).
# Leaky: every vaccinated person not yet infected (breakthrough infections leave V).
VACCINATED_LABELS = {
    VaccineModel.ALL_OR_NOTHING: "Vaccinated (immune)",
    VaccineModel.LEAKY: "Vaccinated (not yet infected)",
}


def compartment_figure(
    results: pd.DataFrame,
    vaccine_model: VaccineModel = VaccineModel.ALL_OR_NOTHING,
    model: ModelType = ModelType.SIR,
    title: str | None = None,
) -> Figure:
    """Line chart of every compartment over time (E is shown only for SEIR)."""
    model = ModelType(model)
    fig, ax = plt.subplots()
    for column, label, color in SERIES:
        if column == "E" and model is not ModelType.SEIR:
            continue
        label = label or VACCINATED_LABELS[VaccineModel(vaccine_model)]
        ax.plot(results["day"], results[column], label=label, color=color)
    ax.set_title(title or f"Disease Spread ({model} Model)")
    ax.set_xlabel("Days")
    ax.set_ylabel("People")
    ax.legend()
    return fig


SCENARIO_COLORS = ["black", "purple", "darkorange", "teal"]


def scenario_comparison_figure(results: pd.DataFrame) -> Figure:
    """Infectious curve of every scenario in long-format results, on one chart."""
    fig, ax = plt.subplots()
    for index, (name, group) in enumerate(results.groupby("scenario", sort=False)):
        color = SCENARIO_COLORS[index % len(SCENARIO_COLORS)]
        ax.plot(group["day"], group["I"], label=name, color=color)
    ax.set_title("Infected Over Time by Scenario")
    ax.set_xlabel("Days")
    ax.set_ylabel("People infected")
    ax.legend()
    return fig
