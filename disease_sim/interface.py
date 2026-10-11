"""Streamlit dashboard. This is the only module that imports streamlit.

Layout: sidebar controls, an always-visible status area (numerical error and
whether every outbreak finished), and five tabs. Every widget keeps its value
in session state through `_kept`, so values survive range changes and hidden
widgets, and "Reset to defaults" can restore all of them.
"""

from dataclasses import fields
from pathlib import Path

import pandas as pd
import streamlit as st

from disease_sim import explain
from disease_sim.export import results_csv, summary_csv
from disease_sim.metrics import Summary
from disease_sim.parameters import (
    DEFAULT_STEPS_PER_DAY,
    LEGACY_STEPS_PER_DAY,
    ContactReduction,
    DiseaseParams,
    ModelType,
    SimulationConfig,
    Vaccination,
    VaccineModel,
)
from disease_sim.presets import CUSTOM, PRESETS, PRESETS_BY_NAME
from disease_sim.scenarios import (
    COMBINED,
    default_scenarios,
    estimate_scenarios_step_error,
    run_scenarios,
    summarize_scenarios,
)
from disease_sim.visualization import (
    compartment_figure,
    daily_infected_distribution_figure,
    infected_statistics_figure,
    scenario_bar_figure,
    scenario_comparison_figure,
)

MODEL_DOC = Path(__file__).resolve().parent.parent / "docs" / "MODEL.md"

MODEL_LABELS = {ModelType.SIR: "SIR", ModelType.SEIR: "SEIR (with latent stage)"}

VACCINE_MODEL_LABELS = {
    VaccineModel.ALL_OR_NOTHING: "Immunity (all-or-nothing)",
    VaccineModel.LEAKY: "Partial protection (leaky)",
}

R0_INPUT = "R₀ and infectious period"
RATES_INPUT = "Rates (β, γ)"

STEPS_PER_DAY_LABELS = {
    LEGACY_STEPS_PER_DAY: "1 (legacy: matches Phase 1)",
    DEFAULT_STEPS_PER_DAY: "4 (default)",
    10: "10",
    20: "20",
    50: "50 (most accurate)",
}

# Slider and input ranges: (min, max, step).
DAYS_RANGE = (10, 730, 1)
POPULATION_RANGE = (100, 1_000_000, 1_000)
R0_RANGE = (0.5, 20.0, 0.1)
INFECTIOUS_PERIOD_RANGE = (1.0, 30.0, 0.5)
LATENT_PERIOD_RANGE = (0.5, 21.0, 0.5)
INFECTION_RATE_RANGE = (0.01, 3.0, 0.001)
RECOVERY_RATE_RANGE = (0.01, 1.0, 0.001)

DEFAULTS = {
    "model": ModelType.SEIR,
    "population": 10_000,
    "initial_infected": 10,
    "days": 365,
    "preset": CUSTOM,
    "input_mode": R0_INPUT,
    "r0": 2.5,
    "infectious_period": 7.0,
    "infection_rate": 0.357,  # R0 2.5 over 7 days, shown when switching to rates
    "recovery_rate": 0.143,
    "latent_period": 5.0,
    "coverage": 30,
    "effectiveness": 90,
    "vaccine_model": VaccineModel.ALL_OR_NOTHING,
    "reduction": 30,
    "start_day": 14,
    "lift": False,
    "end_day": 365,
    "steps_per_day": DEFAULT_STEPS_PER_DAY,
    "sim_log": False,
    "compare_log": False,
}

# Rows of the scenario comparison table: summary column -> (label, format).
COMPARISON_ROWS = {
    "peak_infectious": ("Peak infected", "{:,.0f}"),
    "peak_day": ("Peak day", "{:d}"),
    "attack_rate": ("Attack rate", "{:.1%}"),
    "infections_during_simulation": ("New infections", "{:,.0f}"),
    "cumulative_infections": ("Cumulative infections", "{:,.0f}"),
    "infections_averted": ("Infections averted (by last day)", "{:,.0f}"),
    "initial_effective_reproduction_number": ("Rₑ at day 0", "{:.2f}"),
    "still_infected_at_end": ("Still infected at end", None),
}

# Columns of the descriptive-statistics table: summary column -> label.
STATISTICS_COLUMNS = {
    "peak_infectious": "Peak infected",
    "peak_day": "Peak day",
    "mean_infectious": "Mean infected",
    "median_infectious": "Median infected",
    "sd_infectious": "SD infected",
}

