# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

An interactive epidemic simulator (Streamlit). Development follows a phased plan in `docs/ROADMAP.md`. Check it for the current phase, the approved design decisions, and acceptance criteria before adding features. The owner approves architecture and major features; work is done on one feature branch and PR per phase.

## Commands

```bash
uv venv -p 3.13 .venv && uv pip install -p .venv -r requirements-dev.txt   # or python -m venv + pip
.venv/bin/streamlit run main.py           # run the app
.venv/bin/python -m pytest                # all tests
.venv/bin/python -m pytest tests/test_models.py::test_vaccine_models_agree_at_full_effectiveness
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

## Architecture

- `main.py` is only the Streamlit entry point. It calls `disease_sim.interface.run()`. Keep the name: Streamlit Community Cloud deployment is configured to use it.
- `disease_sim/` is the simulation package. **Only `interface.py` may import `streamlit`.** Everything else is pure Python so it can be tested without a browser.
- Data flow: `parameters.py` frozen dataclasses (validated in `__post_init__`, including NaN/∞ rejection) → `models.simulate()` → a DataFrame with columns `day, S, E, I, R, V` (day 0 is the initial state; E is all zeros for SIR) → `metrics.summarize()` and `visualization.py`. `scenarios.run_scenarios()` runs several scenarios and returns the same columns plus `scenario` (long format).
- SIR and SEIR share one engine in `models.simulate()`; `DiseaseParams.model` picks which. `simulate_sir()` is a Phase 1 alias.
- Time stepping: forward Euler with `SimulationConfig.steps_per_day` steps per day (default 4; 1 is the legacy setting). Output is daily. The app estimates numerical error by step doubling (`models.estimate_step_error`, rerun at 2× steps) and warns above `STEP_ERROR_TOLERANCE`.
- Vaccination (`interventions.apply_vaccination`) runs once at day 0 and returns a susceptibility multiplier for V. It is 0 for all-or-nothing and `1 − effectiveness` for leaky. Both vaccine models share one code path through that multiplier.
- Contact reduction multiplies β by `(1 − reduction)` for each step that starts in `[start_day, end_day)`.
- Dashboard (`interface.py`): sidebar → cached `_compute()` (`st.cache_data` on the frozen input dataclasses) → status area (step error, unfinished outbreaks) → five tabs. Every widget's value goes through `_kept(key)`, which mirrors it into `_kept_<key>` session state and clamps it to the current range. Without this, Streamlit resets a widget whose range changes and forgets a hidden widget's value. `DEFAULTS` holds every default, and "Reset to defaults" writes them back. Add new widgets the same way.
- UI wording (tooltips, captions, run summary, status messages) lives in `explain.py`; CSV export in `export.py`. Both are pure so tests check them directly. Figures in `visualization.py` take fixed colors and line patterns per compartment and per scenario name. On log axes, values below `LOG_FLOOR` are hidden with a note.
- App tests (`tests/test_app.py`) use `AppTest`. Results are cached across runs, so the autouse fixture clears `_compute`. A test that expects a recomputation after returning to earlier settings must clear the cache first. Look up widgets by label, not index: main-area widgets come before sidebar widgets in `AppTest` lists.
- `docs/MODEL.md` must describe exactly what the code implements. Update it with any change to equations, metrics, or assumptions.

## Invariants the tests enforce

- With no vaccination and `steps_per_day=1`, SIR output must match the original `main.py` loop (copied into `tests/test_models.py`) to within 1e-9. Do not change the update rule (forward Euler, simultaneous update) without updating that test deliberately.
- S + E + I + R + V = N on every day, and no compartment goes negative, including at rates far above the slider limits. Each flow is capped at the size of its source compartment to guarantee this.
