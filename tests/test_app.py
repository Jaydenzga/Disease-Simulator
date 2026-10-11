import warnings
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import disease_sim.interface as interface
from disease_sim import explain
from disease_sim.parameters import ModelType, VaccineModel
from disease_sim.scenarios import COMBINED, CONTACT_REDUCTION_ONLY, NO_INTERVENTION

MAIN = str(Path(__file__).resolve().parent.parent / "main.py")


@pytest.fixture(autouse=True)
def fresh_cache():
    """Results are cached across app runs; start every test without them."""
    interface._compute.clear()
    yield
    interface._compute.clear()


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
                "contact": by_name[COMBINED].contact_reduction,
                "results": results,
            }
        )
        return results

    monkeypatch.setattr(interface, "run_scenarios", spy)
    return calls


@pytest.fixture
def figure_calls(monkeypatch):
    """Record the arguments of every call to the figure builders the app uses."""
    calls = {}

    def record(name):
        real = getattr(interface, name)

        def spy(*args, **kwargs):
            calls.setdefault(name, []).append((args, kwargs))
            return real(*args, **kwargs)

        monkeypatch.setattr(interface, name, spy)

    for name in (
        "compartment_figure",
        "scenario_comparison_figure",
        "infected_statistics_figure",
    ):
        record(name)
    return calls


def _app():
    return AppTest.from_file(MAIN, default_timeout=30).run()


def _labels(elements):
    return [e.label for e in elements]


def _slider(app, label):
    return next(s for s in app.slider if s.label == label)


def _radio(app, label):
    return next(r for r in app.radio if r.label == label)


def _steps(app):
    return next(s for s in app.selectbox if s.label == "Simulation steps per day")


def _number(app, label):
    return next(n for n in app.number_input if n.label == label)


def _combined(call):
    results = call["results"]
    return results[results["scenario"] == COMBINED]


def _warnings(app):
    return [w.value for w in app.warning]


def _successes(app):
    return [s.value for s in app.success]


# --- Layout ---------------------------------------------------------------------------


def test_app_runs_with_five_tabs_and_no_warnings():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        app = _app()
    assert not app.exception
    assert [t.label for t in app.tabs] == ["Simulation", "Compare", "Statistics", "Data", "About"]
    unexpected = [w for w in caught if not issubclass(w.category, ResourceWarning)]
    assert not unexpected, [str(w.message) for w in unexpected]


def test_status_area_shows_accuracy_and_outbreak_status():
    app = _app()
    # Defaults: error within tolerance; the combined SEIR scenario has not finished.
    assert any(s.startswith("Estimated numerical error: about") for s in _successes(app))
    (unfinished,) = [w for w in _warnings(app) if w.startswith("Outbreak not over")]
    assert f"day 365 in: {COMBINED}." in unfinished

    _slider(app, "Days to simulate").set_value(730).run()
    assert not any(w.startswith("Outbreak not over") for w in _warnings(app))
    assert explain.FINISHED_MESSAGE.format(days=730) in _successes(app)


def test_summary_cards_and_run_summary(simulations):
    app = _app()
    cards = {m.label: m.value for m in app.metric}
    assert list(cards) == ["R₀", "Rₑ at day 0", "Peak infected", "Peak day", "Attack rate"]
    assert cards["R₀"] == "2.50"
    assert cards["Attack rate"].endswith("%")
    assert all(m.help for m in app.metric)
    summary_text = [m.value for m in app.markdown if m.value.startswith("Infections peak")]
    assert summary_text and f"peak on day {cards['Peak day']}," in summary_text[0]


def test_every_control_has_a_tooltip():
    app = _app()
    for group in (app.slider, app.radio, app.number_input, app.selectbox, app.checkbox):
        for widget in group:
            assert widget.help, widget.label


# --- Defaults and reset ---------------------------------------------------------------


