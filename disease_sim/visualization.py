"""Plotly figure builders. Each takes results or summary DataFrames and returns a figure.

Colors and line patterns are assigned per compartment and per scenario, not
by position, so a series keeps its look on every chart. Every series also has
its own line pattern, so the charts can be read without telling colors apart.
The colors come from a categorical palette checked for colorblind separation:
every pair differs by at least 13 OKLab ΔE×100 under simulated protanopia and
deuteranopia and by about 20 with normal vision.
"""

import textwrap

import pandas as pd
import plotly.graph_objects as go

from disease_sim.metrics import Summary
from disease_sim.parameters import ModelType, VaccineModel
from disease_sim.scenarios import (
    COMBINED,
    CONTACT_REDUCTION_ONLY,
    NO_INTERVENTION,
    VACCINATION_ONLY,
)

BLUE, YELLOW, MAGENTA, GREEN, GRAY = "#2a78d6", "#eda100", "#e87ba4", "#008300", "#52514e"
INK, MUTED_INK, GRID = "#1f1f1e", "#52514e", "#e6e6e3"


# What the V compartment holds differs by vaccine model, so its label does too.
# All-or-nothing: only the people the vaccine protected (vaccine failures are in S).
# Leaky: every vaccinated person not yet infected (breakthrough infections leave V).
VACCINATED_LABELS = {
    VaccineModel.ALL_OR_NOTHING: "Vaccinated (immune)",
    VaccineModel.LEAKY: "Vaccinated (not yet infected)",
}

# column: (legend label, color, line pattern, line width). Drawn in this order.
COMPARTMENT_STYLES = {
    "E": ("Exposed (not yet infectious)", YELLOW, "dash", 2),  # SEIR only
    "I": ("Infected", MAGENTA, "solid", 3),
    "R": ("Recovered", GREEN, "dot", 2),
    "S": ("Susceptible", BLUE, "solid", 2),
    "V": (None, GRAY, "dashdot", 2),  # label depends on the vaccine model
}

# scenario name: (color, line pattern). The baseline is neutral gray.
SCENARIO_STYLES = {
    NO_INTERVENTION: (GRAY, "solid"),
    VACCINATION_ONLY: (BLUE, "dash"),
    CONTACT_REDUCTION_ONLY: (YELLOW, "dot"),
    COMBINED: (MAGENTA, "dashdot"),
}
# For scenarios with other names, in order of appearance.
EXTRA_STYLES = [(GREEN, "longdash"), (INK, "longdashdot")]

# On a log axis, 0 has no position. Values below this many people (including
# zeros) are left out of log charts, and the chart says how many were left out.
LOG_FLOOR = 0.01
LOG_NOTE = "Log scale: {count} daily values below {floor} people (including zeros) are not drawn."


def scenario_style(name: str, position: int) -> tuple[str, str]:
    """Color and line pattern for a scenario; `position` is used for unknown names."""
    if name in SCENARIO_STYLES:
        return SCENARIO_STYLES[name]
    return EXTRA_STYLES[position % len(EXTRA_STYLES)]


def _wrap(name: str, width: int = 14) -> str:
    """Break a long label over lines so it does not crowd a narrow chart."""
    return "<br>".join(textwrap.wrap(name, width)) or name


def _visible(values: pd.Series, log_y: bool) -> tuple[list, int]:
    """Values to draw and how many were hidden (only on a log axis)."""
    if not log_y:
        return values.tolist(), 0
    shown = [value if value >= LOG_FLOOR else None for value in values]  # None leaves a gap
    return shown, shown.count(None)


def _style(fig: go.Figure, title: str, x_title: str, y_title: str, log_y: bool = False) -> None:
    fig.update_layout(
        title={"text": title, "x": 0, "xanchor": "left", "automargin": True},
        font={"family": "system-ui, -apple-system, Segoe UI, sans-serif", "size": 14, "color": INK},
        paper_bgcolor="white",
        plot_bgcolor="white",
        hovermode="x unified",
        separators=".,",
        # Horizontal, at the bottom of the figure: on narrow screens it wraps onto more
        # rows and the plot shrinks to make room, so it never covers the title or axis.
        legend={
            "orientation": "h",
            "yref": "container",
            "y": 0,
            "yanchor": "bottom",
            "x": 0,
            "xanchor": "left",
            "title": None,
        },
        margin={"l": 8, "r": 8, "t": 56, "b": 8},
    )
    axis = {
        "showgrid": True,
        "gridcolor": GRID,
        "linecolor": GRID,
        "zeroline": False,
        "automargin": True,  # grow the margin to fit tick labels and titles
    }
    fig.update_xaxes(title=x_title, **axis)
    fig.update_yaxes(
        title=y_title,
        type="log" if log_y else "linear",
        rangemode="normal" if log_y else "tozero",  # counts: a linear axis starts at 0
        tickformat="~s" if log_y else ",~r",
        **axis,
    )


def _add_log_note(fig: go.Figure, hidden: int) -> None:
    if hidden:
        fig.add_annotation(
            text=LOG_NOTE.format(count=hidden, floor=LOG_FLOOR),
            xref="paper",
            yref="paper",
            x=0,
            y=1.0,
            yanchor="bottom",
            xanchor="left",
            showarrow=False,
            font={"size": 12, "color": MUTED_INK},
        )


