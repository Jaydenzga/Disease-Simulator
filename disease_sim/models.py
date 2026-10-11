"""Compartmental epidemic models.

The model is stepped with forward Euler using `config.steps_per_day` steps
per day; with one step per day this is exactly the update rule of the
original single-file app. Within a step, every flow is computed from the
state at the start of the step and then applied together, so the order of
the update lines does not matter. Each flow is capped at the size of the
compartment it drains, so compartments never go negative, and every flow
leaves one compartment and enters another, so S + I + R + V = N exactly (up
to floating-point rounding).
"""

import pandas as pd

from disease_sim.interventions import apply_vaccination
from disease_sim.parameters import DiseaseParams, SimulationConfig, Vaccination

COMPARTMENTS = ["S", "I", "R", "V"]


def simulate(
    config: SimulationConfig,
    disease: DiseaseParams,
    vaccination: Vaccination | None = None,
) -> pd.DataFrame:
    """Run the model with optional day-0 vaccination.

    Returns one row per day from day 0 (initial state) to `config.days`,
    with columns `day` and the compartments in `COMPARTMENTS`.
    """
    vaccination = vaccination or Vaccination()
    n = config.population
    dt = 1.0 / config.steps_per_day
    beta, gamma = disease.infection_rate, disease.recovery_rate

    infected = config.initial_infected
    start = apply_vaccination(n - infected, vaccination)
    susceptible, vaccinated = start.susceptible, start.vaccinated
    recovered = 0.0

    rows = [(0, susceptible, infected, recovered, vaccinated)]
    for day in range(1, config.days + 1):
        for _ in range(config.steps_per_day):
            force = beta * infected / n * dt
            new_infections = min(force * susceptible, susceptible)
            breakthrough = min(force * start.susceptibility * vaccinated, vaccinated)
            new_recoveries = min(gamma * dt * infected, infected)

            susceptible -= new_infections
            vaccinated -= breakthrough
            infected += new_infections + breakthrough - new_recoveries
            recovered += new_recoveries

        rows.append((day, susceptible, infected, recovered, vaccinated))

    return pd.DataFrame(rows, columns=["day", *COMPARTMENTS])


def simulate_sir(
    config: SimulationConfig,
    disease: DiseaseParams,
    vaccination: Vaccination | None = None,
) -> pd.DataFrame:
    """Phase 1 name for `simulate`, kept so existing callers keep working."""
    return simulate(config, disease, vaccination)
