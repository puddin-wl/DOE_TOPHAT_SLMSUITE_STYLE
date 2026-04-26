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
    intensity: np.ndarray | None = None


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
    intensity = amplitude**2
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
        intensity=intensity,
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
    intensity = amplitude**2

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
        intensity=intensity,
    )


def make_industrial_logistic_target(config: DOEConfig, grid: Grid) -> TargetResult:
    X, Y = _focus_mesh_um(grid)
    dx = np.abs(X) - config.target_width_um / 2.0
    dy = np.abs(Y) - config.target_height_um / 2.0

    transition_x = (
        config.transition_width_13_90_x_um
        if config.transition_width_13_90_x_um is not None
        else config.transition_width_13_90_um
    )
    transition_y = (
        config.transition_width_13_90_y_um
        if config.transition_width_13_90_y_um is not None
        else config.transition_width_13_90_um
    )
    if transition_x <= 0 or transition_y <= 0:
        raise ValueError("transition widths must be positive")

    sx = transition_x / 4.055
    sy = transition_y / 4.055
    ix = 1.0 / (1.0 + np.exp(np.clip(dx / sx, -80.0, 80.0)))
    iy = 1.0 / (1.0 + np.exp(np.clip(dy / sy, -80.0, 80.0)))
    base_intensity = np.minimum(ix, iy)

    threshold = float(config.free_region_threshold_intensity)
    if not (0.0 < threshold < 1.0):
        raise ValueError("free_region_threshold_intensity must be between 0 and 1")

    finite = base_intensity >= threshold
    constrained_intensity = np.array(base_intensity, copy=True)

    descending_edge_mode = config.descending_edge_mode.lower()
    use_legacy_tail = bool(config.tail_to_free)
    use_descending_edge = descending_edge_mode != "none" or use_legacy_tail
    if use_descending_edge:
        if descending_edge_mode not in {"none", "raised_cosine"}:
            raise ValueError(f"Unknown descending_edge_mode: {config.descending_edge_mode!r}")
        tail_end_intensity = (
            config.tail_end_intensity if use_legacy_tail else config.descending_edge_end_intensity
        )
        tail_width_um = config.tail_width_um if use_legacy_tail else config.descending_edge_width_um
        if not (0.0 < tail_end_intensity < threshold):
            raise ValueError(
                "descending edge end intensity must be between 0 and free_region_threshold_intensity"
            )
        if tail_width_um <= 0:
            raise ValueError("descending edge width must be positive when enabled")

        d13_x = sx * np.log(1.0 / threshold - 1.0)
        d13_y = sy * np.log(1.0 / threshold - 1.0)
        distance_past_13 = np.maximum(dx - d13_x, dy - d13_y)
        tail = (distance_past_13 > 0.0) & (distance_past_13 <= tail_width_um)
        u = np.clip(distance_past_13[tail] / tail_width_um, 0.0, 1.0)
        constrained_intensity[tail] = tail_end_intensity + (
            threshold - tail_end_intensity
        ) * 0.5 * (1.0 + np.cos(np.pi * u))
        finite = finite | tail

    noise = ~finite

    amplitude = np.full((grid.n, grid.n), np.nan, dtype=np.float64)
    amplitude[finite] = np.sqrt(constrained_intensity[finite])

    roi = base_intensity >= 0.5
    core = base_intensity >= config.metric_uniform_level
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
        intensity=constrained_intensity,
    )


def _transition_widths(config: DOEConfig) -> tuple[float, float]:
    transition_x = (
        config.transition_width_13_90_x_um
        if config.transition_width_13_90_x_um is not None
        else config.transition_width_13_90_um
    )
    transition_y = (
        config.transition_width_13_90_y_um
        if config.transition_width_13_90_y_um is not None
        else config.transition_width_13_90_um
    )
    if transition_x <= 0 or transition_y <= 0:
        raise ValueError("transition widths must be positive")
    return float(transition_x), float(transition_y)


