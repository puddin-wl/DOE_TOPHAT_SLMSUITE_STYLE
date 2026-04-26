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
    beam_shape_file: str = "\u53c2\u6570/3044.bgData"

    n: int = 2048
    focus_sampling_um: float = 2.5
    iterations: int = 50
    seed: int = 7

    target_width_um: float = 330.0
    target_height_um: float = 120.0
    corner_radius_um: float = 0.0
    transition_width_13_90_um: float = 40.0
    transition_width_13_90_x_um: float | None = None
    transition_width_13_90_y_um: float | None = None
    free_region_threshold_intensity: float = 0.135
    descending_edge_mode: str = "none"
    descending_edge_width_um: float = 0.0
    descending_edge_end_intensity: float = 0.03
    controlled_tail_end_intensity: float = 0.03
    controlled_tail_width_um: float | None = None
    controlled_tail_width_x_um: float | None = None
    controlled_tail_width_y_um: float | None = None
    tail_to_free: bool = False
    tail_end_intensity: float = 0.03
    tail_width_um: float = 12.0
    metric_core_level: float = 0.95
    metric_uniform_level: float = 0.90
    side_lobe_search_width_um: float = 250.0
    side_lobe_smoothing_sigma_um: float = 5.0
    side_lobe_crossing_margin_um: float = 5.0
    side_lobe_prominence_threshold: float = 0.02
    core_width_um: float = 320.0
    core_height_um: float = 100.0
    edge_width_x_um: float = 20.0
    edge_width_y_um: float = 50.0
    free_region_width_x_um: float = 120.0
    free_region_width_y_um: float = 120.0

    method: str = "wgs"
    target: str = "industrial_logistic"
    phase_init: str = "quadratic"
    mraf_factor: float = 0.5
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
