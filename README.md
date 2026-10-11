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

The app opens in your browser at http://localhost:8501. It starts with an illustrative SEIR outbreak (R₀ = 2.5, N = 10,000) and both interventions switched on; **Reset to defaults** in the sidebar restores these settings at any time.

### Sidebar controls

Every control has a **?** tooltip with a plain-language explanation.

| Group | Control | Meaning |
|---|---|---|
| Model and population | Model | **SIR**, or **SEIR**, which adds an Exposed stage (infected but not yet infectious) |
| | Population | Total number of people (N) |
| | Initially infected | People infectious on day 0 |
| | Days to simulate | Length of the simulation (up to 730 days) |
| Disease | Disease preset | Fills in typical published values for COVID-19, influenza, measles, or chickenpox. Moving a disease slider switches back to **Custom**. |
| | Describe the disease by | **R₀ and mean infectious period**, or the **rates** β and γ. Switching converts the current values. |
| | R₀ / Mean infectious period | Converted to γ = 1 / period and β = R₀ · γ |
| | Infection rate β / Recovery rate γ | Transmission and recovery rates, per day |
| | Mean latent period (days) | SEIR only: average time from infection to becoming infectious (σ = 1 / period) |
| Vaccination | Vaccination coverage (%) | Share of the initially susceptible population vaccinated on day 0 |
| | Vaccine effectiveness (%) | How well the vaccine works (meaning depends on the vaccine model) |
| | Vaccine model | **Immunity**: that % of vaccinated people are fully immune. **Partial protection**: every vaccinated person's infection risk is reduced by that %. |
| Contact reduction | Contact reduction (%) | Distancing or masking: lowers transmission by this % from the start day, optionally until an end day |
| Numerical accuracy | Simulation steps per day | 4 by default, 1 reproduces the original app, up to 50 |

### Dashboard

- **Status area** (always visible): the estimated numerical error, and whether every scenario's outbreak is over by the last day.
- **Simulation:** summary cards (R₀, Rₑ at day 0, peak infected, peak day, attack rate), a one-paragraph summary in plain language, and the compartment chart with an optional logarithmic axis.
- **Compare:** the infected curves of four scenarios (**no intervention**, **vaccination only**, **contact reduction only**, **both**), bar charts of peak infected and attack rate, and a comparison table with infections averted.
- **Statistics:** the mean and median of the daily infected counts drawn on the curve, a box plot per scenario, and a descriptive-statistics table, with an explanation of how deterministic results, numerical error, and statistical uncertainty differ.
- **Data:** the daily results, with CSV downloads for your scenario, all scenarios (columns `scenario, day, S, E, I, R, V`), and the scenario summary.
- **About:** the full model description from [docs/MODEL.md](docs/MODEL.md).

Charts are interactive (hover, zoom, click a legend entry to hide a series), use colorblind-safe colors with a distinct line pattern per series, and adapt to narrow screens.

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
  presets.py            Disease presets (COVID-19, influenza, measles, ...)
  visualization.py      Plotly charts
  explain.py            Tooltips, captions, and plain-language summaries
  export.py             CSV export
  interface.py          Streamlit dashboard (the only module that imports streamlit)
.streamlit/config.toml  Theme
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

The tests check that the population total is conserved and no compartment goes negative; that the SIR model at 1 step per day reproduces the original version of this app exactly; that SIR and SEIR match the Kermack–McKendrick final-size equation; that SEIR approaches SIR as the latent period shrinks; that interventions behave as expected; that metrics match hand calculations; that charts have the expected series, axes, colors, and log-scale handling; that the dashboard's tabs, controls, reset button, CSV downloads, and caching work; and that invalid inputs (including NaN and infinity) are rejected.
