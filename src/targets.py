from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import DOEConfig
from .grids import Grid


@dataclass
class TargetResult:
    amplitude: np.ndarray
    roi_mask: np.ndarray
    core_mask: np.ndarray
    transition_mask: np.ndarray
    noise_mask: np.ndarray
    zero_mask: np.ndarray
    signal_mask: np.ndarray
    finite_mask: np.ndarray


def _focus_mesh_um(grid: Grid) -> tuple[np.ndarray, np.ndarray]:
    X, Y = np.meshgrid(grid.x_um_focus, grid.y_um_focus)
    return X, Y


def _eval_roi_mask(config: DOEConfig, X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    width = getattr(config, "target_eval_width_um", config.target_width_um)
    height = getattr(config, "target_eval_height_um", config.target_height_um)
    return (np.abs(X) <= width / 2.0) & (np.abs(Y) <= height / 2.0)


def make_hard_rectangle(config: DOEConfig, grid: Grid) -> TargetResult:
    X, Y = _focus_mesh_um(grid)
    roi = _eval_roi_mask(config, X, Y)
    amplitude = np.zeros((grid.n, grid.n), dtype=np.float64)
    amplitude[roi] = 1.0
    finite = np.ones_like(roi, dtype=bool)
    zero = ~roi
    return TargetResult(
        amplitude=amplitude,
        roi_mask=roi,
        core_mask=roi.copy(),
        transition_mask=np.zeros_like(roi, dtype=bool),
        noise_mask=np.zeros_like(roi, dtype=bool),
        zero_mask=zero,
        signal_mask=roi.copy(),
        finite_mask=finite,
    )


def _raised_cosine_envelope(coord_um: np.ndarray, core_width_um: float, edge_width_um: float) -> np.ndarray:
    half_core = core_width_um / 2.0
    half_support = half_core + edge_width_um
    abs_coord = np.abs(coord_um)

    envelope = np.full_like(coord_um, np.nan, dtype=np.float64)
    core = abs_coord <= half_core
    edge = (abs_coord > half_core) & (abs_coord <= half_support)
    envelope[core] = 1.0

    if edge_width_um > 0:
        t = (abs_coord[edge] - half_core) / edge_width_um
        envelope[edge] = 0.5 * (1.0 + np.cos(np.pi * t))
    else:
        envelope[edge] = 0.0
    return envelope


def make_soft_rectangle(config: DOEConfig, grid: Grid) -> TargetResult:
    X, Y = _focus_mesh_um(grid)
    ex = _raised_cosine_envelope(X, config.core_width_um, config.edge_width_x_um)
    ey = _raised_cosine_envelope(Y, config.core_height_um, config.edge_width_y_um)

    signal = np.isfinite(ex) & np.isfinite(ey)
    amplitude = np.zeros((grid.n, grid.n), dtype=np.float64)
    amplitude[signal] = ex[signal] * ey[signal]

    roi = _eval_roi_mask(config, X, Y)
    core = (np.abs(X) <= config.core_width_um / 2.0) & (
        np.abs(Y) <= config.core_height_um / 2.0
    )
    transition = signal & ~core

    signal_half_x = config.core_width_um / 2.0 + config.edge_width_x_um
    signal_half_y = config.core_height_um / 2.0 + config.edge_width_y_um
    free_half_x = signal_half_x + config.free_region_width_x_um
    free_half_y = signal_half_y + config.free_region_width_y_um
    free_box = (np.abs(X) <= free_half_x) & (np.abs(Y) <= free_half_y)
    noise = free_box & ~signal
    zero = ~free_box
    amplitude[noise] = np.nan
    finite = ~noise

    return TargetResult(
        amplitude=amplitude,
        roi_mask=roi,
        core_mask=core,
        transition_mask=transition,
        noise_mask=noise,
        zero_mask=zero,
        signal_mask=signal,
        finite_mask=finite,
    )


def rounded_rectangle_sdf(
    X: np.ndarray,
    Y: np.ndarray,
    width_um: float,
    height_um: float,
    corner_radius_um: float,
) -> np.ndarray:
    hx = width_um / 2.0
    hy = height_um / 2.0
    r = min(corner_radius_um, hx, hy)
    qx = np.abs(X) - (hx - r)
    qy = np.abs(Y) - (hy - r)
    outside_dist = np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2)
    inside_dist = np.minimum(np.maximum(qx, qy), 0.0)
    return outside_dist + inside_dist - r


def make_rounded_rtad_target(config: DOEConfig, grid: Grid) -> TargetResult:
    X, Y = _focus_mesh_um(grid)
    d = rounded_rectangle_sdf(
        X,
        Y,
        config.core_width_um,
        config.core_height_um,
        config.corner_radius_um,
    )

    amplitude = np.zeros((grid.n, grid.n), dtype=np.float64)
    core = d <= 0.0
    shoulder = (d > 0.0) & (d <= config.shoulder_width_um)
    fall = (d > config.shoulder_width_um) & (
        d <= config.shoulder_width_um + config.fall_width_um
    )

    amplitude[core] = 1.0
    amplitude[shoulder] = config.shoulder_level
    if config.fall_width_um > 0:
        t = (d[fall] - config.shoulder_width_um) / config.fall_width_um
        t = np.clip(t, 0.0, 1.0)
        amplitude[fall] = config.shoulder_level * 0.5 * (1.0 + np.cos(np.pi * t))

    signal = core | shoulder | fall
    noise_start = config.shoulder_width_um + config.fall_width_um
    noise_end = noise_start + config.noise_band_um
    noise = (d > noise_start) & (d <= noise_end)
    if config.rounded_rtad_outer_zero_guard:
        zero = d > noise_end
    else:
        noise = d > noise_start
        zero = np.zeros_like(noise, dtype=bool)
    amplitude[noise] = np.nan
    finite = ~noise

    return TargetResult(
        amplitude=amplitude,
        roi_mask=_eval_roi_mask(config, X, Y),
        core_mask=core,
        transition_mask=shoulder | fall,
        noise_mask=noise,
        zero_mask=zero,
        signal_mask=signal,
        finite_mask=finite,
    )


def make_target(config: DOEConfig, grid: Grid) -> TargetResult:
    target = config.target.lower()
    if target == "hard":
        return make_hard_rectangle(config, grid)
    if target == "soft":
        return make_soft_rectangle(config, grid)
    if target in {"rounded_rtad", "rounded-rtad", "rtad"}:
        return make_rounded_rtad_target(config, grid)
    raise ValueError(f"Unknown target type: {config.target!r}")
