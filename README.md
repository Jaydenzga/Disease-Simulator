# Disease Simulator

An interactive epidemic simulator built with Streamlit. Choose an SIR or SEIR model, set the population and disease parameters, add vaccination and contact reduction, and compare four intervention scenarios side by side with summary statistics.

> This is an educational model for exploring how epidemics behave. It is not a forecast of any real outbreak.

## Installation

Requires Python 3.11 or newer.

```bash
git clone https://github.com/Jaydenzga/Disease-Simulator.git
cd Disease-Simulator
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
streamlit run main.py
```

The app opens in your browser at http://localhost:8501. Controls:

| Control | Meaning |
|---|---|
| Model | **SIR**, or **SEIR**, which adds an Exposed stage (infected but not yet infectious) |
| Population | Total number of people (N) |
| Initial Infected | People infectious on day 0 |
| Disease Input | Enter the disease as **rates** (β, γ) or as **R₀ and mean infectious period** |
| Infection Rate / Recovery Rate | Transmission rate β and recovery rate γ, per day |
| R₀ / Mean infectious period | Converted to γ = 1 / period and β = R₀ · γ |
| Mean latent period (days) | SEIR only: average time from infection to becoming infectious (σ = 1 / period) |
| Days | Length of the simulation |
| Vaccinated (%) | Share of the initially susceptible population vaccinated on day 0 |
| Vaccine Effectiveness (%) | How well the vaccine works (meaning depends on the vaccine model) |
| Vaccine Model | **Immunity**: that % of vaccinated people are fully immune. **Partial protection**: every vaccinated person's infection risk is reduced by that %. |
| Contact Reduction (%) | Distancing or masking: lowers transmission by this % from the start day, optionally until an end day |
| Simulation steps per day | Accuracy of the numerical solution: 4 by default, 1 reproduces the original app, up to 50. The app estimates the numerical error and warns when more steps are needed. |

The app shows the compartment curves for your settings, then compares four scenarios (**no intervention**, **vaccination only**, **contact reduction only**, **both**) in one chart and a summary table. The table lists peak infected and peak day; the mean, median, and standard deviation of daily infected counts; new and cumulative infections; attack rate; infections averted; and Rₑ at day 0.

## The model

```
SIR:   S ──β·S·I/N──▶ I ──γ·I──▶ R
SEIR:  S ──β·S·I/N──▶ E ──σ·E──▶ I ──γ·I──▶ R
```

- S + E + I + R + V = N on every day. V holds vaccinated people (vaccination happens once, on day 0).
- R₀ = β / γ, the same for SIR and SEIR.
- The equations are solved with forward Euler using several steps per day.
- Main assumptions: everyone mixes equally; closed population with no deaths; permanent immunity; deterministic (no randomness).

The mean, median, and standard deviation describe the shape of one deterministic curve. They are not estimates of uncertainty or statistical significance.

**[docs/MODEL.md](docs/MODEL.md)** has the full equations, parameter table, numerical method, metric formulas, assumptions, and limitations.

## Project structure

```
main.py                 Streamlit entry point
disease_sim/
  parameters.py         Input dataclasses and validation
  interventions.py      Vaccination and contact reduction
  models.py             Shared SIR/SEIR simulation engine
  metrics.py            Summary metrics and descriptive statistics
  scenarios.py          Four-scenario comparison
  visualization.py      Charts
  interface.py          Streamlit controls and layout
tests/                  Pytest suite
docs/MODEL.md           Scientific documentation
docs/ROADMAP.md         Development plan
```

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest
ruff check .
```

The tests check that the population total is conserved and no compartment goes negative; that the SIR model at 1 step per day reproduces the original version of this app exactly; that SIR and SEIR match the Kermack–McKendrick final-size equation; that SEIR approaches SIR as the latent period shrinks; that interventions behave as expected; that metrics match hand calculations; and that invalid inputs (including NaN and infinity) are rejected.
