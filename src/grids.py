from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np

from .config import DOEConfig, resolve_project_path


@dataclass
class Grid:
    n: int
    x_mm: np.ndarray
    y_mm: np.ndarray
    x_um_focus: np.ndarray
    y_um_focus: np.ndarray
    X_mm: np.ndarray
    Y_mm: np.ndarray
    FX_cyc_per_mm: np.ndarray
    FY_cyc_per_mm: np.ndarray
    dx_mm: float
    focus_sampling_um: float
    compute_window_mm: float


def make_grid(config: DOEConfig) -> Grid:
    n = config.n
    dx_mm = config.doe_sampling_mm
    coords_mm = (np.arange(n) - n // 2) * dx_mm
    focus_coords_um = (np.arange(n) - n // 2) * config.focus_sampling_um
    X_mm, Y_mm = np.meshgrid(coords_mm, coords_mm)

    freq = np.fft.fftshift(np.fft.fftfreq(n, d=dx_mm))
    FX, FY = np.meshgrid(freq, freq)
    return Grid(
        n=n,
        x_mm=coords_mm,
        y_mm=coords_mm,
        x_um_focus=focus_coords_um,
        y_um_focus=focus_coords_um,
        X_mm=X_mm,
        Y_mm=Y_mm,
        FX_cyc_per_mm=FX,
        FY_cyc_per_mm=FY,
        dx_mm=dx_mm,
        focus_sampling_um=config.focus_sampling_um,
        compute_window_mm=config.compute_window_mm,
    )


def aperture_mask(grid: Grid, diameter_mm: float) -> np.ndarray:
    radius_mm = diameter_mm / 2.0
    return (grid.X_mm**2 + grid.Y_mm**2) <= radius_mm**2


def gaussian_aperture_amplitude(config: DOEConfig, grid: Grid) -> tuple[np.ndarray, np.ndarray]:
    radius_1e2_mm = config.gaussian_1e2_diameter_mm / 2.0
    gaussian = np.exp(-(grid.X_mm**2 + grid.Y_mm**2) / radius_1e2_mm**2)
    mask = aperture_mask(grid, config.aperture_diameter_mm)
    amplitude = gaussian * mask.astype(np.float64)
    if config.normalize_input_power:
        norm = np.sqrt(np.sum(amplitude**2))
        if norm > 0:
            amplitude = amplitude / norm
    return amplitude, mask


def lens_pupil_mask(config: DOEConfig, grid: Grid) -> np.ndarray:
    return aperture_mask(grid, config.lens_pupil_diameter_mm)


def load_bgdata_summary(path: str | Path, root: Path | None = None) -> dict:
    root = root or Path.cwd()
    resolved = resolve_project_path(path, root)
    if not resolved.exists():
        matches = list(root.rglob(Path(path).name))
        if matches:
            resolved = matches[0]
    summary: dict = {
        "path": str(resolved),
        "exists": resolved.exists(),
        "used_for_solver_amplitude": False,
    }
    if not resolved.exists():
        return summary

    try:
        with h5py.File(resolved, "r") as f:
            width = int(f["BG_DATA/1/RAWFRAME/WIDTH"][0])
            height = int(f["BG_DATA/1/RAWFRAME/HEIGHT"][0])
            pixel_x_um = float(f["BG_DATA/1/RAWFRAME/PIXELSCALEXUM"][0])
            pixel_y_um = float(f["BG_DATA/1/RAWFRAME/PIXELSCALEYUM"][0])
            data = f["BG_DATA/1/DATA"][()].reshape(height, width).astype(np.float64)
            bg = float(np.percentile(data, 1.0))
            intensity = np.clip(data - bg, 0.0, None)
            total = float(np.sum(intensity))

            if total > 0:
                yy = (np.arange(height) - (height - 1) / 2.0) * pixel_y_um
                xx = (np.arange(width) - (width - 1) / 2.0) * pixel_x_um
                X, Y = np.meshgrid(xx, yy)
                cx = float(np.sum(intensity * X) / total)
                cy = float(np.sum(intensity * Y) / total)
                sx = float(np.sqrt(np.sum(intensity * (X - cx) ** 2) / total))
                sy = float(np.sqrt(np.sum(intensity * (Y - cy) ** 2) / total))
            else:
                cx = cy = sx = sy = float("nan")

            summary.update(
                {
                    "shape": [height, width],
                    "pixel_scale_um": [pixel_y_um, pixel_x_um],
                    "fov_um": [height * pixel_y_um, width * pixel_x_um],
                    "background_percentile_1": bg,
                    "centroid_um": [cy, cx],
                    "d4sigma_um_estimate": [4.0 * sy, 4.0 * sx],
                    "note": "Shape-only diagnostic. Solver still uses expanded 5 mm 1/e^2 Gaussian.",
                }
            )
    except Exception as exc:
        summary["error"] = f"{type(exc).__name__}: {exc}"
    return summary
