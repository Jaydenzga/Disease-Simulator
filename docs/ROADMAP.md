# Disease Simulator — Implementation Roadmap

Status: **Approved 2026-10-10.** Decisions are recorded at the end of this document.
Owner: Jayden (approves architecture and features) · Lead engineer: Claude Code

This document is the plan for turning the single-file Streamlit SIR demo (`main.py`) into a tested, documented, deployable epidemiological simulation app.

---

## 1. Where the project is now

| Area | Current state |
|---|---|
| Code | One script, `main.py`, about 50 lines. Sliders, simulation loop, and plotting are mixed together. |
| Model | Discrete-time SIR with a 1-day step: `new_inf = I·β·S/N`, `new_rec = I·γ`. |
| Vaccination | **Broken.** `vaccinated` is computed and plotted as a flat line, but it is never removed from `S`, so it has no effect. Plotting it next to S, I, R also makes the total look larger than `N`. |
| Plotting | Static matplotlib figure. |
| Packaging | No `requirements.txt`, README, tests, or CI. |
| Git | `main.py` has uncommitted changes (the Streamlit sliders and vaccination slider). These should be committed as the baseline before Phase 1 starts so the refactor has a clean diff. |

---

## 2. Target project structure

```
disease_simulation/
├── main.py                      # Streamlit entry point (thin: imports and calls interface.run())
├── disease_sim/                 # Importable package, no Streamlit imports outside interface.py
│   ├── __init__.py
│   ├── parameters.py            # Dataclasses: DiseaseParams, Intervention, SimulationConfig + validation
│   ├── models.py                # SIR and SEIR step functions and simulate(); returns a pandas DataFrame
│   ├── interventions.py         # Vaccination (applied at t=0) and contact reduction (time-dependent β)
│   ├── scenarios.py             # Run several named scenarios and combine results for comparison
│   ├── metrics.py               # Peak infected, peak day, attack rate, R0 / Re, etc.
│   ├── visualization.py         # Plotly figure builders (pure functions: DataFrame → Figure)
│   └── interface.py             # Streamlit layout: sidebar controls, tabs, metric cards, downloads
├── tests/
│   ├── conftest.py
│   ├── test_models.py           # Conservation, nonnegativity, regression, analytic checks
│   ├── test_interventions.py
│   ├── test_scenarios.py
│   ├── test_metrics.py
│   └── test_visualization.py    # Figures build, have the expected traces
├── docs/
│   ├── ROADMAP.md               # This file
│   └── MODEL.md                 # Equations, assumptions, parameter meanings, limitations
├── .github/workflows/tests.yml  # CI: lint + pytest
├── .streamlit/config.toml       # Theme and server settings for Streamlit Cloud
├── requirements.txt             # Runtime dependencies (read by Streamlit Cloud)
├── requirements-dev.txt         # pytest, ruff (includes -r requirements.txt)
├── pyproject.toml               # ruff and pytest configuration only (no packaging needed)
├── README.md
└── CLAUDE.md
```

Design rules:
- **The simulation core is pure Python with no Streamlit dependency.** It can be tested and imported from a notebook without a browser. Only `interface.py` imports `streamlit`.
- **The model returns data and the interface draws it.** `models.simulate()` returns a DataFrame with columns `day, S, E, I, R, V` (E is all zeros for SIR). Visualization, metrics, and CSV export all use that one format.
- **Parameters are validated in one place.** `parameters.py` rejects bad inputs (negative rates, initial infected > population, effectiveness outside 0–1) with clear errors, so the UI and tests share the same rules.

---

## 3. Dependencies

`requirements.txt` (runtime, used by Streamlit Community Cloud):

```
streamlit>=1.33
plotly>=5.18
pandas>=2.0
numpy>=1.26
```

`requirements-dev.txt`:

```
-r requirements.txt
pytest>=8.0
ruff>=0.4
```

Notes:
- **matplotlib is removed.** Plotly replaces it in Phase 3. Until then, Phase 1 keeps the matplotlib chart so the app works after each phase, and `requirements.txt` lists it temporarily.
- **No SciPy.** The models are simple enough to step directly (see §4.1), and leaving SciPy out keeps deployment light.
- I'll use lower-bound pins as above and confirm the exact versions on a clean install during Phase 4.
- **Python version:** CI tests 3.11, 3.12, and 3.13. Your local Python is 3.14. I'll check that all dependencies install on 3.14 and add it to the CI matrix if they do.

