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


def make_hard_rectangle(config: DOEConfig, grid: Grid) -> TargetResult:
    X, Y = _focus_mesh_um(grid)
    roi = (np.abs(X) <= config.target_width_um / 2.0) & (
        np.abs(Y) <= config.target_height_um / 2.0
    )
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

    roi = (np.abs(X) <= config.target_width_um / 2.0) & (
        np.abs(Y) <= config.target_height_um / 2.0
    )
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


def make_industrial_logistic_target(config: DOEConfig, grid: Grid) -> TargetResult:
    X, Y = _focus_mesh_um(grid)
    dx = np.abs(X) - config.target_width_um / 2.0
    dy = np.abs(Y) - config.target_height_um / 2.0
    d = np.maximum(dx, dy)

    if config.transition_width_13_90_um <= 0:
        raise ValueError("transition_width_13_90_um must be positive")
    s = config.transition_width_13_90_um / 4.055
    intensity = 1.0 / (1.0 + np.exp(np.clip(d / s, -80.0, 80.0)))

    threshold = float(config.free_region_threshold_intensity)
    finite = intensity >= threshold
    noise = ~finite

    amplitude = np.full((grid.n, grid.n), np.nan, dtype=np.float64)
    amplitude[finite] = np.sqrt(intensity[finite])

    roi = intensity >= 0.5
    core = intensity >= config.metric_uniform_level
    transition = finite & ~core
    zero = np.zeros_like(finite, dtype=bool)

    return TargetResult(
        amplitude=amplitude,
        roi_mask=roi,
        core_mask=core,
        transition_mask=transition,
        noise_mask=noise,
        zero_mask=zero,
        signal_mask=finite,
        finite_mask=finite,
    )


def make_target(config: DOEConfig, grid: Grid) -> TargetResult:
    target = config.target.lower()
    if target == "hard":
        return make_hard_rectangle(config, grid)
    if target == "soft":
        return make_soft_rectangle(config, grid)
    if target in {"industrial_logistic", "industrial", "logistic"}:
        return make_industrial_logistic_target(config, grid)
    raise ValueError(f"Unknown target type: {config.target!r}")
