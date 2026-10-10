"""Simulation inputs and their validation.

All rates are per day. Fractions (coverage, effectiveness) are in [0, 1];
the interface is responsible for converting percentages.
"""

from dataclasses import dataclass
from enum import StrEnum


class VaccineModel(StrEnum):
    """How vaccine effectiveness is interpreted.

    ALL_OR_NOTHING: a fraction `effectiveness` of vaccinated people become
        fully immune; the rest are unprotected.
    LEAKY: every vaccinated person's chance of infection per contact is
        reduced by `effectiveness`.
    """

    ALL_OR_NOTHING = "all_or_nothing"
    LEAKY = "leaky"


def _check_fraction(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1, got {value}")


def _check_nonnegative(name: str, value: float) -> None:
    if value < 0:
        raise ValueError(f"{name} must be nonnegative, got {value}")


@dataclass(frozen=True)
class DiseaseParams:
    """Transmission (beta) and recovery (gamma) rates, per day."""

    infection_rate: float
    recovery_rate: float

    def __post_init__(self) -> None:
        _check_nonnegative("infection_rate", self.infection_rate)
        _check_nonnegative("recovery_rate", self.recovery_rate)

    @property
    def basic_reproduction_number(self) -> float:
        """R0 = beta / gamma (infinite if nobody ever recovers)."""
        if self.recovery_rate == 0:
            return float("inf")
        return self.infection_rate / self.recovery_rate


@dataclass(frozen=True)
class Vaccination:
    """Vaccination applied once, at day 0, to the initially susceptible."""

    coverage: float = 0.0
    effectiveness: float = 1.0
    model: VaccineModel = VaccineModel.ALL_OR_NOTHING

    def __post_init__(self) -> None:
        _check_fraction("coverage", self.coverage)
        _check_fraction("effectiveness", self.effectiveness)
        # Accept plain strings such as "leaky" from callers.
        object.__setattr__(self, "model", VaccineModel(self.model))


@dataclass(frozen=True)
class SimulationConfig:
    """Population size, initial outbreak size, and run length."""

    population: float
    initial_infected: float
    days: int

    def __post_init__(self) -> None:
        if self.population <= 0:
            raise ValueError(f"population must be positive, got {self.population}")
        _check_nonnegative("initial_infected", self.initial_infected)
        if self.initial_infected > self.population:
            raise ValueError(
                f"initial_infected ({self.initial_infected}) cannot exceed "
                f"population ({self.population})"
            )
        if int(self.days) != self.days or self.days < 1:
            raise ValueError(f"days must be a positive integer, got {self.days}")