---

## 4. Scientific design

The full write-up goes in `docs/MODEL.md`. This section is the summary for approval.

### 4.1 Compartments and equations

**SIR** (preserved from the current app):

```
dS/dt = −β · S · I / N
dI/dt =  β · S · I / N − γ · I
dR/dt =  γ · I
```

**SEIR** (new): adds an Exposed (infected but not yet infectious) compartment with incubation rate σ = 1 / mean incubation period.

```
dS/dt = −β · S · I / N
dE/dt =  β · S · I / N − σ · E
dI/dt =  σ · E − γ · I
dR/dt =  γ · I
```

**V (vaccinated and protected)** is a separate compartment that both models use. It stays constant because there is no waning immunity. N = S + E + I + R + V is constant.

| Symbol | Meaning | UI control | Default |
|---|---|---|---|
| N | Total population | Population | 1,000 |
| I₀ | Initially infectious | Initial infected | 2 |
| β | Transmission rate (per day) | Infection rate | 0.05 *(matches current app)* |
| γ | Recovery rate (per day) = 1 / infectious period | Recovery rate | 0.03 *(matches current app)* |
| σ | Incubation rate (per day) = 1 / latent period | Incubation period (days), SEIR only | 5 days |
| R₀ | β / γ, shown as a derived value | Display only | — |

### 4.2 Numerical method

- Fixed-step **forward Euler** with step `dt` (default **1 day**). This is the same update the current app uses, so with default settings the refactored SIR gives the **same numbers as the original `main.py`** (enforced by a regression test).
- An optional "sub-steps per day" setting (1, 4, 10) lets users trade speed for accuracy. Output is still reported once per day.
- **Nonnegativity guard:** with large rates, a plain Euler step can push a compartment below zero. Each step limits every flow to what is in its source compartment (for example, new infections ≤ S). Every flow is subtracted from one compartment and added to another, so the total population stays exactly the same even when a flow is limited. Tests check this directly (§6).

### 4.3 Vaccination (fixes the current bug)

- **Coverage c** (0–100%) is the share of the initially susceptible population that gets vaccinated.
- **Effectiveness e** (0–100%). What it means depends on the **vaccine model**, which the user picks:

| Vaccine model | Meaning of e | At t = 0 | Infection of V over time |
|---|---|---|---|
| **All-or-nothing (immunity)** (default) | Share of vaccinated people who become fully immune | `V₀ = c · e · S₀`; the unprotected `c · (1−e) · S₀` stay in S | None: V is fully immune |
| **Leaky (partial protection)** | Reduction in each vaccinated person's chance of infection per contact | `V₀ = c · S₀` (everyone vaccinated goes to V) | V is infected at rate `(1−e) · β · I / N` (into E for SEIR, I for SIR) |

- Both modes use one V compartment with a susceptibility multiplier: 0 for all-or-nothing, `(1−e)` for leaky. This keeps the equations and the code path shared.
- With the same c and e, both modes give the same starting effective reproduction number, `Rₑ(0) = R₀ · (S₀ + m · V₀) / N`, where m is the susceptibility multiplier. They then play out differently: a leaky vaccine allows "breakthrough" infections over a long outbreak. Comparing the two is a useful teaching point and works as a scenario comparison.
- The chart shows **V (vaccinated)** as its own compartment, so the curves always add up to N.
- `Rₑ(0)` is shown so users can see when vaccination pushes it below 1, the herd-immunity threshold.

### 4.4 Contact reduction (for scenario comparisons)

- An optional non-pharmaceutical intervention, such as distancing or masking: β is multiplied by `(1 − r)` from a chosen **start day** onward, optionally until an **end day**.
- This gives a second kind of intervention to compare against vaccination, which makes scenario comparisons worthwhile.

### 4.5 Scenarios

- A **scenario** is a name plus a full set of parameters and interventions.
- Built-in comparison presets:
  1. **No intervention** (baseline)
  2. **Vaccination only**
  3. **Contact reduction only**
  4. **Vaccination + contact reduction**
- Users can edit each preset's intervention settings. Disease parameters are shared across scenarios so the comparison is fair.

### 4.6 Summary metrics (per scenario)

Peak infectious count and the day it happens, total ever infected (attack rate as a % of N), final susceptible, R₀, Rₑ at t = 0, and infections averted compared with the baseline.

