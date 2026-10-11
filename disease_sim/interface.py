"""Streamlit interface. This is the only module that imports streamlit."""

import streamlit as st

from disease_sim.models import STEP_ERROR_TOLERANCE, steps_for_tolerance
from disease_sim.parameters import (
    DEFAULT_LATENT_PERIOD,
    DEFAULT_STEPS_PER_DAY,
    LEGACY_STEPS_PER_DAY,
    ContactReduction,
    DiseaseParams,
    ModelType,
    SimulationConfig,
    Vaccination,
    VaccineModel,
)
from disease_sim.scenarios import (
    COMBINED,
    default_scenarios,
    estimate_scenarios_step_error,
    run_scenarios,
    summarize_scenarios,
)
from disease_sim.visualization import compartment_figure, scenario_comparison_figure

VACCINE_MODEL_LABELS = {
    VaccineModel.ALL_OR_NOTHING: "Immunity (all-or-nothing)",
    VaccineModel.LEAKY: "Partial protection (leaky)",
}

VACCINATED_CAPTIONS = {
    VaccineModel.ALL_OR_NOTHING: (
        "**Vaccinated (immune)** counts only the people the vaccine protected "
        "(coverage × effectiveness). Vaccinated people it failed to protect are "
        "counted as Susceptible."
    ),
    VaccineModel.LEAKY: (
        "**Vaccinated (not yet infected)** counts every vaccinated person who has not "
        "been infected. Each has their infection risk reduced by the effectiveness %. "
        "Breakthrough infections move people to Infected, so this line can fall."
    ),
}

RATES_INPUT = "Rates (β, γ)"
R0_INPUT = "R₀ and infectious period"

STEPS_PER_DAY_LABELS = {
    LEGACY_STEPS_PER_DAY: "1 (legacy: matches Phase 1)",
    DEFAULT_STEPS_PER_DAY: "4 (default)",
    10: "10",
    20: "20",
    50: "50 (most accurate)",
}

# Summary table columns, in display order, with readable headings.
SUMMARY_COLUMNS = {
    "peak_infectious": "Peak infected",
    "peak_day": "Peak day",
    "mean_infectious": "Mean infected",
    "median_infectious": "Median infected",
    "sd_infectious": "SD infected",
    "infections_during_simulation": "New infections",
    "cumulative_infections": "Cumulative infections",
    "attack_rate": "Attack rate (%)",
    "infections_averted": "Infections averted (by last day)",
    "initial_effective_reproduction_number": "Rₑ at day 0",
    "still_infected_at_end": "Still infected at end",
}

STATISTICS_CAPTION = (
    "Mean, median, and SD describe the daily number of infected people over the "
    "simulated days (SD divides by n, the number of daily values from day 0 to the "
    "last day, because these are all the days, not a sample). The model is "
    "deterministic, so these are descriptive statistics of one curve, **not** "
    "estimates of uncertainty or statistical significance. New infections excludes "
    "the initially infected; cumulative infections includes them. Attack rate = "
    "cumulative infections ÷ population."
)

STEP_SIZE_WARNING = (
    "Numerical error is estimated at about {error:.0%} of the peak at this number of "
    "simulation steps per day. {advice}"
)

UNFINISHED_WARNING = (
    "At least one scenario still has infected people on the last day, so its totals are "
    "incomplete. Infections averted counts only infections up to the last day: an "
    "intervention that merely delays infections past that day looks more effective than "
    "it is. Increase **Days** until no scenario is still infected to compare final totals."
)

DISCLAIMER = (
    "Educational model for exploring how epidemics behave. It is not a forecast of any "
    "real outbreak."
)


def _disease_controls(model: ModelType) -> DiseaseParams:
    input_mode = st.radio("Disease Input", [RATES_INPUT, R0_INPUT], horizontal=True)
    if input_mode == RATES_INPUT:
        infection_rate = st.slider("Infection Rate", 0.01, 0.5, 0.05)
        recovery_rate = st.slider("Recovery Rate", 0.01, 0.5, 0.03)
    else:
        r0 = st.slider("R₀", 0.5, 10.0, 2.5, step=0.1)
        infectious_period = st.slider("Mean infectious period (days)", 1.0, 30.0, 10.0, step=0.5)

    latent_period = DEFAULT_LATENT_PERIOD
    if model is ModelType.SEIR:
        latent_period = st.slider(
            "Mean latent period (days)",
            0.5,
            21.0,
            latent_period,
            step=0.5,
            help="Average time from infection until a person becomes infectious.",
        )
    if input_mode == RATES_INPUT:
        return DiseaseParams(infection_rate, recovery_rate, 1.0 / latent_period, model)
    return DiseaseParams.from_r0(r0, infectious_period, latent_period, model)


