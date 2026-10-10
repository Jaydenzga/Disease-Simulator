"""Compartmental epidemic models.

The SIR model is stepped with forward Euler using a 1-day step, which is the
update rule of the original single-file app. Each flow is capped at the size
of the compartment it drains, so compartments never go negative, and every
flow leaves one compartment and enters another, so S + I + R + V = N exactly
(up to floating-point rounding).
"""

import pandas as pd

from disease_sim.interventions import apply_vaccination
from disease_sim.parameters import DiseaseParams, SimulationConfig, Vaccination

COMPARTMENTS = ["S", "I", "R", "V"]


def simulate_sir(
    config: SimulationConfig,
    disease: DiseaseParams,
    vaccination: Vaccination | None = None,
) -> pd.DataFrame:
    """Run the SIR model with optional day-0 vaccination.

    Returns one row per day from day 0 (initial state) to `config.days`,
    with columns `day` and the compartments in `COMPARTMENTS`.
    """
    vaccination = vaccination or Vaccination()
    n = config.population
    beta, gamma = disease.infection_rate, disease.recovery_rate

    infected = config.initial_infected
    start = apply_vaccination(n - infected, vaccination)
    susceptible, vaccinated = start.susceptible, start.vaccinated
    recovered = 0.0

    rows = [(0, susceptible, infected, recovered, vaccinated)]
    for day in range(1, config.days + 1):
        force = beta * infected / n
        new_infections = min(force * susceptible, susceptible)
        breakthrough = min(force * start.susceptibility * vaccinated, vaccinated)
        new_recoveries = min(gamma * infected, infected)

        susceptible -= new_infections
        vaccinated -= breakthrough
        infected += new_infections + breakthrough - new_recoveries
        recovered += new_recoveries

        rows.append((day, susceptible, infected, recovered, vaccinated))

    return pd.DataFrame(rows, columns=["day", *COMPARTMENTS])
