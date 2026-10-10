"""Streamlit interface. This is the only module that imports streamlit."""

import streamlit as st

from disease_sim.models import simulate_sir
from disease_sim.parameters import (
    DiseaseParams,
    SimulationConfig,
    Vaccination,
    VaccineModel,
)
from disease_sim.visualization import compartment_figure

VACCINE_MODEL_LABELS = {
    VaccineModel.ALL_OR_NOTHING: "Immunity (all-or-nothing)",
    VaccineModel.LEAKY: "Partial protection (leaky)",
}


def run() -> None:
    population = st.slider("Population", 100, 10000, 1000)
    initial_infected = st.slider("Initial Infected", 1, 100, 2)
    infection_rate = st.slider("Infection Rate", 0.01, 0.5, 0.05)
    recovery_rate = st.slider("Recovery Rate", 0.01, 0.5, 0.03)
    days = st.slider("Days", 10, 200, 30)

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

    results = simulate_sir(
        SimulationConfig(population, initial_infected, days),
        DiseaseParams(infection_rate, recovery_rate),
        Vaccination(
            coverage=vaccination_percentage / 100,
            effectiveness=effectiveness_percentage / 100,
            model=vaccine_model,
        ),
    )

    st.pyplot(compartment_figure(results))