def _rounded_rectangle_sdf_um(
    X: np.ndarray,
    Y: np.ndarray,
    width_um: float,
    height_um: float,
    radius_um: float,
) -> np.ndarray:
    radius_um = max(0.0, min(float(radius_um), width_um / 2.0, height_um / 2.0))
    half_inner_x = width_um / 2.0 - radius_um
    half_inner_y = height_um / 2.0 - radius_um
    qx = np.abs(X) - half_inner_x
    qy = np.abs(Y) - half_inner_y
    outside = np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2)
    inside = np.minimum(np.maximum(qx, qy), 0.0)
    return outside + inside - radius_um


def make_industrial_rounded_logistic_target(config: DOEConfig, grid: Grid) -> TargetResult:
    X, Y = _focus_mesh_um(grid)
    transition_x, transition_y = _transition_widths(config)
    transition_ref = float(min(transition_x, transition_y))
    corner_radius_um = config.corner_radius_um if config.corner_radius_um > 0 else transition_ref
    corner_radius_um = min(corner_radius_um, config.target_width_um / 2.0, config.target_height_um / 2.0)
    tail_end = float(config.controlled_tail_end_intensity)
    threshold = float(config.free_region_threshold_intensity)
    tail_width_um = (
        float(config.controlled_tail_width_um)
        if config.controlled_tail_width_um is not None
        else 2.0 * transition_ref
    )

    if not (0.0 < threshold < 1.0):
        raise ValueError("free_region_threshold_intensity must be between 0 and 1")
    if not (0.0 < tail_end < threshold):
        raise ValueError("controlled_tail_end_intensity must be between 0 and free_region_threshold_intensity")
    if tail_width_um <= 0:
        raise ValueError("controlled_tail_width_um must be positive")

    sdf_um = _rounded_rectangle_sdf_um(
        X,
        Y,
        config.target_width_um,
        config.target_height_um,
        corner_radius_um,
    )
    grad_y, grad_x = np.gradient(sdf_um, grid.focus_sampling_um, grid.focus_sampling_um)
    grad_norm = np.sqrt(grad_x**2 + grad_y**2)
    normal_x = np.divide(grad_x, grad_norm, out=np.zeros_like(grad_x), where=grad_norm > 0)
    normal_y = np.divide(grad_y, grad_norm, out=np.zeros_like(grad_y), where=grad_norm > 0)
    transition_local = np.maximum(
        np.abs(normal_x) * transition_x + np.abs(normal_y) * transition_y,
        1e-9,
    )
    s = transition_local / 4.055
    base_intensity = 1.0 / (1.0 + np.exp(np.clip(sdf_um / s, -80.0, 80.0)))
    constrained_intensity = np.array(base_intensity, copy=True)

    d13 = s * np.log(1.0 / threshold - 1.0)
    finite = base_intensity >= threshold
    distance_past_13 = sdf_um - d13
    tail = (distance_past_13 > 0.0) & (distance_past_13 <= tail_width_um)
    u = np.clip(distance_past_13[tail] / tail_width_um, 0.0, 1.0)
    constrained_intensity[tail] = tail_end + (threshold - tail_end) * 0.5 * (1.0 + np.cos(np.pi * u))
    finite = finite | tail

    noise = ~finite
    amplitude = np.full((grid.n, grid.n), np.nan, dtype=np.float64)
    amplitude[finite] = np.sqrt(constrained_intensity[finite])

    roi = base_intensity >= 0.5
    core = base_intensity >= config.metric_uniform_level
    transition = finite & ~core & ~tail
    zero = np.zeros_like(finite, dtype=bool)

    return TargetResult(
        amplitude=amplitude,
        roi_mask=roi,
        core_mask=core,
        transition_mask=transition | tail,
        noise_mask=noise,
        zero_mask=zero,
        signal_mask=finite,
        finite_mask=finite,
        intensity=constrained_intensity,
    )


def make_target(config: DOEConfig, grid: Grid) -> TargetResult:
    target = config.target.lower()
    if target == "hard":
        return make_hard_rectangle(config, grid)
    if target == "soft":
        return make_soft_rectangle(config, grid)
    if target in {"industrial_logistic", "industrial", "logistic"}:
        return make_industrial_logistic_target(config, grid)
    if target in {"industrial_rounded_logistic", "rounded_logistic", "industrial_rounded"}:
        return make_industrial_rounded_logistic_target(config, grid)
    raise ValueError(f"Unknown target type: {config.target!r}")
