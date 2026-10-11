"""Named intervention scenarios run against shared disease settings.

Every scenario in a comparison uses the same population, run length, and
disease parameters, so differences between them come only from the
interventions.
"""

from dataclasses import asdict, dataclass, field

import pandas as pd

from disease_sim.metrics import summarize
from disease_sim.models import simulate
from disease_sim.parameters import ContactReduction, DiseaseParams, SimulationConfig, Vaccination

NO_INTERVENTION = "No intervention"
VACCINATION_ONLY = "Vaccination only"
CONTACT_REDUCTION_ONLY = "Contact reduction only"
COMBINED = "Vaccination + contact reduction"


@dataclass(frozen=True)
class Scenario:
    name: str
    vaccination: Vaccination = field(default_factory=Vaccination)
    contact_reduction: ContactReduction = field(default_factory=ContactReduction)


def default_scenarios(
    vaccination: Vaccination, contact_reduction: ContactReduction
) -> list[Scenario]:
    """The four standard comparisons; the first is the baseline."""
    return [
        Scenario(NO_INTERVENTION),
        Scenario(VACCINATION_ONLY, vaccination=vaccination),
        Scenario(CONTACT_REDUCTION_ONLY, contact_reduction=contact_reduction),
        Scenario(COMBINED, vaccination, contact_reduction),
    ]


def _check_names(scenarios: list[Scenario]) -> None:
    if not scenarios:
        raise ValueError("at least one scenario is required")
    names = [s.name for s in scenarios]
    if len(set(names)) != len(names):
        raise ValueError(f"scenario names must be unique, got {names}")


def run_scenarios(
    config: SimulationConfig, disease: DiseaseParams, scenarios: list[Scenario]
) -> pd.DataFrame:
    """Simulate each scenario; returns long format: scenario, day, S, E, I, R, V."""
    _check_names(scenarios)
    frames = [
        simulate(config, disease, s.vaccination, s.contact_reduction).assign(scenario=s.name)
        for s in scenarios
    ]
    combined = pd.concat(frames, ignore_index=True)
    return combined[["scenario", *combined.columns.drop("scenario")]]


def summarize_scenarios(
    results: pd.DataFrame, disease: DiseaseParams, scenarios: list[Scenario]
) -> pd.DataFrame:
    """One row of metrics per scenario, indexed by name.

    `infections_averted` compares infections during the simulation with the
    first scenario (the baseline). All scenarios start with the same people
    infected, so this equals the difference in cumulative infections too.
    """
    _check_names(scenarios)
    rows = {
        s.name: asdict(
            summarize(
                results[results["scenario"] == s.name].reset_index(drop=True),
                disease,
                s.vaccination,
                s.contact_reduction,
            )
        )
        for s in scenarios
    }
    table = pd.DataFrame.from_dict(rows, orient="index")
    baseline = table["infections_during_simulation"].iloc[0]
    table["infections_averted"] = baseline - table["infections_during_simulation"]
    table.index.name = "scenario"
    return table