def _vaccination_controls() -> Vaccination:
    vaccination_percentage = st.slider("Vaccinated (%)", 0, 100, 0)
    effectiveness_percentage = st.slider("Vaccine Effectiveness (%)", 0, 100, 100)
    vaccine_model = st.radio(
        "Vaccine Model",
        list(VACCINE_MODEL_LABELS),
        format_func=VACCINE_MODEL_LABELS.get,
        horizontal=True,
        help=(
            "Immunity: the effectiveness % of vaccinated people are fully immune. "
            "Partial protection: every vaccinated person's infection risk is "
            "reduced by the effectiveness %."
        ),
    )
    return Vaccination(
        coverage=vaccination_percentage / 100,
        effectiveness=effectiveness_percentage / 100,
        model=vaccine_model,
    )


def _bounded_slider(label: str, key: str, low: int, high: int, default: int) -> int:
    """Integer slider whose range depends on other inputs, keeping the user's value.

    Streamlit treats a slider whose range changes as a new widget and resets it,
    and forgets a widget's value on any run where it is not drawn. The value is
    therefore kept under a separate session key, clamped into the current range,
    and handed back to the slider before it is drawn.
    """
    store = f"_kept_{key}"
    if key in st.session_state:  # the slider's value from the previous run
        st.session_state[store] = st.session_state[key]
    value = st.session_state.get(store, default)
    st.session_state[key] = st.session_state[store] = min(max(value, low), high)
    return st.slider(label, low, high, key=key)


def _contact_reduction_controls(days: int) -> ContactReduction:
    reduction = st.slider(
        "Contact Reduction (%)",
        0,
        90,
        0,
        help="Distancing or masking: lowers the transmission rate by this % while active.",
    )
    start_day = _bounded_slider("Reduction starts on day", "reduction_start", 0, days - 1, 0)
    end_day = None
    # The end-day slider needs at least two choices (start + 1 .. days).
    can_lift = start_day + 1 < days
    lift = st.checkbox("Lift the reduction before the end of the simulation", disabled=not can_lift)
    if lift and can_lift:
        end_day = _bounded_slider(
            "Reduction ends on day", "reduction_end", start_day + 1, days, days
        )
    return ContactReduction(reduction / 100, start_day, end_day)


def _step_error_warning(config, disease, scenarios, results) -> None:
    error = estimate_scenarios_step_error(config, disease, scenarios, results)
    if error <= STEP_ERROR_TOLERANCE:
        return
    needed = steps_for_tolerance(config.steps_per_day, error)
    options = [k for k in STEPS_PER_DAY_LABELS if k >= needed]
    if options:
        advice = f"Choose at least {options[0]} steps per day for more accurate curves."
    elif config.steps_per_day < max(STEPS_PER_DAY_LABELS):
        advice = "Choose the most accurate setting; results will still be approximate."
    else:
        advice = "Even the most accurate setting is approximate for these rates."
    st.warning(STEP_SIZE_WARNING.format(error=error, advice=advice))


def run() -> None:
    st.caption(DISCLAIMER)
    model = st.radio(
        "Model",
        list(ModelType),
        horizontal=True,
        help="SEIR adds an Exposed stage: infected but not yet infectious.",
    )
    population = st.slider("Population", 100, 10000, 1000)
    initial_infected = st.slider("Initial Infected", 1, 100, 2)
    disease = _disease_controls(model)
    days = st.slider("Days", 10, 200, 30)

    st.subheader("Interventions")
    vaccination = _vaccination_controls()
    contact_reduction = _contact_reduction_controls(days)

    steps_per_day = st.selectbox(
        "Simulation steps per day",
        list(STEPS_PER_DAY_LABELS),
        index=list(STEPS_PER_DAY_LABELS).index(DEFAULT_STEPS_PER_DAY),
        format_func=STEPS_PER_DAY_LABELS.get,
        help="More steps per day give a more accurate solution of the model equations.",
    )

    config = SimulationConfig(population, initial_infected, days, steps_per_day)
    scenarios = default_scenarios(vaccination, contact_reduction)
    results = run_scenarios(config, disease, scenarios)
    # The combined scenario is exactly the settings chosen above.
    chosen = results[results["scenario"] == COMBINED].drop(columns="scenario")
    _step_error_warning(config, disease, scenarios, results)

    st.subheader("Your scenario")
    st.write(f"R₀ = {disease.basic_reproduction_number:.2f}")
    st.pyplot(compartment_figure(chosen, vaccination.model, model=model))
    st.caption(VACCINATED_CAPTIONS[vaccination.model])

    st.subheader("Compare scenarios")
    st.pyplot(scenario_comparison_figure(results))
    table = summarize_scenarios(results, disease, scenarios)
    if table["still_infected_at_end"].any():
        st.warning(UNFINISHED_WARNING)
    table["attack_rate"] *= 100
    st.dataframe(
        table[list(SUMMARY_COLUMNS)].rename(columns=SUMMARY_COLUMNS),
        column_config={
            label: st.column_config.NumberColumn(format="%.2f")
            for key, label in SUMMARY_COLUMNS.items()
            if key not in ("peak_day", "still_infected_at_end")
        },
    )
    st.caption(STATISTICS_CAPTION)
