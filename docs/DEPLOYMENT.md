# Deployment

The recommended host is **Streamlit Community Cloud**, which is free for public apps and deploys straight from this GitHub repository. Nothing has been deployed yet; the steps below are for the repository owner.

## Pre-deployment checklist

These were checked on 2026-10-11 (Phase 4):

| Check | Status |
|---|---|
| Entry file | `main.py` at the repository root. It only calls `disease_sim.interface.run()`. |
| Dependencies | `requirements.txt` at the root: a lock file with exact versions, generated from `requirements.in`. Streamlit Cloud installs it automatically. |
| Python version | Tested on 3.11, 3.12, 3.13, and 3.14 in CI. Choose **3.13** when deploying. |
| Clean install | A fresh virtual environment with `pip install -r requirements-dev.txt` passes every test on Python 3.11, 3.12, and 3.14, and `streamlit run main.py` starts and answers its health check. CI repeats this on every push. |
| Secrets and environment variables | None needed. The app reads no API keys, tokens, or environment variables. `.streamlit/secrets.toml` and `.env` are in `.gitignore` as a precaution. |
| Exposed credentials | The full git history was searched for keys, tokens, passwords, and private keys: none found. |
| Configuration | `.streamlit/config.toml` sets the theme and turns off usage statistics. |
| Resource use | The heaviest allowed input (1,000,000 people, 730 days, 50 steps per day, all four scenarios plus the accuracy check) runs in about 0.2 s and produces about 220 KB of results. The results cache keeps at most 64 entries. |
| Input limits | Every slider and number box has a fixed range, and a test checks that out-of-range values sent to the app never reach the simulation. |

## Deploy on Streamlit Community Cloud

These steps follow Streamlit's documentation as of 2026-10-11 ([Deploy your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)). Button names may change slightly over time.

1. Make sure the CI badge on `main` is green.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub. Authorize Streamlit to access your repositories when asked.
3. Click **Create app** in the upper-right corner. When asked whether you already have an app, choose **Yup, I have an app**.
4. Fill in:
   - **Repository:** `Jaydenzga/Disease-Simulator`
   - **Branch:** `main`
   - **Main file path:** `main.py`
   - **App URL (optional):** a custom subdomain, for example `disease-simulator`. If left blank, Community Cloud generates a long one.
5. Open **Advanced settings**. Change **Python version** from the default (3.12) to **3.13**, and leave **Secrets** empty.
6. Click **Save**. The app starts building; the first build takes a few minutes while it installs `requirements.txt`. The build log is shown beside the app.
7. When the app loads, check it on a computer and a phone: change a slider, choose a disease preset, open every tab, and download a CSV.
8. Replace the "Live demo" placeholder at the top of `README.md` with the app's URL, and add the URL as the repository's website in GitHub (**About → ⚙ → Website**).

After this, every push to `main` updates the app automatically.

### How Community Cloud reads this repository

- It looks for one dependency file, first next to `main.py` and then at the repository root, and uses the first it finds in this order: `uv.lock`, `Pipfile`, `environment.yml`, `requirements.txt`, `pyproject.toml`. This repository has `requirements.txt` (the lock file) and a `pyproject.toml` that only configures Ruff and pytest, so `requirements.txt` is used. **Do not add a `uv.lock`, `Pipfile`, or `environment.yml`**, or it would be used instead.
- `requirements.in`, `requirements-dev.txt`, and `ci/` are ignored by Community Cloud.
- It installs `requirements.txt` with uv, falling back to pip.

### Things to know about the free tier

From [Manage your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app) (Streamlit's stated limits are approximate and subject to change):

- **Sleep:** an app with no traffic for 12 hours goes to sleep. The next visitor clicks **Yes, get this app back up!** and waits briefly.
- **Resources:** up to about 2 CPU cores and 2.7 GB of memory, shared. This app needs far less: the heaviest allowed settings compute in about 0.2 s, and the results cache is capped at 64 entries of about 220 KB each.
- **Cost:** Community Cloud is free, and its documentation describes no usage-based charges, so heavy public use can slow the app down but should not create costs. GitHub Actions is also free for public repositories.
- The app is public: anyone with the link can use it. That is fine because it stores nothing and needs no secrets.

## Run it like the deployed app

To reproduce the cloud environment locally:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run main.py
```

## Free alternatives

Use these only if Streamlit Community Cloud is unavailable:

- **Hugging Face Spaces** (free CPU tier): create a Space and run the app in a Docker container that installs `requirements.txt` and runs `streamlit run main.py --server.port 7860 --server.address 0.0.0.0`.
- **Render** (free web service tier): build command `pip install -r requirements.txt`, start command `streamlit run main.py --server.port $PORT --server.address 0.0.0.0`. Free services sleep when idle and start slowly.

Both need small configuration changes that are not in this repository yet.