PLOTLY_CONFIG = {"displaylogo": False, "responsive": True}


# --- Widget state ---------------------------------------------------------------


def _kept(key: str, low=None, high=None) -> str:
    """Prepare a widget's value under `key` and return the key.

    Streamlit treats a widget whose range changes as a new widget and resets it,
    and forgets a widget's value on any run where it is not drawn. The value is
    therefore also kept under a separate session key, clamped into the current
    range, and handed back to the widget before it is drawn.
    """
    store = f"_kept_{key}"
    if key in st.session_state:  # the widget's value from the previous run
        st.session_state[store] = st.session_state[key]
    value = st.session_state.get(store, DEFAULTS[key])
    if low is not None:
        value = max(value, low)
    if high is not None:
        value = min(value, high)
    st.session_state[key] = st.session_state[store] = value
    return key


def _set(key: str, value) -> None:
    st.session_state[key] = st.session_state[f"_kept_{key}"] = value


def _reset() -> None:
    for key, value in DEFAULTS.items():
        _set(key, value)


def _snap(value: float, value_range: tuple[float, float, float]) -> float:
    """Round to the slider step and clamp into its range."""
    low, high, step = value_range
    return min(max(round(round(value / step) * step, 6), low), high)


def _convert_disease_input() -> None:
    """When the input mode changes, carry the current disease over to the new mode."""
    state = st.session_state
    if state["input_mode"] == RATES_INPUT:
        gamma = 1.0 / state["_kept_infectious_period"]
        _set("recovery_rate", _snap(gamma, RECOVERY_RATE_RANGE))
        _set("infection_rate", _snap(state["_kept_r0"] * gamma, INFECTION_RATE_RANGE))
    else:
        beta, gamma = state["_kept_infection_rate"], state["_kept_recovery_rate"]
        _set("infectious_period", _snap(1.0 / gamma, INFECTIOUS_PERIOD_RANGE))
        _set("r0", _snap(beta / gamma, R0_RANGE))


def _apply_preset() -> None:
    """Fill the disease controls (both input modes) from the chosen preset."""
    preset = PRESETS_BY_NAME.get(st.session_state["preset"])
    if preset is None:  # Custom: keep the current values
        return
    _set("r0", preset.r0)
    _set("infectious_period", preset.infectious_period)
    _set("latent_period", preset.latent_period)
    gamma = 1.0 / preset.infectious_period
    _set("recovery_rate", _snap(gamma, RECOVERY_RATE_RANGE))
    _set("infection_rate", _snap(preset.r0 * gamma, INFECTION_RATE_RANGE))


def _mark_custom() -> None:
    """Editing a disease value by hand means the preset no longer describes it."""
    _set("preset", CUSTOM)


# --- Sidebar --------------------------------------------------------------------


def _slider(label: str, value_range, key: str, **kwargs):
    low, high, step = value_range
    return st.slider(
        label,
        low,
        high,
        step=step,
        key=_kept(key, low, high),
        help=explain.PARAMETER_HELP[key],
        **kwargs,
    )


def _population_controls() -> tuple[ModelType, float, float, int]:
    model = st.radio(
        "Model",
        list(ModelType),
        format_func=MODEL_LABELS.get,
        key=_kept("model"),
        help=explain.PARAMETER_HELP["model"],
    )
    low, high, step = POPULATION_RANGE
    population = st.number_input(
        "Population",
        low,
        high,
        step=step,
        key=_kept("population", low, high),
        help=explain.PARAMETER_HELP["population"],
    )
    initial_infected = st.number_input(
        "Initially infected",
        1,
        population,
        step=1,
        key=_kept("initial_infected", 1, population),
        help=explain.PARAMETER_HELP["initial_infected"],
    )
    days = _slider("Days to simulate", DAYS_RANGE, "days")
    return model, population, initial_infected, days


