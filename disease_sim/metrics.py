"""Summary metrics computed from a results DataFrame.

The infectious-population statistics (mean, median, standard deviation) are
descriptive statistics of one deterministic time series: they summarize the
shape of the curve over the simulated days. They are not estimates from a
sample, so they say nothing about uncertainty or statistical significance.
See docs/MODEL.md for each formula and its limitations.
"""

from dataclasses import dataclass

import pandas as pd

from disease_sim.interventions import contact_multiplier, vaccine_susceptibility
from disease_sim.models import COMPARTMENTS
from disease_sim.parameters import ContactReduction, DiseaseParams, Vaccination

# Fewer than this many people still exposed or infectious counts as "over".
# Compartments hold fractional people, so they decay toward 0 without reaching it.
STILL_INFECTED_THRESHOLD = 1.0


@dataclass(frozen=True)
class Summary:
    peak_infectious: float
    peak_day: int  # first day on which I reaches its maximum
    mean_infectious: float  # over the daily values on days 0..D
    median_infectious: float
    sd_infectious: float  # population SD (divide by n): the series is complete, not a sample
    infections_during_simulation: float  # new infections after day 0
    cumulative_infections: float  # initially infected + infections during the simulation
    attack_rate: float  # cumulative infections / N
    basic_reproduction_number: float  # R0 = beta / gamma
    initial_effective_reproduction_number: float  # R_e at day 0
    still_infected_at_end: bool  # at least one person exposed or infectious on the last day


def initial_effective_reproduction_number(
    results: pd.DataFrame,
    disease: DiseaseParams,
    vaccination: Vaccination | None = None,
    contact_reduction: ContactReduction | None = None,
) -> float:
    """R_e(0) = R0 * contact multiplier at t=0 * (S0 + m * V0) / N.

    m is the vaccinated susceptibility (0 all-or-nothing, 1 - e leaky). This
    is the value at day 0 only: a contact reduction starting later does not
    lower it, and R_e changes as people are infected.
    """
    day0 = results.iloc[0]
    n = day0[COMPARTMENTS].sum()
    m = vaccine_susceptibility(vaccination or Vaccination())
    exposure = (day0["S"] + m * day0["V"]) / n
    multiplier = contact_multiplier(0.0, contact_reduction or ContactReduction())
    if exposure == 0 or multiplier == 0:
        return 0.0  # avoids inf * 0 when nobody recovers
    return float(disease.basic_reproduction_number * multiplier * exposure)


def summarize(
    results: pd.DataFrame,
    disease: DiseaseParams,
    vaccination: Vaccination | None = None,
    contact_reduction: ContactReduction | None = None,
) -> Summary:
    infectious = results["I"]
    first, last = results.iloc[0], results.iloc[-1]
    n = first[COMPARTMENTS].sum()

    # Every infection moves someone out of S or V, so their combined drop
    # counts infections exactly (I + R would miss people still in E).
    during = (first["S"] - last["S"]) + (first["V"] - last["V"])
    cumulative = first["E"] + first["I"] + during

    return Summary(
        peak_infectious=float(infectious.max()),
        peak_day=int(results["day"].iloc[infectious.to_numpy().argmax()]),
        mean_infectious=float(infectious.mean()),
        median_infectious=float(infectious.median()),
        sd_infectious=float(infectious.std(ddof=0)),
        infections_during_simulation=float(during),
        cumulative_infections=float(cumulative),
        attack_rate=float(cumulative / n),
        basic_reproduction_number=disease.basic_reproduction_number,
        initial_effective_reproduction_number=initial_effective_reproduction_number(
            results, disease, vaccination, contact_reduction
        ),
        still_infected_at_end=bool(last["E"] + last["I"] >= STILL_INFECTED_THRESHOLD),
    )
