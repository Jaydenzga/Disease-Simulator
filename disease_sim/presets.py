"""Disease presets: rounded, typical published values for well-known infections.

Each preset fills in R0 and the mean infectious and latent periods. They are
starting points for exploring the model, not fitted estimates: published values
vary by place, time, and method, and this model leaves out deaths, prior
immunity, and differences between people. Sources are listed in docs/MODEL.md.
"""

from dataclasses import dataclass

from disease_sim.parameters import DiseaseParams, ModelType

CUSTOM = "Custom"


@dataclass(frozen=True)
class DiseasePreset:
    name: str
    r0: float
    infectious_period: float  # days
    latent_period: float  # days
    r0_range: str  # spread of published R0 estimates, for display

    def disease(self, model: ModelType = ModelType.SEIR) -> DiseaseParams:
        return DiseaseParams.from_r0(self.r0, self.infectious_period, self.latent_period, model)


PRESETS = (
    DiseasePreset("COVID-19 (original strain, 2020)", 2.5, 5.0, 3.0, "about 2–3.5"),
    DiseasePreset("COVID-19 (Delta variant, 2021)", 5.0, 5.0, 2.0, "about 3–8"),
    DiseasePreset("Seasonal influenza", 1.3, 4.0, 2.0, "about 1.2–1.4"),
    DiseasePreset("1918 pandemic influenza", 2.0, 4.0, 2.0, "about 1.5–3"),
    DiseasePreset("Measles", 15.0, 5.0, 8.0, "about 12–18"),
    DiseasePreset("Chickenpox", 10.0, 7.0, 14.0, "about 7–12"),
)

PRESETS_BY_NAME = {preset.name: preset for preset in PRESETS}
