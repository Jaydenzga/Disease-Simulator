"""Compartmental epidemic models (SIR and SEIR) sharing one engine.

SIR and SEIR differ only in where new infections go: SIR sends them straight
to I, SEIR sends them to E, from which they progress to I at rate sigma. In
SIR, E stays at zero.

The model is stepped with forward Euler using `config.steps_per_day` steps
per day; with one step per day this is exactly the update rule of the
original single-file app. Within a step, every flow is computed from the
state at the start of the step and then applied together, so the order of
the update lines does not matter. Each flow is capped at the size of the
compartment it drains, so compartments never go negative, and every flow
leaves one compartment and enters another, so S + E + I + R + V = N exactly
(up to floating-point rounding).
"""

import pandas as pd

from disease_sim.interventions import apply_vaccination, contact_multiplier
from disease_sim.parameters import (
    ContactReduction,
    DiseaseParams,
    ModelType,
    SimulationConfig,
    Vaccination,
)

COMPARTMENTS = ["S", "E", "I", "R", "V"]


def simulate(
    config: SimulationConfig,
    disease: DiseaseParams,
    vaccination: Vaccination | None = None,
    contact_reduction: ContactReduction | None = None,
) -> pd.DataFrame:
    """Run the SIR or SEIR model (per `disease.model`).

    Vaccination is applied once at day 0. Contact reduction scales the
    transmission rate during each step that starts inside its active window.
    Returns one row per day from day 0 (initial state) to `config.days`,
    with columns `day` and the compartments in `COMPARTMENTS`.
    """
    vaccination = vaccination or Vaccination()
    contact_reduction = contact_reduction or ContactReduction()
    n = config.population
    dt = 1.0 / config.steps_per_day
    beta, gamma, sigma = disease.infection_rate, disease.recovery_rate, disease.progression_rate
    has_latent_stage = disease.model is ModelType.SEIR

    infected = config.initial_infected
    start = apply_vaccination(n - infected, vaccination)
    susceptible, vaccinated = start.susceptible, start.vaccinated
    exposed = recovered = 0.0

    rows = [(0, susceptible, exposed, infected, recovered, vaccinated)]
    for day in range(1, config.days + 1):
        for step in range(config.steps_per_day):
            t = day - 1 + step / config.steps_per_day  # time at the start of this step
            force = beta * contact_multiplier(t, contact_reduction) * infected / n * dt
            new_infections = min(force * susceptible, susceptible)
            breakthrough = min(force * start.susceptibility * vaccinated, vaccinated)
            new_recoveries = min(gamma * dt * infected, infected)

            susceptible -= new_infections
            vaccinated -= breakthrough
            if has_latent_stage:
                progressions = min(sigma * dt * exposed, exposed)
                exposed += new_infections + breakthrough - progressions
                infected += progressions - new_recoveries
            else:
                infected += new_infections + breakthrough - new_recoveries
            recovered += new_recoveries

        rows.append((day, susceptible, exposed, infected, recovered, vaccinated))

    return pd.DataFrame(rows, columns=["day", *COMPARTMENTS])


def simulate_sir(
    config: SimulationConfig,
    disease: DiseaseParams,
    vaccination: Vaccination | None = None,
) -> pd.DataFrame:
    """Phase 1 name for `simulate`, kept so existing callers keep working."""
    return simulate(config, disease, vaccination)