def _disease_controls(model: ModelType) -> DiseaseParams:
    preset = st.selectbox(
        "Disease preset",
        [CUSTOM, *(p.name for p in PRESETS)],
        key=_kept("preset"),
        on_change=_apply_preset,
        help=explain.PARAMETER_HELP["preset"],
    )
    if preset != CUSTOM:
        st.caption(explain.preset_caption(PRESETS_BY_NAME[preset]))
    input_mode = st.radio(
        "Describe the disease by",
        [R0_INPUT, RATES_INPUT],
        key=_kept("input_mode"),
        on_change=_convert_disease_input,
        help=explain.PARAMETER_HELP["input_mode"],
    )
    if input_mode == R0_INPUT:
        r0 = _slider("R₀", R0_RANGE, "r0", on_change=_mark_custom)
        infectious_period = _slider(
            "Mean infectious period (days)",
            INFECTIOUS_PERIOD_RANGE,
            "infectious_period",
            on_change=_mark_custom,
        )
    else:
        infection_rate = _slider(
            "Infection rate β (per day)",
            INFECTION_RATE_RANGE,
            "infection_rate",
            format="%.3f",
            on_change=_mark_custom,
        )
        recovery_rate = _slider(
            "Recovery rate γ (per day)",
            RECOVERY_RATE_RANGE,
            "recovery_rate",
            format="%.3f",
            on_change=_mark_custom,
        )

    latent_period = DEFAULTS["latent_period"]
    if model is ModelType.SEIR:
        latent_period = _slider(
            "Mean latent period (days)",
            LATENT_PERIOD_RANGE,
            "latent_period",
            on_change=_mark_custom,
        )

    if input_mode == R0_INPUT:
        disease = DiseaseParams.from_r0(r0, infectious_period, latent_period, model)
        st.caption(f"β = {disease.infection_rate:.3f} and γ = {disease.recovery_rate:.3f} per day")
    else:
        disease = DiseaseParams(infection_rate, recovery_rate, 1.0 / latent_period, model)
        st.caption(
            f"R₀ = β / γ = {disease.basic_reproduction_number:.2f}; mean infectious period "
            f"{disease.mean_infectious_period:.1f} days"
        )
    return disease


def _vaccination_controls() -> Vaccination:
    coverage = _slider("Vaccination coverage (%)", (0, 100, 1), "coverage")
    effectiveness = _slider("Vaccine effectiveness (%)", (0, 100, 1), "effectiveness")
    vaccine_model = st.radio(
        "Vaccine model",
        list(VACCINE_MODEL_LABELS),
        format_func=VACCINE_MODEL_LABELS.get,
        key=_kept("vaccine_model"),
        help=explain.PARAMETER_HELP["vaccine_model"],
    )
    return Vaccination(coverage / 100, effectiveness / 100, vaccine_model)


def _contact_reduction_controls(days: int) -> ContactReduction:
    reduction = _slider("Contact reduction (%)", (0, 90, 1), "reduction")
    start_day = _slider("Reduction starts on day", (0, days - 1, 1), "start_day")
    # The end-day slider needs at least two choices (start + 1 .. days).
    can_lift = start_day + 1 < days
    lift = st.checkbox(
        "Lift the reduction before the last day",
        key=_kept("lift"),
        disabled=not can_lift,
        help=explain.PARAMETER_HELP["lift"],
    )
    end_day = None
    if lift and can_lift:
        end_day = _slider("Reduction ends on day", (start_day + 1, days, 1), "end_day")
    return ContactReduction(reduction / 100, start_day, end_day)


def _sidebar() -> tuple[SimulationConfig, DiseaseParams, Vaccination, ContactReduction]:
    with st.sidebar:
        st.button(
            "Reset to defaults",
            on_click=_reset,
            type="primary",
            icon=":material/restart_alt:",
            width="stretch",
            help="Restore every setting to its starting value.",
        )
        with st.expander("Model and population", expanded=True, icon=":material/groups:"):
            model, population, initial_infected, days = _population_controls()
        with st.expander("Disease", expanded=True, icon=":material/coronavirus:"):
            disease = _disease_controls(model)
        with st.expander("Vaccination", expanded=True, icon=":material/vaccines:"):
            vaccination = _vaccination_controls()
        with st.expander("Contact reduction", expanded=True, icon=":material/social_distance:"):
            contact_reduction = _contact_reduction_controls(days)
        with st.expander("Numerical accuracy", icon=":material/tune:"):
            steps_per_day = st.selectbox(
                "Simulation steps per day",
                list(STEPS_PER_DAY_LABELS),
                format_func=STEPS_PER_DAY_LABELS.get,
                key=_kept("steps_per_day"),
                help=explain.PARAMETER_HELP["steps_per_day"],
            )
    config = SimulationConfig(population, initial_infected, days, steps_per_day)
    return config, disease, vaccination, contact_reduction


