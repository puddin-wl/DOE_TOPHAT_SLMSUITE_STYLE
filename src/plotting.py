from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from .config import DOEConfig
from .grids import Grid
from .metrics import roi_normalized_intensity
from .targets import TargetResult


def _crop_indices(coords: np.ndarray, half_width: float) -> np.ndarray:
    return np.flatnonzero(np.abs(coords) <= half_width)


def _save_image(
    path: Path,
    image: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    title: str,
    cmap: str = "viridis",
    vmin: float | None = None,
    vmax: float | None = None,
) -> None:
    plt.figure(figsize=(6.2, 5.4), dpi=160)
    extent = [float(x[0]), float(x[-1]), float(y[0]), float(y[-1])]
    im = plt.imshow(
        image,
        extent=extent,
        origin="lower",
        cmap=cmap,
        aspect="equal",
        interpolation="nearest",
        vmin=vmin,
        vmax=vmax,
    )
    plt.xlabel("x (um)")
    plt.ylabel("y (um)")
    plt.title(title)
    plt.colorbar(im, fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def _focus_crop(config: DOEConfig, grid: Grid, data: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ix = _crop_indices(grid.x_um_focus, config.plot_crop_um)
    iy = _crop_indices(grid.y_um_focus, config.plot_crop_um)
    return data[np.ix_(iy, ix)], grid.x_um_focus[ix], grid.y_um_focus[iy]


def save_all_plots(
    out_dir: Path,
    config: DOEConfig,
    grid: Grid,
    target: TargetResult,
    phase: np.ndarray,
    focal_intensity: np.ndarray,
    aperture: np.ndarray,
) -> None:
    target_crop, x_crop, y_crop = _focus_crop(config, grid, target.amplitude)
    target_plot = np.ma.masked_invalid(target_crop)
    _save_image(out_dir / "target.png", target_plot, x_crop, y_crop, "target amplitude")

    mask_image = np.zeros_like(target.amplitude, dtype=np.float64)
    mask_image[target.zero_mask] = 0.0
    mask_image[target.noise_mask] = 1.0
    mask_image[target.transition_mask] = 2.0
    mask_image[target.core_mask] = 3.0
    mask_image[target.roi_mask] = np.maximum(mask_image[target.roi_mask], 4.0)
    mask_crop, _, _ = _focus_crop(config, grid, mask_image)
    _save_image(out_dir / "masks.png", mask_crop, x_crop, y_crop, "masks: zero, noise, transition, core, ROI")

    near_half = max(config.aperture_diameter_mm * 0.55, 1.0)
    ix = _crop_indices(grid.x_mm, near_half)
    iy = _crop_indices(grid.y_mm, near_half)
    phase_masked = np.where(aperture, phase, np.nan)
    phase_crop = phase_masked[np.ix_(iy, ix)]
    _save_image(
        out_dir / "phase.png",
        np.ma.masked_invalid(phase_crop),
        grid.x_mm[ix] * 1000.0,
        grid.y_mm[iy] * 1000.0,
        "DOE phase inside 15 mm aperture",
        cmap="twilight",
        vmin=0.0,
        vmax=2.0 * np.pi,
    )

    intensity_crop, _, _ = _focus_crop(config, grid, focal_intensity)
    _save_image(out_dir / "focal_intensity.png", intensity_crop, x_crop, y_crop, "focal intensity")
    log_crop = np.log10(intensity_crop / (np.nanmax(intensity_crop) + 1e-30) + 1e-8)
    _save_image(out_dir / "focal_intensity_log.png", log_crop, x_crop, y_crop, "log focal intensity")

    roi_norm = roi_normalized_intensity(target, focal_intensity)
    ix_roi = _crop_indices(grid.x_um_focus, config.target_width_um / 2.0)
    iy_roi = _crop_indices(grid.y_um_focus, config.target_height_um / 2.0)
    roi_crop = roi_norm[np.ix_(iy_roi, ix_roi)]
    _save_image(
        out_dir / "roi_intensity.png",
        np.ma.masked_invalid(roi_crop),
        grid.x_um_focus[ix_roi],
        grid.y_um_focus[iy_roi],
        "ROI intensity / ROI mean",
    )

    _save_profiles(out_dir / "center_profiles.png", config, grid, focal_intensity)


def _save_profiles(path: Path, config: DOEConfig, grid: Grid, intensity: np.ndarray) -> None:
    cx = grid.n // 2
    cy = grid.n // 2
    x_roi = np.abs(grid.x_um_focus) <= config.target_width_um / 2.0
    y_roi = np.abs(grid.y_um_focus) <= config.target_height_um / 2.0
    x_vals = intensity[cy, x_roi]
    y_vals = intensity[y_roi, cx]
    x_mean = float(np.mean(x_vals)) if x_vals.size else 0.0
    y_mean = float(np.mean(y_vals)) if y_vals.size else 0.0
    x_norm = x_vals / x_mean if x_mean > 0 else x_vals
    y_norm = y_vals / y_mean if y_mean > 0 else y_vals

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), dpi=160)
    axes[0].plot(grid.x_um_focus[x_roi], x_norm, lw=1.5)
    axes[0].axhline(1.0, color="k", lw=0.8, alpha=0.5)
    axes[0].set_xlabel("x (um)")
    axes[0].set_ylabel("I / mean")
    axes[0].set_title("x center profile in 330 um ROI")
    axes[0].grid(alpha=0.25)

    axes[1].plot(grid.y_um_focus[y_roi], y_norm, lw=1.5)
    axes[1].axhline(1.0, color="k", lw=0.8, alpha=0.5)
    axes[1].set_xlabel("y (um)")
    axes[1].set_ylabel("I / mean")
    axes[1].set_title("y center profile in 120 um ROI")
    axes[1].grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(path)
    plt.close(fig)
