from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class DOEConfig:
    wavelength_nm: float = 532.0
    focal_length_mm: float = 429.0
    asm_distance_mm: float = 200.0

    aperture_diameter_mm: float = 15.0
    gaussian_1e2_diameter_mm: float = 5.0
    lens_pupil_diameter_mm: float = 15.0
    beam_shape_file: str = "参数/3044.bgData"

    n: int = 2048
    focus_sampling_um: float = 2.5
    iterations: int = 50
    seed: int = 7

    target_eval_width_um: float = 330.0
    target_eval_height_um: float = 120.0
    target_width_um: float = 330.0
    target_height_um: float = 120.0
    core_width_um: float = 310.0
    core_height_um: float = 95.0
    edge_width_x_um: float = 20.0
    edge_width_y_um: float = 50.0
    free_region_width_x_um: float = 120.0
    free_region_width_y_um: float = 120.0
    corner_radius_um: float = 25.0
    shoulder_width_um: float = 20.0
    shoulder_level: float = 0.75
    fall_width_um: float = 50.0
    noise_band_um: float = 80.0
    rounded_rtad_outer_zero_guard: bool = True

    method: str = "mraf"
    target: str = "rounded_rtad"
    phase_init: str = "astigmatic_quadratic"
    mraf_factor: float = 1.0
    target_power_fraction: float | None = None
    normalize_input_power: bool = True
    feedback_exponent: float = 2.0

    quadratic_strength: float = 7.0
    astigmatic_strength_x: float = 8.0
    astigmatic_strength_y: float = 3.5
    conical_strength: float = 11.0

    plot_crop_um: float = 600.0

    @property
    def wavelength_mm(self) -> float:
        return self.wavelength_nm * 1e-6

    @property
    def focus_sampling_mm(self) -> float:
        return self.focus_sampling_um * 1e-3

    @property
    def compute_window_mm(self) -> float:
        return self.wavelength_mm * self.focal_length_mm / self.focus_sampling_mm

    @property
    def doe_sampling_mm(self) -> float:
        return self.compute_window_mm / self.n

    def to_dict(self) -> dict:
        data = asdict(self)
        data["wavelength_mm"] = self.wavelength_mm
        data["focus_sampling_mm"] = self.focus_sampling_mm
        data["compute_window_mm"] = self.compute_window_mm
        data["doe_sampling_mm"] = self.doe_sampling_mm
        return data


def update_config(config: DOEConfig, **kwargs) -> DOEConfig:
    data = config.to_dict()
    for key in (
        "wavelength_mm",
        "focus_sampling_mm",
        "compute_window_mm",
        "doe_sampling_mm",
    ):
        data.pop(key, None)
    data.update({k: v for k, v in kwargs.items() if v is not None})
    return DOEConfig(**data)


def resolve_project_path(path: str | Path, root: Path | None = None) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return (root or Path.cwd()) / p