def test_defaults_are_the_approved_illustrative_settings(simulations):
    _app()
    call = simulations[-1]
    disease, config = call["disease"], call["config"]
    assert disease.model is ModelType.SEIR
    assert disease.basic_reproduction_number == pytest.approx(2.5)
    assert disease.mean_infectious_period == pytest.approx(7.0)
    assert disease.mean_latent_period == pytest.approx(5.0)
    assert (config.population, config.initial_infected, config.days) == (10_000, 10, 365)
    assert config.steps_per_day == 4
    vaccination, contact = call["vaccination"], call["contact"]
    assert (vaccination.coverage, vaccination.effectiveness) == pytest.approx((0.3, 0.9))
    assert vaccination.model is VaccineModel.ALL_OR_NOTHING
    assert (contact.reduction, contact.start_day, contact.end_day) == (
        pytest.approx(0.3),
        14,
        None,
    )


def test_reset_restores_every_setting(simulations):
    app = _app()
    defaults = simulations[-1]
    _radio(app, "Model").set_value(ModelType.SIR).run()
    _number(app, "Population").set_value(5_000).run()
    _number(app, "Initially infected").set_value(50).run()
    _slider(app, "Days to simulate").set_value(200).run()
    _radio(app, "Describe the disease by").set_value(interface.RATES_INPUT).run()
    _slider(app, "Infection rate β (per day)").set_value(0.5).run()
    _slider(app, "Vaccination coverage (%)").set_value(80).run()
    _radio(app, "Vaccine model").set_value(VaccineModel.LEAKY).run()
    _slider(app, "Reduction starts on day").set_value(40).run()
    app.checkbox[0].check().run()
    _slider(app, "Reduction ends on day").set_value(100).run()
    _steps(app).set_value(20).run()
    app.toggle[0].set_value(True).run()
    assert simulations[-1]["config"] != defaults["config"]

    interface._compute.clear()  # so the reset run is recorded, not served from the cache
    app.button[0].click().run()
    assert not app.exception
    after = simulations[-1]
    for key in ("config", "disease", "vaccination", "contact"):
        assert after[key] == defaults[key], key
    assert _radio(app, "Describe the disease by").value == interface.R0_INPUT
    assert not app.checkbox[0].value
    assert not any(t.value for t in app.toggle)

    # Settings hidden at the time of the reset come back at their defaults too.
    app.checkbox[0].check().run()
    assert _slider(app, "Reduction ends on day").value == 365


# --- Disease and population controls ---------------------------------------------------


def test_latent_period_slider_only_for_seir(simulations):
    app = _app()
    _slider(app, "Mean latent period (days)").set_value(8.0).run()
    disease = simulations[-1]["disease"]
    assert disease.mean_latent_period == pytest.approx(8.0)
    assert (_combined(simulations[-1])["E"].iloc[1:] > 0).all()

    _radio(app, "Model").set_value(ModelType.SIR).run()
    assert "Mean latent period (days)" not in _labels(app.slider)
    assert simulations[-1]["disease"].model is ModelType.SIR
    assert (_combined(simulations[-1])["E"] == 0).all()


def test_switching_input_mode_keeps_the_disease(simulations):
    app = _app()
    _slider(app, "R₀").set_value(3.0).run()
    _slider(app, "Mean infectious period (days)").set_value(5.0).run()

    _radio(app, "Describe the disease by").set_value(interface.RATES_INPUT).run()
    assert _slider(app, "Infection rate β (per day)").value == pytest.approx(0.6)
    assert _slider(app, "Recovery rate γ (per day)").value == pytest.approx(0.2)
    disease = simulations[-1]["disease"]
    assert (disease.infection_rate, disease.recovery_rate) == pytest.approx((0.6, 0.2))

    _slider(app, "Infection rate β (per day)").set_value(0.4).run()
    _radio(app, "Describe the disease by").set_value(interface.R0_INPUT).run()
    assert _slider(app, "R₀").value == pytest.approx(2.0)
    assert _slider(app, "Mean infectious period (days)").value == pytest.approx(5.0)
    assert not app.exception


def test_initial_infected_cannot_exceed_population(simulations):
    app = _app()
    _number(app, "Population").set_value(1_000).run()
    _number(app, "Initially infected").set_value(1_000).run()
    _number(app, "Population").set_value(100).run()
    assert not app.exception
    assert _number(app, "Initially infected").value == 100
    assert simulations[-1]["config"].initial_infected == 100


def test_legacy_steps_per_day_selectable(simulations):
    app = _app()
    _steps(app).set_value(1).run()
    assert not app.exception
    assert simulations[-1]["config"].steps_per_day == 1


