import pytest

import disease_sim.interface as interface
from disease_sim import explain
from disease_sim.models import simulate
from disease_sim.parameters import ModelType, SimulationConfig
from disease_sim.presets import CUSTOM, PRESETS, PRESETS_BY_NAME


def test_preset_names_are_unique_and_not_custom():
    names = [p.name for p in PRESETS]
    assert len(set(names)) == len(names)
    assert CUSTOM not in names
    assert set(PRESETS_BY_NAME) == set(names)


def _on_slider(value, value_range):
    low, high, step = value_range
    return low <= value <= high and abs(round(value / step) * step - value) < 1e-9


@pytest.mark.parametrize("preset", PRESETS, ids=lambda p: p.name)
def test_preset_fits_the_sliders_in_both_input_modes(preset):
    assert _on_slider(preset.r0, interface.R0_RANGE)
    assert _on_slider(preset.infectious_period, interface.INFECTIOUS_PERIOD_RANGE)
    assert _on_slider(preset.latent_period, interface.LATENT_PERIOD_RANGE)
    disease = preset.disease()
    low, high, _ = interface.INFECTION_RATE_RANGE
    assert low <= disease.infection_rate <= high
    low, high, _ = interface.RECOVERY_RATE_RANGE
    assert low <= disease.recovery_rate <= high


@pytest.mark.parametrize("preset", PRESETS, ids=lambda p: p.name)
@pytest.mark.parametrize("model", list(ModelType))
def test_preset_disease_matches_its_values_and_simulates(preset, model):
    disease = preset.disease(model)
    assert disease.model is model
    assert disease.basic_reproduction_number == pytest.approx(preset.r0)
    assert disease.mean_infectious_period == pytest.approx(preset.infectious_period)
    assert disease.mean_latent_period == pytest.approx(preset.latent_period)
    config = SimulationConfig(10_000, 10, 365)
    df = simulate(config, disease)
    total = df[["S", "E", "I", "R", "V"]].sum(axis=1)
    assert (total - 10_000).abs().max() < 1e-6
    assert (df[["S", "E", "I", "R", "V"]] >= 0).all().all()


def test_preset_caption_states_values_and_limits():
    measles = PRESETS_BY_NAME["Measles"]
    text = explain.preset_caption(measles)
    assert "R₀ 15" in text and measles.r0_range in text
    assert "infectious for 5 days" in text and "latent for 8 days" in text
    assert "no deaths" in text
