from pathlib import Path

from streamlit.testing.v1 import AppTest

from disease_sim.parameters import VaccineModel

MAIN = str(Path(__file__).resolve().parent.parent / "main.py")


def test_app_runs_and_reruns_on_input():
    app = AppTest.from_file(MAIN, default_timeout=30).run()
    assert not app.exception

    vaccinated = next(s for s in app.slider if s.label == "Vaccinated (%)")
    vaccinated.set_value(60).run()
    assert not app.exception

    app.radio[0].set_value(VaccineModel.LEAKY).run()
    assert not app.exception
