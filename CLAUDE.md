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
- Data flow: `parameters.py` dataclasses (validated in `__post_init__`) → `models.simulate_sir()` → a DataFrame with columns `day, S, I, R, V` (day 0 is the initial state) → `visualization.py` builds a figure from that DataFrame.
- Vaccination (`interventions.apply_vaccination`) runs once at day 0 and returns a susceptibility multiplier for V. It is 0 for all-or-nothing and `1 − effectiveness` for leaky. Both vaccine models share one code path through that multiplier.

## Invariants the tests enforce

- With no vaccination, SIR output must match the original `main.py` loop (copied into `tests/test_models.py`) to within 1e-9. Do not change the update rule (forward Euler, 1-day step) without updating that test deliberately.
- S + I + R + V = N on every day, and no compartment goes negative, including at rates far above the slider limits. Each flow is capped at the size of its source compartment to guarantee this.
