from __future__ import annotations

import numpy as np

from .config import DOEConfig
from .grids import Grid
from .targets import TargetResult


def target_intensity(target: TargetResult) -> np.ndarray:
    out = np.full_like(target.amplitude, np.nan, dtype=np.float64)
    finite = np.isfinite(target.amplitude)
    out[finite] = target.amplitude[finite] ** 2
    return out


def _crossing_between(
    coord_a: float,
    value_a: float,
    coord_b: float,
    value_b: float,
    threshold: float,
) -> float:
    denom = value_b - value_a
    if abs(denom) < 1e-30:
        return float(0.5 * (coord_a + coord_b))
    t = (threshold - value_a) / denom
    return float(coord_a + np.clip(t, 0.0, 1.0) * (coord_b - coord_a))


def _center_connected_edges(
    coord_um: np.ndarray,
    values: np.ndarray,
    threshold: float,
) -> tuple[float, float, float]:
    if values.size == 0 or not np.any(np.isfinite(values)):
        return float("nan"), float("nan"), float("nan")

    finite_values = np.nan_to_num(values, nan=-np.inf, posinf=np.inf, neginf=-np.inf)
    above = finite_values >= threshold
    if not np.any(above):
        return float("nan"), float("nan"), float("nan")

    center = int(np.argmin(np.abs(coord_um)))
    if not above[center]:
        return float("nan"), float("nan"), float("nan")

    left = center
    while left > 0 and above[left - 1]:
        left -= 1

    right = center
    while right < values.size - 1 and above[right + 1]:
        right += 1

    if left > 0:
        left_cross = _crossing_between(
            float(coord_um[left - 1]),
            float(finite_values[left - 1]),
            float(coord_um[left]),
            float(finite_values[left]),
            threshold,
        )
    else:
        left_cross = float(coord_um[left])

    if right < values.size - 1:
        right_cross = _crossing_between(
            float(coord_um[right]),
            float(finite_values[right]),
            float(coord_um[right + 1]),
            float(finite_values[right + 1]),
            threshold,
        )
    else:
        right_cross = float(coord_um[right])

    return left_cross, right_cross, float(right_cross - left_cross)


def _mean_finite(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.mean(finite)) if finite.size else 0.0


def _reference_intensity(config: DOEConfig, target: TargetResult, intensity: np.ndarray) -> tuple[float, str]:
    ti = target_intensity(target)
    masks = [
        (f"target_I_ge_{config.metric_core_level:g}", np.isfinite(ti) & (ti >= config.metric_core_level)),
        (f"target_I_ge_{config.metric_uniform_level:g}", np.isfinite(ti) & (ti >= config.metric_uniform_level)),
        ("target_I_ge_0.5", np.isfinite(ti) & (ti >= 0.5)),
        ("signal", target.signal_mask),
    ]
    for name, mask in masks:
        value = _mean_finite(intensity[mask])
        if value > 0:
            return value, name
    fallback = float(np.nanmax(intensity)) if intensity.size else 0.0
    return fallback, "global_max"


def _rms_about_one(values: np.ndarray) -> tuple[float, float, float, float]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float("nan"), float("nan"), float("nan"), float("nan")
    return (
        float(np.sqrt(np.mean((finite - 1.0) ** 2))),
        float(np.mean(finite)),
        float(np.std(finite)),
        float(np.ptp(finite)),
    )


def _transition_width(edge_90: tuple[float, float, float], edge_13: tuple[float, float, float]) -> float:
    left_90, right_90, _ = edge_90
    left_13, right_13, _ = edge_13
    widths = []
    if np.isfinite(left_90) and np.isfinite(left_13):
        widths.append(left_90 - left_13)
    if np.isfinite(right_90) and np.isfinite(right_13):
        widths.append(right_13 - right_90)
    widths = [float(w) for w in widths if np.isfinite(w) and w >= 0]
    return float(np.mean(widths)) if widths else float("nan")