# --- Computation -----------------------------------------------------------------


@st.cache_data(max_entries=64, show_spinner=False)
def _compute(
    config: SimulationConfig,
    disease: DiseaseParams,
    vaccination: Vaccination,
    contact_reduction: ContactReduction,
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    """Results (long format), summary table, and estimated step error for all scenarios.

    Cached on the inputs, which are frozen dataclasses, so returning to earlier
    settings reuses the earlier results.
    """
    scenarios = default_scenarios(vaccination, contact_reduction)
    results = run_scenarios(config, disease, scenarios)
    table = summarize_scenarios(results, disease, scenarios)
    error = estimate_scenarios_step_error(config, disease, scenarios, results)
    return results, table, error


def _summary(table: pd.DataFrame, scenario: str) -> Summary:
    row = table.loc[scenario]
    return Summary(**{f.name: row[f.name] for f in fields(Summary)})


def _scenario(results: pd.DataFrame, scenario: str) -> pd.DataFrame:
    rows = results[results["scenario"] == scenario]
    return rows.drop(columns="scenario").reset_index(drop=True)


# --- Main area -------------------------------------------------------------------


def _status_message(ok: bool, text: str) -> None:
    if ok:
        st.success(text, icon=":material/check_circle:")
    else:
        st.warning(text, icon=":material/warning:")


def _status(config: SimulationConfig, table: pd.DataFrame, error: float) -> None:
    """Numerical error and outbreak completion, shown above the tabs."""
    accuracy, outbreak = st.columns(2)
    with accuracy:
        choices = list(STEPS_PER_DAY_LABELS)
        _status_message(*explain.step_error_message(error, config.steps_per_day, choices))
    with outbreak:
        unfinished = list(table.index[table["still_infected_at_end"]])
        _status_message(*explain.outbreak_status_message(unfinished, config.days))


def _chart(fig, key: str) -> None:
    st.plotly_chart(fig, theme=None, config=PLOTLY_CONFIG, key=key)


def _log_toggle(key: str) -> bool:
    return st.toggle("Logarithmic y-axis", key=_kept(key), help=explain.PARAMETER_HELP["log_scale"])


def _simulation_tab(config, disease, vaccination, results, table) -> None:
    summary = _summary(table, COMBINED)
    st.subheader("Your scenario")
    st.caption("Vaccination and contact reduction as set in the sidebar.")
    cards = [
        ("R₀", f"{summary.basic_reproduction_number:.2f}", "r0"),
        ("Rₑ at day 0", f"{summary.initial_effective_reproduction_number:.2f}", "re0"),
        ("Peak infected", f"{summary.peak_infectious:,.0f}", "peak_infectious"),
        ("Peak day", f"{summary.peak_day}", "peak_day"),
        ("Attack rate", f"{summary.attack_rate:.1%}", "attack_rate"),
    ]
    for column, (label, value, key) in zip(st.columns(len(cards)), cards, strict=True):
        column.metric(label, value, help=explain.METRIC_HELP[key], border=True)
    st.markdown(explain.run_summary(summary, config.population, config.days))

    log_y = _log_toggle("sim_log")
    chosen = _scenario(results, COMBINED)
    _chart(compartment_figure(chosen, vaccination.model, disease.model, log_y=log_y), "sim_chart")
    st.caption(explain.VACCINATED_CAPTIONS[vaccination.model])
    st.caption(
        "Deterministic model results: the same settings always give exactly the same "
        "numbers. The **Statistics** tab explains what they do and do not measure."
    )
    with st.expander("What do these numbers mean?", icon=":material/help:"):
        st.markdown("\n".join(f"- **{term}**: {text}" for term, text in explain.GLOSSARY))


def _comparison_table(table: pd.DataFrame) -> pd.DataFrame:
    """Metrics as rows and scenarios as columns, formatted as text for reading."""
    rows = {}
    for column, (label, fmt) in COMPARISON_ROWS.items():
        if fmt is None:
            rows[label] = ["Yes" if value else "No" for value in table[column]]
        elif column == "peak_day":
            rows[label] = [fmt.format(int(value)) for value in table[column]]
        else:
            rows[label] = [fmt.format(value) for value in table[column]]
    return pd.DataFrame(rows, index=table.index).T


def _compare_tab(results, table) -> None:
    st.subheader("Compare scenarios")
    st.caption(
        "All four scenarios share the disease and population settings. They differ only in "
        "the interventions: none, the sidebar's vaccination, its contact reduction, or both."
    )
    log_y = _log_toggle("compare_log")
    _chart(scenario_comparison_figure(results, log_y=log_y), "compare_chart")
    peak, attack = st.columns(2)
    with peak:
        figure = scenario_bar_figure(table, "peak_infectious", "Peak infected", "People")
        _chart(figure, "peak_bars")
    with attack:
        figure = scenario_bar_figure(
            table, "attack_rate", "Attack rate", "Share of population", percent=True
        )
        _chart(figure, "attack_bars")
    st.dataframe(_comparison_table(table), width="stretch")
    st.caption(
        "Infections averted compares each scenario with **No intervention**, counting "
        "infections up to the last day only."
    )


def _statistics_tab(results, table, error) -> None:
    st.subheader("Descriptive statistics")
    st.info(explain.STATISTICS_SCOPE, icon=":material/info:")

    st.markdown("##### Three kinds of numbers")
    for column, (title, text) in zip(st.columns(3), explain.THREE_KINDS, strict=True):
        with column, st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(text)
            if title.startswith("Numerical error"):
                st.caption(f"Current estimate: about {error:.1%} of the peak.")

    names = list(table.index)
    scenario = st.selectbox(
        "Scenario",
        names,
        index=names.index(COMBINED),
        key="stats_scenario",
        help="Which scenario's daily infected counts to show with their mean and median.",
    )
    figure = infected_statistics_figure(
        _scenario(results, scenario),
        _summary(table, scenario),
        title=f"Daily infected with mean and median: {scenario}",
    )
    _chart(figure, "stats_chart")
    _chart(daily_infected_distribution_figure(results), "distribution_chart")
    st.caption(explain.DISTRIBUTION_CAPTION)

    st.dataframe(
        table[list(STATISTICS_COLUMNS)].rename(columns=STATISTICS_COLUMNS),
        width="stretch",
        column_config={
            label: st.column_config.NumberColumn(
                format="%d" if column == "peak_day" else "%.1f",
                help=explain.METRIC_HELP[column],
            )
            for column, label in STATISTICS_COLUMNS.items()
        },
    )
    st.caption(explain.STATISTICS_CAPTION)


def _data_tab(results, table) -> None:
    st.subheader("Data")
    st.caption(
        "Daily values of every compartment, in people. Values are fractional because the "
        "model treats the population as continuous."
    )
    yours = results[results["scenario"] == COMBINED]
    downloads = [
        ("Your scenario (CSV)", results_csv(yours), "your_scenario.csv"),
        ("All scenarios (CSV)", results_csv(results), "all_scenarios.csv"),
        ("Scenario summary (CSV)", summary_csv(table), "scenario_summary.csv"),
    ]
    for column, (label, data, file_name) in zip(st.columns(3), downloads, strict=True):
        column.download_button(
            label,
            data,
            file_name=file_name,
            mime="text/csv",
            icon=":material/download:",
            width="stretch",
            on_click="ignore",
        )
    st.markdown("**Your scenario**")
    st.dataframe(_scenario(results, COMBINED).round(2), width="stretch", hide_index=True)
    with st.expander("All scenarios (long format)"):
        st.dataframe(results.round(2), width="stretch", hide_index=True)


def _about_tab() -> None:
    try:
        st.markdown(MODEL_DOC.read_text(encoding="utf-8"))
    except OSError:
        st.warning("The model description (docs/MODEL.md) could not be found.")


def run() -> None:
    st.set_page_config(
        page_title="Disease Simulator",
        page_icon=":material/coronavirus:",
        layout="wide",
        initial_sidebar_state="auto",  # collapsed on phones, open on wider screens
    )
    config, disease, vaccination, contact_reduction = _sidebar()
    results, table, error = _compute(config, disease, vaccination, contact_reduction)

    st.title("Disease Simulator")
    st.caption(explain.DISCLAIMER)
    _status(config, table, error)

    simulation, compare, statistics, data, about = st.tabs(
        ["Simulation", "Compare", "Statistics", "Data", "About"]
    )
    with simulation:
        _simulation_tab(config, disease, vaccination, results, table)
    with compare:
        _compare_tab(results, table)
    with statistics:
        _statistics_tab(results, table, error)
    with data:
        _data_tab(results, table)
    with about:
        _about_tab()
