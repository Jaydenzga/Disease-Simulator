"""Plain-language text for the dashboard: tooltips, captions, and run summaries.

Kept separate from the interface so the wording can be tested without a browser.
"""

from disease_sim.metrics import Summary
from disease_sim.models import STEP_ERROR_TOLERANCE, steps_for_tolerance
from disease_sim.parameters import VaccineModel
from disease_sim.presets import DiseasePreset

DISCLAIMER = (
    "Educational model for exploring how epidemics behave. It is not a forecast of any "
    "real outbreak."
)

# Tooltips for the sidebar controls.
PARAMETER_HELP = {
    "model": (
        "SIR: Susceptible → Infected → Recovered. SEIR adds an Exposed stage: infected but "
        "not yet able to infect others."
    ),
    "population": "Total number of people (N). Nobody is born, dies, or moves in or out.",
    "initial_infected": "People who are already infectious on day 0.",
    "days": "How many days to simulate. Results are reported once per day.",
    "preset": (
        "Fill in R₀ and the infectious and latent periods with rounded, typical published "
        "values for a well-known infection. These are educational approximations, not "
        "forecasts. Moving any disease slider afterwards switches back to Custom."
    ),
    "input_mode": (
        "Describe the disease by its rates, or by R₀ and how long people stay infectious."
    ),
    "infection_rate": (
        "β: infections caused per infectious person per day, if everyone they meet were "
        "susceptible."
    ),
    "recovery_rate": (
        "γ: share of infectious people who recover each day. 1 / γ is the mean infectious period."
    ),
    "r0": (
        "Basic reproduction number: the average number of people one infectious person "
        "infects in a fully susceptible population. Above 1, an outbreak can grow."
    ),
    "infectious_period": "Average number of days a person stays infectious (1 / γ).",
    "latent_period": (
        "Average number of days from being infected to becoming infectious (1 / σ). "
        "Not the same as the incubation period, which ends at symptom onset."
    ),
    "coverage": "Share of the initially susceptible population vaccinated on day 0.",
    "effectiveness": "How well the vaccine works. Its meaning depends on the vaccine model.",
    "vaccine_model": (
        "Immunity: the effectiveness % of vaccinated people are fully immune. "
        "Partial protection: every vaccinated person's infection risk is "
        "reduced by the effectiveness %."
    ),
    "reduction": "Distancing or masking: lowers the transmission rate by this % while active.",
    "start_day": "First day the contact reduction is in effect.",
    "lift": "End the contact reduction on a chosen day; otherwise it lasts to the end.",
    "end_day": "First day without the contact reduction.",
    "steps_per_day": (
        "The equations are solved in small time steps. More steps per day give a more "
        "accurate solution but take longer. 1 reproduces the original app."
    ),
    "log_scale": (
        "A logarithmic y-axis shows small and large numbers together, so the early growth "
        "and the tail of the outbreak are visible. Zeros cannot be drawn on it."
    ),
}

# Tooltips and glossary entries for the metrics.
METRIC_HELP = {
    "r0": PARAMETER_HELP["r0"] + " R₀ = β / γ.",
    "re0": (
        "Effective reproduction number on day 0: R₀ adjusted for vaccination and any "
        "contact reduction in effect on day 0. Below 1, each case causes less than one new "
        "case on average, so the outbreak shrinks."
    ),
    "peak_infectious": "The largest number of people infectious at the same time.",
    "peak_day": "The first day on which the number infectious is at its largest.",
    "attack_rate": (
        "Share of the population infected at some point by the last day, including the "
        "initially infected."
    ),
    "mean_infectious": "Average of the daily infectious counts from day 0 to the last day.",
    "median_infectious": (
        "Middle value of the daily infectious counts: half the days are above it, half below."
    ),
    "sd_infectious": (
        "Standard deviation of the daily infectious counts: how far a typical day is from the "
        "mean. Divides by the number of days because every day is included, not a sample."
    ),
    "infections_during_simulation": "New infections after day 0.",
    "cumulative_infections": "Initially infected plus new infections.",
    "infections_averted": (
        "New infections in the no-intervention scenario minus new infections in this "
        "scenario, counted up to the last day."
    ),
    "still_infected_at_end": "At least one person is still exposed or infectious on the last day.",
}

GLOSSARY = [
    ("R₀", METRIC_HELP["r0"]),
    ("Rₑ at day 0", METRIC_HELP["re0"]),
    ("Peak infected", METRIC_HELP["peak_infectious"]),
    ("Peak day", METRIC_HELP["peak_day"]),
    ("Attack rate", METRIC_HELP["attack_rate"]),
    ("New infections", METRIC_HELP["infections_during_simulation"]),
    ("Cumulative infections", METRIC_HELP["cumulative_infections"]),
    ("Infections averted", METRIC_HELP["infections_averted"]),
]

VACCINATED_CAPTIONS = {
    VaccineModel.ALL_OR_NOTHING: (
        "**Vaccinated (immune)** counts only the people the vaccine protected "
        "(coverage × effectiveness). Vaccinated people it failed to protect are "
        "counted as Susceptible."
    ),
    VaccineModel.LEAKY: (
        "**Vaccinated (not yet infected)** counts every vaccinated person who has not "
        "been infected. Each has their infection risk reduced by the effectiveness %. "
        "Breakthrough infections move people to Infected, so this line can fall."
    ),
}

