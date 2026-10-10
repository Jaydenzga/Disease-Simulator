"""Interventions that modify the initial state or the dynamics."""

from dataclasses import dataclass

from disease_sim.parameters import Vaccination, VaccineModel


@dataclass(frozen=True)
class VaccinatedStart:
    """Result of vaccinating the initial susceptible pool."""

    susceptible: float
    vaccinated: float
    # Relative infection risk of a vaccinated person compared with an
    # unvaccinated one: 0 for all-or-nothing (V is immune), 1 - e for leaky.
    susceptibility: float


def apply_vaccination(susceptible: float, vaccination: Vaccination) -> VaccinatedStart:
    """Move vaccinated people out of S and into V at day 0.

    All-or-nothing: V0 = c * e * S0 are fully immune; the vaccinated people
    the vaccine failed for stay in S.
    Leaky: V0 = c * S0, all partially protected.
    """
    c, e = vaccination.coverage, vaccination.effectiveness
    if vaccination.model is VaccineModel.ALL_OR_NOTHING:
        vaccinated = c * e * susceptible
        susceptibility = 0.0
    else:
        vaccinated = c * susceptible
        susceptibility = 1.0 - e
    return VaccinatedStart(
        susceptible=susceptible - vaccinated,
        vaccinated=vaccinated,
        susceptibility=susceptibility,
    )
