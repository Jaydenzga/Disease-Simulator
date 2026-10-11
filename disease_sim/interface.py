"""Streamlit interface. This is the only module that imports streamlit."""

import streamlit as st

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
from disease_sim.scenarios import COMBINED, default_scenarios, run_scenarios, summarize_scenarios
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
    10: "10 (most accurate)",
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
    "infections_averted": "Infections averted",
    "initial_effective_reproduction_number": "Rₑ at day 0",
    "still_infected_at_end": "Still spreading at end",
}

STATISTICS_CAPTION = (
    "Mean, median, and SD describe the daily number of infected people over the "
    "simulated days (SD divides by n, the number of days, because these are all the "
    "days, not a sample). The model is deterministic, so these are descriptive "
    "statistics of one curve, **not** estimates of uncertainty or statistical "
    "significance. New infections excludes the initially infected; cumulative "
    "infections includes them. Attack rate = cumulative infections ÷ population."
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
        recovery_rate = 1.0 / infectious_period
        infection_rate = r0 * recovery_rate

    latent_period = 5.0
    if model is ModelType.SEIR:
        latent_period = st.slider(
            "Mean latent period (days)",
            0.5,
            21.0,
            latent_period,
            step=0.5,
            help="Average time from infection until a person becomes infectious.",
        )
    return DiseaseParams(infection_rate, recovery_rate, 1.0 / latent_period, model)


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


def _contact_reduction_controls(days: int) -> ContactReduction:
    reduction = st.slider(
        "Contact Reduction (%)",
        0,
        90,
        0,
        help="Distancing or masking: lowers the transmission rate by this % while active.",
    )
    start_day = st.slider("Reduction starts on day", 0, days - 1, 0)
    end_day = None
    if st.checkbox("Lift the reduction before the end of the simulation"):
        end_day = st.slider("Reduction ends on day", start_day + 1, days, days)
    return ContactReduction(reduction / 100, start_day, end_day)


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

    st.subheader("Your scenario")
    st.write(f"R₀ = {disease.basic_reproduction_number:.2f}")
    st.pyplot(compartment_figure(chosen, vaccination.model, model=model))
    st.caption(VACCINATED_CAPTIONS[vaccination.model])

    st.subheader("Compare scenarios")
    st.pyplot(scenario_comparison_figure(results))
    table = summarize_scenarios(results, disease, scenarios)
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
