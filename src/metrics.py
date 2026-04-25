from __future__ import annotations

import numpy as np

from .config import DOEConfig
from .grids import Grid
from .targets import TargetResult


def _center_line_width_50(coord_um: np.ndarray, values: np.ndarray) -> float:
    if values.size == 0 or not np.any(values > 0):
        return 0.0
    threshold = 0.5 * float(np.max(values))
    center = values.size // 2
    above = values >= threshold
    if not above[center]:
        candidates = np.flatnonzero(above)
        if candidates.size == 0:
            return 0.0
        center = int(candidates[np.argmin(np.abs(candidates - center))])

    left = center
    while left > 0 and above[left - 1]:
        left -= 1
    right = center
    while right < values.size - 1 and above[right + 1]:
        right += 1
    return float(coord_um[right] - coord_um[left])


def _normal_profile_stats(values: np.ndarray) -> tuple[np.ndarray, float, float]:
    mean = float(np.mean(values)) if values.size else 0.0
    if mean <= 0:
        norm = np.ones_like(values)
    else:
        norm = values / mean
    return norm, float(np.ptp(norm)), float(np.std(norm))


def compute_metrics(config: DOEConfig, grid: Grid, target: TargetResult, intensity: np.ndarray) -> dict:
    roi_values = intensity[target.roi_mask]
    roi_mean = float(np.mean(roi_values)) if roi_values.size else 0.0
    roi_norm = roi_values / roi_mean if roi_mean > 0 else np.ones_like(roi_values)
    rms = float(np.sqrt(np.mean((roi_norm - 1.0) ** 2))) if roi_values.size else 0.0
    efficiency = float(np.sum(roi_values) / np.sum(intensity)) if np.sum(intensity) > 0 else 0.0

    cy = grid.n // 2
    cx = grid.n // 2
    x_roi = np.abs(grid.x_um_focus) <= config.target_width_um / 2.0
    y_roi = np.abs(grid.y_um_focus) <= config.target_height_um / 2.0
    x_profile = intensity[cy, x_roi]
    y_profile = intensity[y_roi, cx]
    x_norm, x_p2p, x_std = _normal_profile_stats(x_profile)
    y_norm, y_p2p, y_std = _normal_profile_stats(y_profile)

    return {
        "rms_in_roi": rms,
        "efficiency_in_roi": efficiency,
        "size_50_x": _center_line_width_50(grid.x_um_focus, intensity[cy, :]),
        "size_50_y": _center_line_width_50(grid.y_um_focus, intensity[:, cx]),
        "center_profile_p2p_x": x_p2p,
        "center_profile_p2p_y": y_p2p,
        "center_profile_std_x": x_std,
        "center_profile_std_y": y_std,
        "center_profile_flatness_score": float(x_std + y_std),
        "roi_mean_intensity": roi_mean,
        "roi_pixel_count": int(np.count_nonzero(target.roi_mask)),
        "x_profile_points": int(x_norm.size),
        "y_profile_points": int(y_norm.size),
    }


def roi_normalized_intensity(target: TargetResult, intensity: np.ndarray) -> np.ndarray:
    values = intensity[target.roi_mask]
    mean = float(np.mean(values)) if values.size else 0.0
    out = np.full_like(intensity, np.nan, dtype=np.float64)
    out[target.roi_mask] = values / mean if mean > 0 else values
    return out
