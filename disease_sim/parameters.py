"""Simulation inputs and their validation.

All rates are per day. Fractions (coverage, effectiveness) are in [0, 1];
the interface is responsible for converting percentages. Every numeric input
must be finite: NaN fails every comparison, so without an explicit check it
would slip past range checks and turn the whole simulation into NaN.
"""

import math
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


def _check_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value}")


def _check_fraction(name: str, value: float) -> None:
    _check_finite(name, value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1, got {value}")


def _check_nonnegative(name: str, value: float) -> None:
    _check_finite(name, value)
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


DEFAULT_STEPS_PER_DAY = 4
# One step per day reproduces the original single-file app exactly.
LEGACY_STEPS_PER_DAY = 1


def _check_positive_integer(name: str, value: float) -> None:
    _check_finite(name, value)
    if int(value) != value or value < 1:
        raise ValueError(f"{name} must be a positive integer, got {value}")


@dataclass(frozen=True)
class SimulationConfig:
    """Population size, initial outbreak size, run length, and time resolution.

    `steps_per_day` splits each day into that many Euler steps of length
    1 / steps_per_day. Results are still reported once per day.
    """

    population: float
    initial_infected: float
    days: int
    steps_per_day: int = DEFAULT_STEPS_PER_DAY

    def __post_init__(self) -> None:
        _check_finite("population", self.population)
        if self.population <= 0:
            raise ValueError(f"population must be positive, got {self.population}")
        _check_nonnegative("initial_infected", self.initial_infected)
        if self.initial_infected > self.population:
            raise ValueError(
                f"initial_infected ({self.initial_infected}) cannot exceed "
                f"population ({self.population})"
            )
        _check_positive_integer("days", self.days)
        _check_positive_integer("steps_per_day", self.steps_per_day)