def _line(x, y, name: str, color: str, dash: str, width: float = 2) -> go.Scatter:
    return go.Scatter(
        x=x,
        y=y,
        name=name,
        mode="lines",
        line={"color": color, "dash": dash, "width": width},
        hovertemplate="%{y:,.1f}",
    )


def compartment_figure(
    results: pd.DataFrame,
    vaccine_model: VaccineModel = VaccineModel.ALL_OR_NOTHING,
    model: ModelType = ModelType.SIR,
    title: str | None = None,
    log_y: bool = False,
) -> go.Figure:
    """Line chart of every compartment over time (E is shown only for SEIR)."""
    model = ModelType(model)
    fig = go.Figure()
    hidden = 0
    for column, (label, color, dash, width) in COMPARTMENT_STYLES.items():
        if column == "E" and model is not ModelType.SEIR:
            continue
        label = label or VACCINATED_LABELS[VaccineModel(vaccine_model)]
        values, count = _visible(results[column], log_y)
        hidden += count
        fig.add_trace(_line(results["day"], values, label, color, dash, width))
    _style(fig, title or f"Disease spread ({model} model)", "Day", "People", log_y)
    _add_log_note(fig, hidden)
    return fig


def scenario_comparison_figure(results: pd.DataFrame, log_y: bool = False) -> go.Figure:
    """Infected curve of every scenario in long-format results, on one chart."""
    fig = go.Figure()
    hidden = 0
    for position, (name, group) in enumerate(results.groupby("scenario", sort=False)):
        color, dash = scenario_style(name, position)
        values, count = _visible(group["I"], log_y)
        hidden += count
        fig.add_trace(_line(group["day"], values, name, color, dash))
    _style(fig, "Infected over time by scenario", "Day", "People infected", log_y)
    _add_log_note(fig, hidden)
    return fig


def scenario_bar_figure(
    table: pd.DataFrame, column: str, title: str, axis_title: str, percent: bool = False
) -> go.Figure:
    """Horizontal bars of one summary metric per scenario (index = scenario name).

    Scenario names label the bars directly, so color is not needed to read them.
    """
    values = table[column] * (100 if percent else 1)
    text_format = "{:.1f}%" if percent else "{:,.0f}"
    names = list(table.index)
    colors = [scenario_style(name, i)[0] for i, name in enumerate(names)]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=names,
            orientation="h",
            marker={"color": colors, "line": {"color": "white", "width": 2}},
            text=[text_format.format(v) for v in values],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{text}<extra></extra>",
        )
    )
    _style(fig, title, axis_title, "")
    fig.update_layout(hovermode="closest", showlegend=False, margin={"r": 48})
    # Scenario names on a category axis, first scenario on top, wrapped for narrow screens.
    fig.update_yaxes(
        type="category",
        autorange="reversed",
        showgrid=False,
        tickformat="",
        tickvals=names,
        ticktext=[_wrap(name) for name in names],
    )
    fig.update_xaxes(rangemode="tozero", ticksuffix="%" if percent else "")
    return fig


def infected_statistics_figure(
    results: pd.DataFrame, summary: Summary, title: str = "Daily infected with mean and median"
) -> go.Figure:
    """Infected curve with its mean and median drawn as reference lines."""
    label, color, dash, width = COMPARTMENT_STYLES["I"]
    fig = go.Figure(_line(results["day"], results["I"], label, color, dash, width))
    for name, value, line_dash, position in [
        ("Mean", summary.mean_infectious, "dash", "top right"),
        ("Median", summary.median_infectious, "dot", "bottom right"),
    ]:
        fig.add_hline(
            y=value,
            line={"color": INK, "dash": line_dash, "width": 1.5},
            annotation_text=f"{name}: {value:,.1f}",
            annotation_position=position,
            annotation_font={"color": INK, "size": 12},
        )
    _style(fig, title, "Day", "People infected")
    fig.update_layout(showlegend=False)
    return fig


def daily_infected_distribution_figure(results: pd.DataFrame) -> go.Figure:
    """Box plot of the daily infected counts of each scenario.

    Each box summarizes the values on days 0..D of one deterministic curve:
    median line, quartile box, mean as a dashed line, outlying days as points.
    """
    fig = go.Figure()
    for position, (name, group) in enumerate(results.groupby("scenario", sort=False)):
        color, _ = scenario_style(name, position)
        fig.add_trace(
            go.Box(
                x=group["I"],
                name=name,
                marker={"color": color, "size": 4},
                line={"color": color, "width": 2},
                fillcolor="rgba(0,0,0,0)",
                boxmean=True,
                boxpoints="outliers",
                hoverinfo="x",
            )
        )
    _style(fig, "Distribution of daily infected counts", "People infected on a day", "")
    names = list(results["scenario"].unique())
    fig.update_layout(hovermode="closest", showlegend=False)
    fig.update_yaxes(
        type="category",
        autorange="reversed",
        showgrid=False,
        tickformat="",
        tickvals=names,
        ticktext=[_wrap(name) for name in names],
    )
    return fig
