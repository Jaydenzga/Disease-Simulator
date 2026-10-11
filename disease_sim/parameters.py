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


class ModelType(StrEnum):
    """Which compartments the disease passes through.

    SIR: infected people are infectious immediately.
    SEIR: infected people first spend a latent period in E (infected but not
        yet infectious) before moving to I.
    """

    SIR = "SIR"
    SEIR = "SEIR"


DEFAULT_LATENT_PERIOD = 5.0  # days


def _check_positive(name: str, value: float) -> None:
    _check_finite(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


@dataclass(frozen=True)
class DiseaseParams:
    """Per-day rates: transmission (beta), recovery (gamma), progression (sigma).

    `progression_rate` is sigma, the rate at which exposed people become
    infectious (1 / mean latent period). Only SEIR uses it.
    """

    infection_rate: float
    recovery_rate: float
    progression_rate: float = 1.0 / DEFAULT_LATENT_PERIOD
    model: ModelType = ModelType.SIR

    def __post_init__(self) -> None:
        _check_nonnegative("infection_rate", self.infection_rate)
        _check_nonnegative("recovery_rate", self.recovery_rate)
        _check_positive("progression_rate", self.progression_rate)
        object.__setattr__(self, "model", ModelType(self.model))

    @classmethod
    def from_r0(
        cls,
        r0: float,
        infectious_period: float,
        latent_period: float = DEFAULT_LATENT_PERIOD,
        model: ModelType = ModelType.SIR,
    ) -> "DiseaseParams":
        """Build rates from R0 and mean periods in days.

        gamma = 1 / infectious period, beta = R0 * gamma, sigma = 1 / latent period.
        """
        _check_nonnegative("r0", r0)
        _check_positive("infectious_period", infectious_period)
        _check_positive("latent_period", latent_period)
        gamma = 1.0 / infectious_period
        return cls(r0 * gamma, gamma, 1.0 / latent_period, model)

    @property
    def basic_reproduction_number(self) -> float:
        """R0 = beta / gamma (infinite if nobody ever recovers).

        The latent period delays infectiousness but does not change how long
        anyone is infectious, so R0 is the same for SIR and SEIR.
        """
        if self.recovery_rate == 0:
            return float("inf")
        return self.infection_rate / self.recovery_rate

    @property
    def mean_infectious_period(self) -> float:
        """1 / gamma, in days (infinite if nobody ever recovers)."""
        if self.recovery_rate == 0:
            return float("inf")
        return 1.0 / self.recovery_rate

    @property
    def mean_latent_period(self) -> float:
        """1 / sigma, in days."""
        return 1.0 / self.progression_rate


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
        # Accept integer-valued floats such as 30.0; the engine needs real ints.
        object.__setattr__(self, "days", int(self.days))
        object.__setattr__(self, "steps_per_day", int(self.steps_per_day))


@dataclass(frozen=True)
class ContactReduction:
    """Non-pharmaceutical intervention (distancing, masking) that scales beta.

    Transmission is multiplied by (1 - reduction) at every time t with
    start_day <= t < end_day. `end_day=None` means it is never lifted.
    """

    reduction: float = 0.0
    start_day: float = 0.0
    end_day: float | None = None

    def __post_init__(self) -> None:
        _check_fraction("reduction", self.reduction)
        _check_nonnegative("start_day", self.start_day)
        if self.end_day is not None:
            _check_finite("end_day", self.end_day)
            if self.end_day <= self.start_day:
                raise ValueError(
                    f"end_day ({self.end_day}) must be after start_day ({self.start_day})"
                )

    def is_active(self, t: float) -> bool:
        return self.start_day <= t and (self.end_day is None or t < self.end_day)
