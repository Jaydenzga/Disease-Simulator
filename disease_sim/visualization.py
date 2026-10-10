"""Figure builders. Each takes a results DataFrame and returns a figure."""

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

SERIES = [
    ("I", "Infected", "red"),
    ("R", "Recovered", "green"),
    ("S", "Susceptible", "blue"),
    ("V", "Vaccinated", "purple"),
]


def compartment_figure(results: pd.DataFrame, title: str = "Disease Spread (SIR Model)") -> Figure:
    """Line chart of every compartment over time."""
    fig, ax = plt.subplots()
    for column, label, color in SERIES:
        ax.plot(results["day"], results[column], label=label, color=color)
    ax.set_title(title)
    ax.set_xlabel("Days")
    ax.set_ylabel("People")
    ax.legend()
    return fig