# --- Interventions ----------------------------------------------------------------------


@pytest.mark.parametrize("model", list(VaccineModel))
def test_effectiveness_slider_changes_simulation(simulations, model):
    app = _app()
    _radio(app, "Vaccine model").set_value(model).run()
    _slider(app, "Vaccination coverage (%)").set_value(60).run()
    _slider(app, "Vaccine effectiveness (%)").set_value(100).run()
    full = simulations[-1]
    _slider(app, "Vaccine effectiveness (%)").set_value(40).run()
    weaker = simulations[-1]

    assert not app.exception
    assert full["vaccination"].effectiveness == 1.0
    assert weaker["vaccination"].effectiveness == pytest.approx(0.4)
    assert weaker["vaccination"].model is model
    ever_infected = [_combined(s)[["E", "I", "R"]].iloc[-1].sum() for s in (full, weaker)]
    assert ever_infected[1] > ever_infected[0]


@pytest.mark.parametrize("model", list(VaccineModel))
def test_chart_and_caption_match_vaccine_model(figure_calls, model):
    app = _app()
    _radio(app, "Vaccine model").set_value(model).run()
    args, _ = figure_calls["compartment_figure"][-1]
    assert args[1] is model
    captions = [c.value for c in app.caption]
    assert explain.VACCINATED_CAPTIONS[model] in captions
    other = next(m for m in VaccineModel if m != model)
    assert explain.VACCINATED_CAPTIONS[other] not in captions


def test_contact_reduction_controls(simulations):
    app = _app()
    _slider(app, "Days to simulate").set_value(100).run()
    _slider(app, "Contact reduction (%)").set_value(40).run()
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


def test_reduction_starting_on_the_last_day_cannot_be_lifted(simulations):
    app = _app()
    _slider(app, "Days to simulate").set_value(30).run()
    app.checkbox[0].check().run()
    _slider(app, "Reduction ends on day").set_value(29).run()
    # Moving the start to the last possible day leaves no valid end day.
    _slider(app, "Reduction starts on day").set_value(29).run()
    assert not app.exception
    assert app.checkbox[0].disabled
    assert "Reduction ends on day" not in _labels(app.slider)
    assert (simulations[-1]["contact"].start_day, simulations[-1]["contact"].end_day) == (29, None)


def _reduction_days(app):
    labels = _labels(app.slider)
    return tuple(
        _slider(app, label).value if label in labels else None
        for label in ("Reduction starts on day", "Reduction ends on day")
    )


def test_reduction_days_survive_lengthening_the_simulation(simulations):
    app = _app()
    _slider(app, "Days to simulate").set_value(100).run()
    _slider(app, "Reduction starts on day").set_value(10).run()
    app.checkbox[0].check().run()
    _slider(app, "Reduction ends on day").set_value(50).run()

    _slider(app, "Days to simulate").set_value(150).run()
    assert not app.exception
    assert _reduction_days(app) == (10, 50)
    assert (simulations[-1]["contact"].start_day, simulations[-1]["contact"].end_day) == (10, 50)


def test_reduction_days_are_clamped_when_shortening_the_simulation():
    app = _app()
    _slider(app, "Days to simulate").set_value(100).run()
    _slider(app, "Reduction starts on day").set_value(30).run()
    app.checkbox[0].check().run()
    _slider(app, "Reduction ends on day").set_value(80).run()

    _slider(app, "Days to simulate").set_value(60).run()  # end day 80 no longer fits
    assert _reduction_days(app) == (30, 60)

    _slider(app, "Days to simulate").set_value(20).run()  # neither fits; nothing left to lift
    assert _reduction_days(app) == (19, None)
    assert app.checkbox[0].disabled

    _slider(app, "Days to simulate").set_value(100).run()  # lengthening keeps the clamped values
    assert not app.exception
    assert _reduction_days(app) == (19, 60)


def test_end_day_follows_a_later_start_day(simulations):
    app = _app()
    _slider(app, "Days to simulate").set_value(100).run()
    app.checkbox[0].check().run()
    _slider(app, "Reduction ends on day").set_value(40).run()
    _slider(app, "Reduction starts on day").set_value(60).run()
    assert _reduction_days(app) == (60, 61)
    assert (simulations[-1]["contact"].start_day, simulations[-1]["contact"].end_day) == (60, 61)


