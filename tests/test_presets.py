import re
from pathlib import Path

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


# The approved values. A change here must be a deliberate, documented scientific
# correction: update docs/MODEL.md §2 (table and evidence) in the same commit.
APPROVED = {
    "COVID-19 (original strain, 2020)": (2.5, 5.0, 3.0, "about 2–3.5"),
    "COVID-19 (Delta variant, 2021)": (5.0, 5.0, 2.0, "about 3–8"),
    "Seasonal influenza": (1.3, 4.0, 2.0, "about 1.2–1.4"),
    "1918 pandemic influenza": (2.0, 4.0, 2.0, "about 1.5–3"),
    "Measles": (15.0, 5.0, 8.0, "about 12–18"),
    "Chickenpox": (10.0, 7.0, 14.0, "about 7–12"),
}


def test_preset_values_are_the_approved_ones():
    actual = {p.name: (p.r0, p.infectious_period, p.latent_period, p.r0_range) for p in PRESETS}
    assert actual == APPROVED


def test_model_doc_lists_every_preset_with_its_values():
    text = (Path(__file__).resolve().parent.parent / "docs" / "MODEL.md").read_text("utf-8")
    for preset in PRESETS:
        row = (
            f"| {preset.name} | {preset.r0:g} | {preset.r0_range} | "
            f"{preset.infectious_period:g} days | {preset.latent_period:g} days |"
        )
        assert row in text, row


@pytest.mark.parametrize("preset", PRESETS, ids=lambda p: p.name)
def test_preset_r0_lies_in_its_published_range(preset):
    low, high = (float(x) for x in re.findall(r"[\d.]+", preset.r0_range))
    assert low <= preset.r0 <= high
    assert preset.r0 > 1  # every preset is a disease that can cause an outbreak


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
    assert "not a forecast" in text
