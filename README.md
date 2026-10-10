# Disease Simulator

An interactive epidemic simulator built with Streamlit. Adjust population size, transmission and recovery rates, and vaccination settings, and watch how an outbreak spreads through a population under the SIR (Susceptible–Infected–Recovered) model.

> This is an educational model for exploring how epidemics behave. It is not a forecasting tool.

## Installation

Requires Python 3.11 or newer.

```bash
git clone git@github.com:Jaydenzga/Disease-Simulator.git
cd Disease-Simulator
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
streamlit run main.py
```

The app opens in your browser at http://localhost:8501. Move the sliders to change:

| Control | Meaning |
|---|---|
| Population | Total number of people (N) |
| Initial Infected | People infectious on day 0 |
| Infection Rate | Transmission rate β, per day |
| Recovery Rate | Recovery rate γ, per day (mean infectious period = 1/γ days) |
| Days | Length of the simulation |
| Vaccinated (%) | Share of the initially susceptible population vaccinated on day 0 |
| Vaccine Effectiveness (%) | How well the vaccine works (meaning depends on the vaccine model) |
| Vaccine Model | **Immunity**: that % of vaccinated people are fully immune. **Partial protection**: every vaccinated person's infection risk is reduced by that %. |

## The model

Each day, with S + I + R + V = N:

```
new infections  = β · I · S / N            (plus β · I · V / N · (1 − e) for a leaky vaccine)
new recoveries  = γ · I
```

- The basic reproduction number is R₀ = β / γ.
- Vaccination happens once, on day 0, and immunity never wanes.
- The population is closed: no births, deaths, or migration.
- Everyone mixes with everyone else equally.

## Project structure

```
main.py                 Streamlit entry point
disease_sim/
  parameters.py         Input dataclasses and validation
  interventions.py      Vaccination
  models.py             SIR simulation
  visualization.py      Charts
  interface.py          Streamlit controls and layout
tests/                  Pytest suite
docs/ROADMAP.md         Development plan
```

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest
ruff check .
```

The tests check that the population total is conserved, that no compartment goes negative, and that the SIR model reproduces the original version of this app exactly.