# --- Numerical accuracy -------------------------------------------------------------------


def test_step_size_warning_for_fast_rates():
    app = _app()
    assert not any("Numerical error" in w for w in _warnings(app))

    _radio(app, "Model").set_value(ModelType.SIR).run()
    _slider(app, "R₀").set_value(4.0).run()
    _slider(app, "Mean infectious period (days)").set_value(1.0).run()
    warning = next(w for w in _warnings(app) if "Numerical error" in w)
    assert "Choose at least 50 steps per day" in warning

    _steps(app).set_value(50).run()
    assert not app.exception
    assert not any("Numerical error" in w for w in _warnings(app))


# --- Charts and tabs ------------------------------------------------------------------------


def test_log_toggles_switch_their_own_chart(figure_calls):
    app = _app()
    assert figure_calls["compartment_figure"][-1][1]["log_y"] is False
    assert figure_calls["scenario_comparison_figure"][-1][1]["log_y"] is False

    sim_toggle, compare_toggle = app.toggle
    sim_toggle.set_value(True).run()
    assert figure_calls["compartment_figure"][-1][1]["log_y"] is True
    assert figure_calls["scenario_comparison_figure"][-1][1]["log_y"] is False

    compare_toggle.set_value(True).run()
    assert figure_calls["scenario_comparison_figure"][-1][1]["log_y"] is True


def test_comparison_table_lists_all_scenarios():
    app = _app()
    table = app.dataframe[0].value
    assert list(table.columns) == _scenario_names()
    assert [label for label, _ in interface.COMPARISON_ROWS.values()] == list(table.index)
    assert table.loc["Still infected at end", NO_INTERVENTION] == "No"
    assert table.loc["Still infected at end", COMBINED] == "Yes"
    assert table.loc["Infections averted (by last day)", NO_INTERVENTION] == "0"


def _scenario_names():
    return [NO_INTERVENTION, "Vaccination only", CONTACT_REDUCTION_ONLY, COMBINED]


def test_statistics_tab_explains_scope_and_follows_the_chosen_scenario(figure_calls):
    app = _app()
    assert explain.STATISTICS_SCOPE in [i.value for i in app.info]
    shown = " ".join(m.value for m in app.markdown)
    for title, _ in explain.THREE_KINDS:
        assert f"**{title}**" in shown
    assert explain.STATISTICS_CAPTION in [c.value for c in app.caption]

    stats = app.dataframe[1].value
    assert list(stats.index) == _scenario_names()
    assert list(stats.columns) == list(interface.STATISTICS_COLUMNS.values())

    assert "Scenario" in _labels(app.selectbox)
    next(s for s in app.selectbox if s.label == "Scenario").set_value(NO_INTERVENTION).run()
    _, kwargs = figure_calls["infected_statistics_figure"][-1]
    assert kwargs["title"].endswith(NO_INTERVENTION)


def test_data_tab_offers_three_csv_downloads():
    app = _app()
    downloads = app.get("download_button")
    assert [d.proto.label for d in downloads] == [
        "Your scenario (CSV)",
        "All scenarios (CSV)",
        "Scenario summary (CSV)",
    ]
    your_scenario = app.dataframe[2].value
    assert list(your_scenario.columns) == ["day", "S", "E", "I", "R", "V"]
    assert len(your_scenario) == 366


def test_about_tab_shows_the_model_description():
    app = _app()
    model_doc = interface.MODEL_DOC.read_text(encoding="utf-8")
    assert model_doc.strip() in [m.value.strip() for m in app.markdown]


# --- Caching ---------------------------------------------------------------------------------


def test_results_are_cached_across_reruns(simulations):
    app = _app()
    assert len(simulations) == 1
    app.toggle[0].set_value(True).run()  # display-only change
    assert len(simulations) == 1

    _slider(app, "Vaccination coverage (%)").set_value(50).run()
    assert len(simulations) == 2
    _slider(app, "Vaccination coverage (%)").set_value(30).run()  # back to cached settings
    assert len(simulations) == 2
    assert not app.exception
