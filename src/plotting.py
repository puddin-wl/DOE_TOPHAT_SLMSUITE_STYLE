from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from .config import DOEConfig
from .grids import Grid
from .metrics import _center_connected_edges, _transition_width, roi_normalized_intensity, target_intensity
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
    target_crop, x_crop, y_crop = _focus_crop(config, grid, target_intensity(target))
    target_plot = np.ma.masked_invalid(target_crop)
    _save_image(out_dir / "target.png", target_plot, x_crop, y_crop, "target intensity")

    mask_image = np.zeros_like(target.amplitude, dtype=np.float64)
    mask_image[target.zero_mask] = 0.0
    mask_image[target.noise_mask] = 1.0
    mask_image[target.transition_mask] = 2.0
    mask_image[target.roi_mask] = np.maximum(mask_image[target.roi_mask], 3.0)
    mask_image[target.core_mask] = 4.0
    mask_crop, _, _ = _focus_crop(config, grid, mask_image)
    _save_image(out_dir / "masks.png", mask_crop, x_crop, y_crop, "masks: zero, noise, transition, 50%, core")

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

    _save_profiles(out_dir / "center_profiles.png", config, grid, target, focal_intensity)
    _save_profiles(
        out_dir / "center_profiles_raw_norm.png",
        config,
        grid,
        target,
        focal_intensity,
        annotate_crossings=True,
    )


def _save_profiles(
    path: Path,
    config: DOEConfig,
    grid: Grid,
    target: TargetResult,
    intensity: np.ndarray,
    annotate_crossings: bool = False,
) -> None:
    cx = grid.n // 2
    cy = grid.n // 2
    x_view = np.abs(grid.x_um_focus) <= config.plot_crop_um
    y_view = np.abs(grid.y_um_focus) <= config.plot_crop_um
    reference_values = intensity[target.core_mask]
    reference = float(np.mean(reference_values)) if reference_values.size else 0.0
    if reference <= 0:
        reference_values = intensity[target.roi_mask]
        reference = float(np.mean(reference_values)) if reference_values.size else 0.0
    if reference <= 0:
        reference = float(np.nanmax(intensity))

    x_norm = intensity[cy, x_view] / reference if reference > 0 else intensity[cy, x_view]
    y_norm = intensity[y_view, cx] / reference if reference > 0 else intensity[y_view, cx]
    target_i = target_intensity(target)
    x_target = target_i[cy, x_view]
    y_target = target_i[y_view, cx]

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), dpi=160)
    axes[0].plot(grid.x_um_focus[x_view], x_norm, lw=1.5, label="actual")
    axes[0].plot(grid.x_um_focus[x_view], x_target, lw=1.0, alpha=0.75, label="target I")
    _draw_threshold_lines(axes[0], config)
    axes[0].axvline(-config.target_width_um / 2.0, color="tab:red", lw=0.8, alpha=0.45)
    axes[0].axvline(config.target_width_um / 2.0, color="tab:red", lw=0.8, alpha=0.45)
    if annotate_crossings:
        _annotate_profile_crossings(
            axes[0],
            grid.x_um_focus[x_view],
            x_norm,
            config,
            axis_label="x",
        )
    axes[0].set_xlabel("x (um)")
    axes[0].set_ylabel("I / core mean")
    axes[0].set_title("x center profile")
    axes[0].set_ylim(bottom=0.0)
    axes[0].grid(alpha=0.25)
    axes[0].legend(frameon=False, fontsize=8)

    axes[1].plot(grid.y_um_focus[y_view], y_norm, lw=1.5, label="actual")
    axes[1].plot(grid.y_um_focus[y_view], y_target, lw=1.0, alpha=0.75, label="target I")
    _draw_threshold_lines(axes[1], config)
    axes[1].axvline(-config.target_height_um / 2.0, color="tab:red", lw=0.8, alpha=0.45)
    axes[1].axvline(config.target_height_um / 2.0, color="tab:red", lw=0.8, alpha=0.45)
    if annotate_crossings:
        _annotate_profile_crossings(
            axes[1],
            grid.y_um_focus[y_view],
            y_norm,
            config,
            axis_label="y",
        )
    axes[1].set_xlabel("y (um)")
    axes[1].set_ylabel("I / core mean")
    axes[1].set_title("y center profile")
    axes[1].set_ylim(bottom=0.0)
    axes[1].grid(alpha=0.25)
    axes[1].legend(frameon=False, fontsize=8)
    plt.tight_layout()
    plt.savefig(path)
    plt.close(fig)


def _draw_threshold_lines(ax: plt.Axes, config: DOEConfig) -> None:
    lines = [
        (1.0, "1.0", "0.25"),
        (config.metric_uniform_level, "90%", "tab:green"),
        (0.5, "50%", "tab:red"),
        (config.free_region_threshold_intensity, "13.5%", "tab:purple"),
    ]
    for level, label, color in lines:
        ax.axhline(level, color=color, lw=0.8, alpha=0.45, label=label if level != 1.0 else None)


def _annotate_profile_crossings(
    ax: plt.Axes,
    coord_um: np.ndarray,
    profile: np.ndarray,
    config: DOEConfig,
    axis_label: str,
) -> None:
    levels = [
        (config.metric_uniform_level, "90%", "tab:green"),
        (0.5, "50%", "tab:red"),
        (config.free_region_threshold_intensity, "13.5%", "tab:purple"),
    ]
    edges_by_level: dict[float, tuple[float, float, float]] = {}
    for level, label, color in levels:
        left, right, width = _center_connected_edges(coord_um, profile, level)
        edges_by_level[level] = (left, right, width)
        if not (np.isfinite(left) and np.isfinite(right)):
            continue
        ax.scatter([left, right], [level, level], s=18, color=color, zorder=4)
        ax.axvline(left, color=color, lw=0.75, alpha=0.35, ls="--")
        ax.axvline(right, color=color, lw=0.75, alpha=0.35, ls="--")

    edge_90 = edges_by_level[config.metric_uniform_level]
    edge_13 = edges_by_level[config.free_region_threshold_intensity]
    transition = _transition_width(edge_90, edge_13)
    text = "\n".join(
        [
            f"{axis_label} size90={edge_90[2]:.1f} um",
            f"{axis_label} size50={edges_by_level[0.5][2]:.1f} um",
            f"{axis_label} size13.5={edge_13[2]:.1f} um",
            f"13.5-90={transition:.1f} um",
        ]
    )
    ax.text(
        0.02,
        0.96,
        text,
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=8,
        bbox={"facecolor": "white", "alpha": 0.72, "edgecolor": "none", "pad": 3.0},
    )
