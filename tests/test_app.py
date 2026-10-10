from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import disease_sim.interface as interface
from disease_sim.parameters import VaccineModel

MAIN = str(Path(__file__).resolve().parent.parent / "main.py")


@pytest.fixture
def simulations(monkeypatch):
    """Record every simulate_sir call the app makes, with its inputs and results."""
    calls = []
    real = interface.simulate_sir

    def spy(config, disease, vaccination):
        results = real(config, disease, vaccination)
        calls.append({"vaccination": vaccination, "results": results})
        return results

    monkeypatch.setattr(interface, "simulate_sir", spy)
    return calls


def _slider(app, label):
    return next(s for s in app.slider if s.label == label)


def test_app_runs_and_reruns_on_input():
    app = AppTest.from_file(MAIN, default_timeout=30).run()
    assert not app.exception

    _slider(app, "Vaccinated (%)").set_value(60).run()
    assert not app.exception

    app.radio[0].set_value(VaccineModel.LEAKY).run()
    assert not app.exception


@pytest.mark.parametrize("model", list(VaccineModel))
def test_effectiveness_slider_changes_simulation(simulations, model):
    app = AppTest.from_file(MAIN, default_timeout=30).run()
    app.radio[0].set_value(model).run()
    _slider(app, "Infection Rate").set_value(0.3).run()
    _slider(app, "Recovery Rate").set_value(0.1).run()
    _slider(app, "Days").set_value(200).run()
    _slider(app, "Vaccinated (%)").set_value(60).run()
    full = simulations[-1]

    _slider(app, "Vaccine Effectiveness (%)").set_value(40).run()
    weaker = simulations[-1]

    assert not app.exception
    assert full["vaccination"].effectiveness == 1.0
    assert weaker["vaccination"].effectiveness == pytest.approx(0.4)
    assert weaker["vaccination"].model is model
    ever_infected = [s["results"][["I", "R"]].iloc[-1].sum() for s in (full, weaker)]
    assert ever_infected[1] > ever_infected[0]


@pytest.mark.parametrize("model", list(VaccineModel))
def test_chart_and_caption_match_vaccine_model(monkeypatch, model):
    charted_models = []
    real = interface.compartment_figure

    def spy(results, vaccine_model):
        charted_models.append(vaccine_model)
        return real(results, vaccine_model)

    monkeypatch.setattr(interface, "compartment_figure", spy)
    app = AppTest.from_file(MAIN, default_timeout=30).run()
    app.radio[0].set_value(model).run()

    assert charted_models[-1] is model
    assert [c.value for c in app.caption] == [interface.VACCINATED_CAPTIONS[model]]