### 4.7 Stated assumptions and limitations (written up in MODEL.md)

Homogeneous mixing; closed population (no births, deaths, or migration); no disease deaths; lifelong immunity after recovery or vaccination (no reinfection); deterministic (no randomness, so very small outbreaks are not modeled realistically); continuous population counts (fractional people); vaccination happens all at once at t = 0. **This is an educational model, not a forecasting tool.** The README and app will both say so.

---

## 5. Phased plan with acceptance criteria

The app stays runnable at the end of every phase. Each phase is one or more commits on a feature branch, and I'll check in with you at the end of each phase.

### Phase 1 — Fix and organize

Tasks
1. Commit the current `main.py` as the baseline.
2. Create the `disease_sim/` package: `parameters.py`, `models.py` (SIR only), `interventions.py` (vaccination), `visualization.py` (matplotlib for now), `interface.py`.
3. Reduce `main.py` to a thin entry point. `streamlit run main.py` keeps working.
4. Fix vaccination as described in §4.3. Add the effectiveness slider (default 100%, which matches the current slider's intent) and the vaccine model selector (all-or-nothing / leaky).
5. Fix the `suseptible` typo as part of the refactor.
6. Add `requirements.txt`, `requirements-dev.txt`, a minimal `pyproject.toml`, `README.md` (install, run, short model summary), and `.gitignore`.
7. Add the first tests: a regression test against the original loop, plus conservation and nonnegativity checks.

Acceptance criteria
- [ ] `streamlit run main.py` starts and shows SIR curves with the same sliders as today, plus effectiveness.
- [ ] With vaccination at 0%, results match the original `main.py` algorithm to within floating-point tolerance (`1e-9`) for the default parameters and at least two other parameter sets.
- [ ] With vaccination > 0%, S₀ drops by `c · e · S₀` (all-or-nothing) or `c · S₀` (leaky), the epidemic peak is lower or the same, and S + I + R + V = N on every day.
- [ ] With e = 100%, the two vaccine models give identical results.
- [ ] Only `interface.py` imports `streamlit`. Running `grep -r "import streamlit" disease_sim/` lists only that file.
- [ ] README instructions work from a fresh virtualenv.

### Phase 2 — Expand the science

Tasks
1. Add SEIR to `models.py` with a shared `simulate(model="SIR" | "SEIR", ...)` API.
2. Add incubation period control. Infection and recovery rates are already configurable. Add an option to enter them as **R₀ + infectious period** instead of raw rates (clinicians tend to think in those terms), and convert between the two.
3. Add sub-step `dt` support (§4.2).
4. Add contact reduction (§4.4).
5. Add `scenarios.py` and `metrics.py` (§4.5–4.6).
6. Write `docs/MODEL.md` with equations, a parameter table, the numerical method, the vaccination model, assumptions, limitations, and references (Kermack–McKendrick 1927; Keeling & Rohani, *Modeling Infectious Diseases*, 2008).

Acceptance criteria
- [ ] SEIR conserves N and stays nonnegative for all slider combinations (property-style test over a parameter grid).
- [ ] **Analytic check:** for SIR with small `dt`, the final epidemic size matches the Kermack–McKendrick final-size equation `z = 1 − exp(−R₀ · z)` (adjusted for initial conditions) to within 1%.
- [ ] **SEIR → SIR limit:** with a very short incubation period (σ large), SEIR results approach SIR results.
- [ ] **Threshold behavior:** when Rₑ < 1, infections decline from day 0 (no outbreak).
- [ ] Given the same disease parameters, vaccination and contact reduction with no end day each give lower or equal peak and total infections than baseline. (A contact reduction that ends early can cause a rebound, so it is tested separately: the run must still conserve N, and the rebound is described in MODEL.md.)
- [ ] `MODEL.md` documents every equation and assumption the code implements, and nothing more.

### Phase 3 — Interface

Tasks
1. Switch charts to Plotly: compartment curves with hover tooltips, a scenario overlay chart (infectious curves from all scenarios on one plot), and an optional log-scale toggle.
2. Dashboard layout:
   - **Sidebar:** model choice (SIR/SEIR), population and disease parameters, interventions, simulation length.
   - **Tab "Simulation":** metric cards (R₀, Rₑ, peak, peak day, attack rate), the compartment chart, and a short plain-language summary ("The epidemic peaks on day 42 with 312 people infectious…").
   - **Tab "Compare scenarios":** preset editor, overlay chart, and a comparison table with infections averted.
   - **Tab "Data":** results table and **Download CSV** buttons (single run and all scenarios in long format).
   - **Tab "About the model":** shows the content of `MODEL.md`.
3. Cache simulation results with `st.cache_data` so the app stays responsive while sliders move.
4. Drop matplotlib from dependencies.

Acceptance criteria
- [ ] All charts are Plotly with working hover, zoom, and legend toggling.
- [ ] CSV downloads open in Excel and pandas with columns `scenario, day, S, E, I, R, V`.
- [ ] Changing a slider updates results in under about 0.5 s with default settings on a laptop.
- [ ] The layout is usable at narrow (mobile) widths.
- [ ] `visualization.py` functions have tests confirming expected traces and axis labels.

### Phase 4 — Quality and deployment

Tasks
1. Complete the test suite (see §6). Target ≥ 90% line coverage of `disease_sim/` excluding `interface.py`.
2. Add a Streamlit UI smoke test using `streamlit.testing.v1.AppTest`: the app loads without exceptions and changing a slider reruns cleanly.
3. Add `ruff` linting and formatting.
4. Add a GitHub Actions workflow `.github/workflows/tests.yml`: runs on push and PR, uses a Python version matrix, installs dev requirements, runs `ruff check` and `pytest`.
5. Prepare for Streamlit Cloud: add `.streamlit/config.toml`, check that `requirements.txt` at the repo root is complete, and test a clean install in a new virtualenv.
6. README additions: CI badge, screenshot or GIF, live-app link placeholder, project structure, model summary linking to MODEL.md, how to run tests.
7. Update `CLAUDE.md` to match the new architecture.

Acceptance criteria
- [ ] `pytest` passes locally and in CI. CI shows green on `main`.
- [ ] `ruff check .` passes.
- [ ] The app starts from a fresh clone using only the README instructions.
- [ ] Deployment checklist in the README is complete. **The actual deploy is done by you** at share.streamlit.io: sign in with GitHub, select `Jaydenzga/Disease-Simulator`, branch `main`, entry file `main.py`. I can't perform that step, but I'll make sure nothing else is needed.

---

## 6. Test plan

| Category | Tests |
|---|---|
| **Conservation** | For SIR and SEIR, with and without vaccination or contact reduction, over a grid of parameters (including extreme rates near slider maxima and dt = 1): `abs(S+E+I+R+V − N) < 1e-9 · N` every day. |
| **Nonnegativity** | Same grid: every compartment ≥ 0 every day, including at maximum β and γ where a plain Euler step would overshoot. |
| **Regression** | SIR with no vaccination matches the original `main.py` loop exactly (the original loop is copied into the test as a reference). |
| **Analytic** | SIR final size vs. Kermack–McKendrick; Rₑ < 1 means no growth; I₀ = 0 means nothing changes; β = 0 means only recovery. |
| **Model relationships** | SEIR approaches SIR as incubation → 0; more vaccination coverage never increases total infections; 100% coverage × 100% effectiveness means no new infections. |
| **Validation** | Invalid parameters (negative rates, I₀ > N, effectiveness > 1, etc.) raise `ValueError` with clear messages. |
| **Metrics** | Peak and attack rate are correct on hand-built DataFrames. |
| **Visualization** | Figure builders return Plotly figures with the expected trace names. |
| **UI smoke** | `AppTest` loads `main.py` with no exceptions, and every tab renders. |

---

## 7. Out of scope (possible future work)

Disease deaths (SEIRD), waning immunity or reinfection (SEIRS), vaccination rollout over time, age-structured or network models, stochastic (Gillespie or chain-binomial) simulation, fitting to real case data. Your TODO mentions reinfection and deaths. These fit the architecture cleanly as new compartments and can be a Phase 5 if you want them.

---

## Decisions (approved 2026-10-10)

1. **Entry point:** keep `main.py`.
2. **Vaccine model:** both all-or-nothing and leaky, chosen in the UI (§4.3). All-or-nothing is the default.
3. **Numerical method:** forward Euler with daily output and optional sub-steps. No SciPy.
4. **Git workflow:** one feature branch and PR per phase. The uncommitted `main.py` is committed first as the baseline.
5. **Scope:** contact reduction is included as the second intervention type.