STATISTICS_SCOPE = (
    "**These statistics describe one curve across simulated days, not uncertainty across "
    "possible outbreaks.** Each day's infected count is one value; the mean, median, and "
    "standard deviation summarize those values from day 0 to the last day. Running the "
    "same settings again gives exactly the same numbers."
)

STATISTICS_CAPTION = (
    "Mean, median, and SD describe the daily number of infected people over the "
    "simulated days (SD divides by n, the number of daily values from day 0 to the "
    "last day, because these are all the days, not a sample). The model is "
    "deterministic, so these are descriptive statistics of one curve, **not** "
    "estimates of uncertainty or statistical significance. New infections excludes "
    "the initially infected; cumulative infections includes them. Attack rate = "
    "cumulative infections ÷ population."
)

DISTRIBUTION_CAPTION = (
    "Each box summarizes one scenario's daily infected counts: the line inside is the "
    "median, the box spans the middle half of the days, the dashed line is the mean, and "
    "dots are unusually high days. A long box or many dots means the outbreak was "
    "concentrated in a few days, not that the result is uncertain."
)

# (title, explanation) for the three kinds of numbers the dashboard shows.
THREE_KINDS = [
    (
        "Model results: deterministic",
        "The model has no randomness. The same settings always give exactly the same "
        "curves and metrics. They show what the equations imply, not what will happen.",
    ),
    (
        "Numerical error: estimated",
        "The computer solves the equations in small time steps, which introduces a small "
        "error. The app estimates it by rerunning with twice as many steps and comparing. "
        "It measures how well the equations were solved, not how realistic they are.",
    ),
    (
        "Statistical uncertainty: not modeled",
        "Real outbreaks vary by chance, and real parameters are uncertain. This model "
        "measures neither: there are no confidence intervals or p-values. Random "
        "(stochastic) simulations are planned for a later phase.",
    ),
]

STEP_ERROR_OK = (
    "Estimated numerical error: about {error:.1%} of the peak, within the {tolerance:.0%} "
    "tolerance."
)

STEP_SIZE_WARNING = (
    "Numerical error is estimated at about {error:.0%} of the peak at this number of "
    "simulation steps per day. {advice}"
)

UNFINISHED_WARNING = (
    "Outbreak not over by day {days} in: {names}. Totals for these scenarios are "
    "incomplete, and infections averted counts only infections up to the last day: an "
    "intervention that merely delays infections past that day looks more effective than "
    "it is. Increase **Days** to compare final totals."
)

FINISHED_MESSAGE = "Every scenario's outbreak is over by day {days}, so totals are final."


def preset_caption(preset: DiseasePreset) -> str:
    """What a disease preset sets, and how far to trust it."""
    return (
        f"R₀ {preset.r0:g} (published estimates {preset.r0_range}), infectious for "
        f"{preset.infectious_period:g} days, latent for {preset.latent_period:g} days. "
        "Educational approximation, not a forecast: rounded typical values, and the model "
        "still has no deaths, prior immunity, or differences between people. Sources are "
        "in the About tab."
    )


def step_error_message(error: float, steps_per_day: int, choices: list[int]) -> tuple[bool, str]:
    """(within tolerance?, message) for a step-doubling error estimate.

    `choices` are the steps-per-day settings the user can pick from.
    """
    if error <= STEP_ERROR_TOLERANCE:
        return True, STEP_ERROR_OK.format(error=error, tolerance=STEP_ERROR_TOLERANCE)
    needed = steps_for_tolerance(steps_per_day, error)
    options = sorted(k for k in choices if k >= needed)
    if options:
        advice = f"Choose at least {options[0]} steps per day for more accurate curves."
    elif steps_per_day < max(choices):
        advice = "Choose the most accurate setting; results will still be approximate."
    else:
        advice = "Even the most accurate setting is approximate for these rates."
    return False, STEP_SIZE_WARNING.format(error=error, advice=advice)


def outbreak_status_message(unfinished: list[str], days: int) -> tuple[bool, str]:
    """(all finished?, message) given the names of scenarios still infected at the end."""
    if not unfinished:
        return True, FINISHED_MESSAGE.format(days=days)
    return False, UNFINISHED_WARNING.format(days=days, names=", ".join(unfinished))


def _people(count: float) -> str:
    rounded = round(count)
    if rounded == 0 and count > 0:
        return "fewer than 1 person"
    return f"{rounded:,} {'person' if rounded == 1 else 'people'}"


def run_summary(summary: Summary, population: float, days: int) -> str:
    """One short paragraph describing a run in plain language."""
    if summary.peak_day == 0:
        peak = (
            f"The number of infectious people never rises above the starting "
            f"{_people(summary.peak_infectious)}: each case causes fewer new infectious "
            f"cases than it replaces."
        )
    else:
        peak = (
            f"Infections peak on day {summary.peak_day}, when "
            f"{_people(summary.peak_infectious)} "
            f"({summary.peak_infectious / population:.1%} of the population) are infectious "
            f"at the same time."
        )
    total = (
        f"By day {days}, {_people(summary.cumulative_infections)} "
        f"({summary.attack_rate:.1%} of the population) have been infected, including the "
        f"initially infected."
    )
    if summary.still_infected_at_end:
        ending = f"The outbreak is not over by day {days}, so the final total will be higher."
    else:
        ending = f"The outbreak is over by day {days}."
    return " ".join([peak, total, ending])