def compute_metrics(config: DOEConfig, grid: Grid, target: TargetResult, intensity: np.ndarray) -> dict:
    ti = target_intensity(target)
    reference, reference_source = _reference_intensity(config, target, intensity)
    norm_intensity = intensity / reference if reference > 0 else np.zeros_like(intensity)

    mask_13 = np.isfinite(ti) & (ti >= config.free_region_threshold_intensity)
    mask_50 = np.isfinite(ti) & (ti >= 0.5)
    mask_90 = np.isfinite(ti) & (ti >= config.metric_uniform_level)
    mask_core = np.isfinite(ti) & (ti >= config.metric_core_level)

    rms_core, core_mean, core_std, core_p2p = _rms_about_one(norm_intensity[mask_core])
    rms_90, mean_90, std_90, p2p_90 = _rms_about_one(norm_intensity[mask_90])
    rms_50, mean_50, std_50, p2p_50 = _rms_about_one(norm_intensity[mask_50])

    total_power = float(np.sum(intensity))
    efficiency_13 = float(np.sum(intensity[mask_13]) / total_power) if total_power > 0 else 0.0

    cy = grid.n // 2
    cx = grid.n // 2
    x_profile = norm_intensity[cy, :]
    y_profile = norm_intensity[:, cx]

    x_edges_90 = _center_connected_edges(grid.x_um_focus, x_profile, config.metric_uniform_level)
    x_edges_50 = _center_connected_edges(grid.x_um_focus, x_profile, 0.5)
    x_edges_13 = _center_connected_edges(
        grid.x_um_focus,
        x_profile,
        config.free_region_threshold_intensity,
    )
    y_edges_90 = _center_connected_edges(grid.y_um_focus, y_profile, config.metric_uniform_level)
    y_edges_50 = _center_connected_edges(grid.y_um_focus, y_profile, 0.5)
    y_edges_13 = _center_connected_edges(
        grid.y_um_focus,
        y_profile,
        config.free_region_threshold_intensity,
    )

    x_50_roi = np.abs(grid.x_um_focus) <= config.target_width_um / 2.0
    y_50_roi = np.abs(grid.y_um_focus) <= config.target_height_um / 2.0
    _, _, x_std, x_p2p = _rms_about_one(x_profile[x_50_roi])
    _, _, y_std, y_p2p = _rms_about_one(y_profile[y_50_roi])

    size_50_x = x_edges_50[2]
    size_50_y = y_edges_50[2]
    size_13_x = x_edges_13[2]
    size_13_y = y_edges_13[2]
    transition_x = _transition_width(x_edges_90, x_edges_13)
    transition_y = _transition_width(y_edges_90, y_edges_13)

    flatness_score = float(np.nan_to_num(x_std, nan=1e9) + np.nan_to_num(y_std, nan=1e9))

    return {
        "size_50_x_um": size_50_x,
        "size_50_y_um": size_50_y,
        "size_13p5_x_um": size_13_x,
        "size_13p5_y_um": size_13_y,
        "transition_width_13_90_x_um": transition_x,
        "transition_width_13_90_y_um": transition_y,
        "efficiency_13p5": efficiency_13,
        "rms_core": rms_core,
        "rms_90": rms_90,
        "rms_50_reference": rms_50,
        "center_profile_p2p_x": x_p2p,
        "center_profile_p2p_y": y_p2p,
        "center_profile_std_x": x_std,
        "center_profile_std_y": y_std,
        "center_profile_flatness_score": flatness_score,
        "reference_intensity": reference,
        "reference_source": reference_source,
        "target_13p5_pixel_count": int(np.count_nonzero(mask_13)),
        "target_50_pixel_count": int(np.count_nonzero(mask_50)),
        "target_90_pixel_count": int(np.count_nonzero(mask_90)),
        "target_core_pixel_count": int(np.count_nonzero(mask_core)),
        "x_left_90_um": x_edges_90[0],
        "x_right_90_um": x_edges_90[1],
        "x_left_50_um": x_edges_50[0],
        "x_right_50_um": x_edges_50[1],
        "x_left_13p5_um": x_edges_13[0],
        "x_right_13p5_um": x_edges_13[1],
        "y_left_90_um": y_edges_90[0],
        "y_right_90_um": y_edges_90[1],
        "y_left_50_um": y_edges_50[0],
        "y_right_50_um": y_edges_50[1],
        "y_left_13p5_um": y_edges_13[0],
        "y_right_13p5_um": y_edges_13[1],
        "rms_90_mean": mean_90,
        "rms_90_std": std_90,
        "rms_90_p2p": p2p_90,
        "rms_50_mean": mean_50,
        "rms_50_std": std_50,
        "rms_50_p2p": p2p_50,
        "rms_core_mean": core_mean,
        "rms_core_std": core_std,
        "rms_core_p2p": core_p2p,
        "total_power": total_power,
        # Legacy aliases kept so older scripts do not silently break.
        "rms_in_roi": rms_50,
        "efficiency_in_roi": efficiency_13,
        "size_50_x": size_50_x,
        "size_50_y": size_50_y,
    }


def roi_normalized_intensity(target: TargetResult, intensity: np.ndarray) -> np.ndarray:
    values = intensity[target.core_mask]
    reference = float(np.mean(values)) if values.size and np.mean(values) > 0 else 0.0
    if reference <= 0:
        roi_values = intensity[target.roi_mask]
        reference = float(np.mean(roi_values)) if roi_values.size and np.mean(roi_values) > 0 else 0.0

    out = np.full_like(intensity, np.nan, dtype=np.float64)
    if reference > 0:
        out[target.roi_mask] = intensity[target.roi_mask] / reference
    else:
        out[target.roi_mask] = intensity[target.roi_mask]
    return out
