from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import disease_sim.interface as interface
from disease_sim.parameters import ModelType, VaccineModel
from disease_sim.scenarios import COMBINED, CONTACT_REDUCTION_ONLY, NO_INTERVENTION

MAIN = str(Path(__file__).resolve().parent.parent / "main.py")


@pytest.fixture
def simulations(monkeypatch):
    """Record every run_scenarios call the app makes, with its inputs and results."""
    calls = []
    real = interface.run_scenarios

    def spy(config, disease, scenarios):
        results = real(config, disease, scenarios)
        by_name = {s.name: s for s in scenarios}
        calls.append(
            {
                "config": config,
                "disease": disease,
                "scenarios": by_name,
                "vaccination": by_name[COMBINED].vaccination,
                "results": results,
            }
        )
        return results

    monkeypatch.setattr(interface, "run_scenarios", spy)
    return calls


def _app():
    return AppTest.from_file(MAIN, default_timeout=30).run()


def _slider(app, label):
    return next(s for s in app.slider if s.label == label)


def _radio(app, label):
    return next(r for r in app.radio if r.label == label)


def _combined(call):
    results = call["results"]
    return results[results["scenario"] == COMBINED]


def test_app_runs_and_reruns_on_input():
    app = _app()
    assert not app.exception

    _slider(app, "Vaccinated (%)").set_value(60).run()
    assert not app.exception

    _radio(app, "Vaccine Model").set_value(VaccineModel.LEAKY).run()
    assert not app.exception


def test_defaults_preserve_phase_1_settings(simulations):
    _app()
    call = simulations[-1]
    assert call["disease"].model is ModelType.SIR
    assert (call["disease"].infection_rate, call["disease"].recovery_rate) == (0.05, 0.03)
    assert (call["config"].population, call["config"].initial_infected) == (1000, 2)
    assert call["config"].days == 30
    assert call["config"].steps_per_day == 4


@pytest.mark.parametrize("model", list(VaccineModel))
def test_effectiveness_slider_changes_simulation(simulations, model):
    app = _app()
    _radio(app, "Vaccine Model").set_value(model).run()
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
    ever_infected = [_combined(s)[["I", "R"]].iloc[-1].sum() for s in (full, weaker)]
    assert ever_infected[1] > ever_infected[0]


@pytest.mark.parametrize("model", list(VaccineModel))
def test_chart_and_caption_match_vaccine_model(monkeypatch, model):
    charted_models = []
    real = interface.compartment_figure

    def spy(results, vaccine_model, **kwargs):
        charted_models.append(vaccine_model)
        return real(results, vaccine_model, **kwargs)

    monkeypatch.setattr(interface, "compartment_figure", spy)
    app = _app()
    _radio(app, "Vaccine Model").set_value(model).run()

    assert charted_models[-1] is model
    captions = [c.value for c in app.caption]
    assert interface.VACCINATED_CAPTIONS[model] in captions
    assert interface.VACCINATED_CAPTIONS[next(m for m in VaccineModel if m != model)] not in (
        captions
    )


def test_latent_period_slider_only_for_seir(simulations):
    app = _app()
    labels = [s.label for s in app.slider]
    assert "Mean latent period (days)" not in labels

    _radio(app, "Model").set_value(ModelType.SEIR).run()
    _slider(app, "Mean latent period (days)").set_value(8.0).run()
    assert not app.exception
    disease = simulations[-1]["disease"]
    assert disease.model is ModelType.SEIR
    assert disease.mean_latent_period == pytest.approx(8.0)
    assert (_combined(simulations[-1])["E"].iloc[1:] > 0).all()


def test_r0_input_mode_converts_to_rates(simulations):
    app = _app()
    _radio(app, "Disease Input").set_value(interface.R0_INPUT).run()
    _slider(app, "R₀").set_value(3.0).run()
    _slider(app, "Mean infectious period (days)").set_value(5.0).run()
    assert not app.exception
    disease = simulations[-1]["disease"]
    assert disease.recovery_rate == pytest.approx(0.2)
    assert disease.infection_rate == pytest.approx(0.6)


def test_contact_reduction_controls(simulations):
    app = _app()
    _slider(app, "Days").set_value(100).run()
    _slider(app, "Contact Reduction (%)").set_value(40).run()
    _slider(app, "Reduction starts on day").set_value(10).run()
    app.checkbox[0].check().run()
    _slider(app, "Reduction ends on day").set_value(50).run()
    assert not app.exception

    contact = simulations[-1]["scenarios"][CONTACT_REDUCTION_ONLY].contact_reduction
    assert (contact.reduction, contact.start_day, contact.end_day) == (
        pytest.approx(0.4),
        10,
        50,
    )
    assert simulations[-1]["scenarios"][NO_INTERVENTION].contact_reduction.reduction == 0


def test_legacy_steps_per_day_selectable(simulations):
    app = _app()
    app.selectbox[0].set_value(1).run()
    assert not app.exception
    assert simulations[-1]["config"].steps_per_day == 1


def test_comparison_table_lists_all_scenarios():
    app = _app()
    table = app.dataframe[0].value
    assert len(table) == 4
    assert "Mean infected" in table.columns
    assert "SD infected" in table.columns
    assert interface.STATISTICS_CAPTION in [c.value for c in app.caption]
