from __future__ import annotations

import numpy as np

from .config import DOEConfig
from .grids import Grid
from .targets import TargetResult


def target_intensity(target: TargetResult) -> np.ndarray:
    if target.intensity is not None:
        return np.array(target.intensity, copy=True)
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


def _side_lobe_for_profile(
    coord_um: np.ndarray,
    normalized_profile: np.ndarray,
    edge_13: tuple[float, float, float],
    search_width_um: float,
) -> dict:
    left_edge, right_edge, _ = edge_13
    if not (np.isfinite(left_edge) and np.isfinite(right_edge)) or search_width_um <= 0:
        return {
            "peak_rel": float("nan"),
            "distance_um": float("nan"),
            "position_um": float("nan"),
            "side": "none",
        }

    candidates: list[dict] = []
    windows = [
        ("left", (coord_um >= left_edge - search_width_um) & (coord_um < left_edge), left_edge),
        ("right", (coord_um > right_edge) & (coord_um <= right_edge + search_width_um), right_edge),
    ]
    for side, mask, edge in windows:
        valid = mask & np.isfinite(normalized_profile)
        if not np.any(valid):
            continue
        idxs = np.flatnonzero(valid)
        local = idxs[int(np.argmax(normalized_profile[idxs]))]
        position = float(coord_um[local])
        candidates.append(
            {
                "peak_rel": float(normalized_profile[local]),
                "distance_um": float(abs(position - edge)),
                "position_um": position,
                "side": side,
            }
        )

    if not candidates:
        return {
            "peak_rel": float("nan"),
            "distance_um": float("nan"),
            "position_um": float("nan"),
            "side": "none",
        }
    return max(candidates, key=lambda item: item["peak_rel"])


def _gaussian_smooth_1d(values: np.ndarray, sigma_px: float) -> np.ndarray:
    finite = np.isfinite(values)
    filled = np.where(finite, values, 0.0)
    if sigma_px <= 0:
        return filled
    radius = max(1, int(np.ceil(4.0 * sigma_px)))
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (x / sigma_px) ** 2)
    kernel /= np.sum(kernel)
    weights = np.convolve(finite.astype(np.float64), kernel, mode="same")
    smoothed = np.convolve(filled, kernel, mode="same")
    out = np.full_like(values, np.nan, dtype=np.float64)
    valid = weights > 1e-12
    out[valid] = smoothed[valid] / weights[valid]
    return out


def _profile_spacing_um(coord_um: np.ndarray) -> float:
    if coord_um.size < 2:
        return 1.0
    diffs = np.diff(coord_um)
    finite = diffs[np.isfinite(diffs) & (np.abs(diffs) > 0)]
    return float(np.median(np.abs(finite))) if finite.size else 1.0


def _empty_lobe() -> dict:
    return {
        "peak_rel": float("nan"),
        "distance_um": float("nan"),
        "position_um": float("nan"),
        "prominence": float("nan"),
    }


def _peak_prominence(values: np.ndarray, local_index: int, side_indices: np.ndarray) -> float:
    side_set = set(int(i) for i in side_indices)
    left_min = float(values[local_index])
    idx = local_index
    while idx - 1 in side_set:
        idx -= 1
        left_min = min(left_min, float(values[idx]))
        if values[idx] > values[idx + 1]:
            break
    right_min = float(values[local_index])
    idx = local_index
    while idx + 1 in side_set:
        idx += 1
        right_min = min(right_min, float(values[idx]))
        if values[idx] > values[idx - 1]:
            break
    return float(values[local_index] - max(left_min, right_min))


def _outside_max_for_side(
    coord_um: np.ndarray,
    profile: np.ndarray,
    edge_um: float,
    side: str,
    margin_um: float,
    search_width_um: float,
) -> dict:
    if not np.isfinite(edge_um) or search_width_um <= 0:
        return _empty_lobe()
    if side == "left":
        mask = (coord_um >= edge_um - search_width_um) & (coord_um <= edge_um - margin_um)
    else:
        mask = (coord_um >= edge_um + margin_um) & (coord_um <= edge_um + search_width_um)
    valid = np.flatnonzero(mask & np.isfinite(profile))
    if valid.size == 0:
        return _empty_lobe()
    local = valid[int(np.argmax(profile[valid]))]
    return {
        "peak_rel": float(profile[local]),
        "distance_um": float(abs(coord_um[local] - edge_um)),
        "position_um": float(coord_um[local]),
        "prominence": float("nan"),
    }


def _derivative_lobes_for_side(
    coord_um: np.ndarray,
    smoothed_profile: np.ndarray,
    edge_um: float,
    side: str,
    margin_um: float,
    search_width_um: float,
    prominence_threshold: float,
) -> dict:
    if not np.isfinite(edge_um) or search_width_um <= 0:
        return {"first": _empty_lobe(), "strongest": _empty_lobe()}
    if side == "left":
        mask = (coord_um >= edge_um - search_width_um) & (coord_um <= edge_um - margin_um)
    else:
        mask = (coord_um >= edge_um + margin_um) & (coord_um <= edge_um + search_width_um)
    valid = np.flatnonzero(mask & np.isfinite(smoothed_profile))
    if valid.size < 3:
        return {"first": _empty_lobe(), "strongest": _empty_lobe()}

    candidates = []
    valid_set = set(int(i) for i in valid)
    derivative = np.gradient(smoothed_profile, coord_um)
    for idx in valid[1:-1]:
        if idx - 1 not in valid_set or idx + 1 not in valid_set:
            continue
        if not np.all(np.isfinite([derivative[idx - 1], derivative[idx + 1], smoothed_profile[idx]])):
            continue
        derivative_crosses = derivative[idx - 1] > 0.0 and derivative[idx + 1] < 0.0
        local_max = smoothed_profile[idx] >= smoothed_profile[idx - 1] and smoothed_profile[idx] >= smoothed_profile[idx + 1]
        if not (derivative_crosses or local_max):
            continue
        prominence = _peak_prominence(smoothed_profile, int(idx), valid)
        if prominence < prominence_threshold:
            continue
        candidates.append(
            {
                "peak_rel": float(smoothed_profile[idx]),
                "distance_um": float(abs(coord_um[idx] - edge_um)),
                "position_um": float(coord_um[idx]),
                "prominence": prominence,
            }
        )

    if not candidates:
        return {"first": _empty_lobe(), "strongest": _empty_lobe()}
    first = min(candidates, key=lambda item: item["distance_um"])
    strongest = max(candidates, key=lambda item: item["peak_rel"])
    return {"first": first, "strongest": strongest}


def side_lobe_analysis_for_profile(
    coord_um: np.ndarray,
    normalized_profile: np.ndarray,
    threshold: float,
    search_width_um: float,
    smoothing_sigma_um: float,
    crossing_margin_um: float,
    prominence_threshold: float,
) -> dict:
    edge_13 = _center_connected_edges(coord_um, normalized_profile, threshold)
    spacing_um = _profile_spacing_um(coord_um)
    sigma_px = smoothing_sigma_um / spacing_um if spacing_um > 0 else 0.0
    smoothed = _gaussian_smooth_1d(normalized_profile, sigma_px)
    derivative = np.gradient(smoothed, coord_um)
    left_edge, right_edge, _ = edge_13

    outside_left = _outside_max_for_side(
        coord_um, normalized_profile, left_edge, "left", crossing_margin_um, search_width_um
    )
    outside_right = _outside_max_for_side(
        coord_um, normalized_profile, right_edge, "right", crossing_margin_um, search_width_um
    )
    derivative_left = _derivative_lobes_for_side(
        coord_um,
        smoothed,
        left_edge,
        "left",
        crossing_margin_um,
        search_width_um,
        prominence_threshold,
    )
    derivative_right = _derivative_lobes_for_side(
        coord_um,
        smoothed,
        right_edge,
        "right",
        crossing_margin_um,
        search_width_um,
        prominence_threshold,
    )
    return {
        "edge_13": edge_13,
        "smoothed_profile": smoothed,
        "derivative": derivative,
        "smoothing_sigma_um": float(smoothing_sigma_um),
        "smoothing_sigma_px": float(sigma_px),
        "crossing_margin_um": float(crossing_margin_um),
        "prominence_threshold": float(prominence_threshold),
        "outside_max_left": outside_left,
        "outside_max_right": outside_right,
        "derivative_left": derivative_left,
        "derivative_right": derivative_right,
    }


def _side_lobe_metrics(axis_label: str, analysis: dict) -> dict:
    left = analysis["derivative_left"]
    right = analysis["derivative_right"]
    outside_left = analysis["outside_max_left"]
    outside_right = analysis["outside_max_right"]
    return {
        f"outside_max_{axis_label}_left_rel_to_core": outside_left["peak_rel"],
        f"outside_max_{axis_label}_right_rel_to_core": outside_right["peak_rel"],
        f"outside_max_{axis_label}_left_distance_um": outside_left["distance_um"],
        f"outside_max_{axis_label}_right_distance_um": outside_right["distance_um"],
        f"outside_max_{axis_label}_left_position_um": outside_left["position_um"],
        f"outside_max_{axis_label}_right_position_um": outside_right["position_um"],
        f"outside_max_{axis_label}_rel_to_core": max(
            outside_left["peak_rel"], outside_right["peak_rel"]
        ),
        f"first_side_lobe_peak_{axis_label}_left_rel_to_core": left["first"]["peak_rel"],
        f"first_side_lobe_peak_{axis_label}_right_rel_to_core": right["first"]["peak_rel"],
        f"strongest_side_lobe_peak_{axis_label}_left_rel_to_core": left["strongest"]["peak_rel"],
        f"strongest_side_lobe_peak_{axis_label}_right_rel_to_core": right["strongest"]["peak_rel"],
        f"first_side_lobe_distance_{axis_label}_left_um": left["first"]["distance_um"],
        f"first_side_lobe_distance_{axis_label}_right_um": right["first"]["distance_um"],
        f"strongest_side_lobe_distance_{axis_label}_left_um": left["strongest"]["distance_um"],
        f"strongest_side_lobe_distance_{axis_label}_right_um": right["strongest"]["distance_um"],
        f"first_side_lobe_position_{axis_label}_left_um": left["first"]["position_um"],
        f"first_side_lobe_position_{axis_label}_right_um": right["first"]["position_um"],
        f"strongest_side_lobe_position_{axis_label}_left_um": left["strongest"]["position_um"],
        f"strongest_side_lobe_position_{axis_label}_right_um": right["strongest"]["position_um"],
        f"first_side_lobe_prominence_{axis_label}_left": left["first"]["prominence"],
        f"first_side_lobe_prominence_{axis_label}_right": right["first"]["prominence"],
        f"strongest_side_lobe_prominence_{axis_label}_left": left["strongest"]["prominence"],
        f"strongest_side_lobe_prominence_{axis_label}_right": right["strongest"]["prominence"],
    }


def _stronger_peak(left: dict, right: dict) -> dict:
    left_peak = left["peak_rel"] if np.isfinite(left["peak_rel"]) else -np.inf
    right_peak = right["peak_rel"] if np.isfinite(right["peak_rel"]) else -np.inf
    if left_peak == -np.inf and right_peak == -np.inf:
        return _empty_lobe()
    return left if left_peak >= right_peak else right


def _profile_measurements(
    coord_x_um: np.ndarray,
    x_profile: np.ndarray,
    coord_y_um: np.ndarray,
    y_profile: np.ndarray,
    level_90: float,
    level_13: float,
    prefix: str = "",
) -> dict:
    key = f"{prefix}_" if prefix else ""
    x_edges_90 = _center_connected_edges(coord_x_um, x_profile, level_90)
    x_edges_50 = _center_connected_edges(coord_x_um, x_profile, 0.5)
    x_edges_13 = _center_connected_edges(coord_x_um, x_profile, level_13)
    y_edges_90 = _center_connected_edges(coord_y_um, y_profile, level_90)
    y_edges_50 = _center_connected_edges(coord_y_um, y_profile, 0.5)
    y_edges_13 = _center_connected_edges(coord_y_um, y_profile, level_13)

    return {
        f"{key}size_90_x_um": x_edges_90[2],
        f"{key}size_90_y_um": y_edges_90[2],
        f"{key}size_50_x_um": x_edges_50[2],
        f"{key}size_50_y_um": y_edges_50[2],
        f"{key}size_13p5_x_um": x_edges_13[2],
        f"{key}size_13p5_y_um": y_edges_13[2],
        f"{key}transition_width_13_90_x_um": _transition_width(x_edges_90, x_edges_13),
        f"{key}transition_width_13_90_y_um": _transition_width(y_edges_90, y_edges_13),
        f"{key}x_left_90_um": x_edges_90[0],
        f"{key}x_right_90_um": x_edges_90[1],
        f"{key}x_left_50_um": x_edges_50[0],
        f"{key}x_right_50_um": x_edges_50[1],
        f"{key}x_left_13p5_um": x_edges_13[0],
        f"{key}x_right_13p5_um": x_edges_13[1],
        f"{key}y_left_90_um": y_edges_90[0],
        f"{key}y_right_90_um": y_edges_90[1],
        f"{key}y_left_50_um": y_edges_50[0],
        f"{key}y_right_50_um": y_edges_50[1],
        f"{key}y_left_13p5_um": y_edges_13[0],
        f"{key}y_right_13p5_um": y_edges_13[1],
    }


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
    target_x_profile = ti[cy, :]
    target_y_profile = ti[:, cx]

    output_measurements = _profile_measurements(
        grid.x_um_focus,
        x_profile,
        grid.y_um_focus,
        y_profile,
        config.metric_uniform_level,
        config.free_region_threshold_intensity,
        prefix="output",
    )
    x_lobes = side_lobe_analysis_for_profile(
        grid.x_um_focus,
        x_profile,
        config.free_region_threshold_intensity,
        config.side_lobe_search_width_um,
        config.side_lobe_smoothing_sigma_um,
        config.side_lobe_crossing_margin_um,
        config.side_lobe_prominence_threshold,
    )
    y_lobes = side_lobe_analysis_for_profile(
        grid.y_um_focus,
        y_profile,
        config.free_region_threshold_intensity,
        config.side_lobe_search_width_um,
        config.side_lobe_smoothing_sigma_um,
        config.side_lobe_crossing_margin_um,
        config.side_lobe_prominence_threshold,
    )
    x_outside_max = _stronger_peak(x_lobes["outside_max_left"], x_lobes["outside_max_right"])
    y_outside_max = _stronger_peak(y_lobes["outside_max_left"], y_lobes["outside_max_right"])
    target_measurements = _profile_measurements(
        grid.x_um_focus,
        target_x_profile,
        grid.y_um_focus,
        target_y_profile,
        config.metric_uniform_level,
        config.free_region_threshold_intensity,
        prefix="target",
    )

    x_50_roi = np.abs(grid.x_um_focus) <= config.target_width_um / 2.0
    y_50_roi = np.abs(grid.y_um_focus) <= config.target_height_um / 2.0
    _, _, x_std, x_p2p = _rms_about_one(x_profile[x_50_roi])
    _, _, y_std, y_p2p = _rms_about_one(y_profile[y_50_roi])

    flatness_score = float(np.nan_to_num(x_std, nan=1e9) + np.nan_to_num(y_std, nan=1e9))

    metrics = {
        **output_measurements,
        **target_measurements,
        "size_90_x_um": output_measurements["output_size_90_x_um"],
        "size_90_y_um": output_measurements["output_size_90_y_um"],
        "size_50_x_um": output_measurements["output_size_50_x_um"],
        "size_50_y_um": output_measurements["output_size_50_y_um"],
        "size_13p5_x_um": output_measurements["output_size_13p5_x_um"],
        "size_13p5_y_um": output_measurements["output_size_13p5_y_um"],
        "transition_width_13_90_x_um": output_measurements["output_transition_width_13_90_x_um"],
        "transition_width_13_90_y_um": output_measurements["output_transition_width_13_90_y_um"],
        "efficiency_13p5": efficiency_13,
        "rms_core": rms_core,
        "rms_90": rms_90,
        "rms_50_reference": rms_50,
        "center_profile_p2p_x": x_p2p,
        "center_profile_p2p_y": y_p2p,
        "center_profile_std_x": x_std,
        "center_profile_std_y": y_std,
        "center_profile_flatness_score": flatness_score,
        "side_lobe_smoothing_sigma_um": x_lobes["smoothing_sigma_um"],
        "side_lobe_smoothing_sigma_px": x_lobes["smoothing_sigma_px"],
        "side_lobe_crossing_margin_um": x_lobes["crossing_margin_um"],
        "side_lobe_prominence_threshold": x_lobes["prominence_threshold"],
        **_side_lobe_metrics("x", x_lobes),
        **_side_lobe_metrics("y", y_lobes),
        "outside_max_x_rel_to_core": x_outside_max["peak_rel"],
        "outside_max_y_rel_to_core": y_outside_max["peak_rel"],
        "outside_max_distance_x_um": x_outside_max["distance_um"],
        "outside_max_distance_y_um": y_outside_max["distance_um"],
        "outside_max_position_x_um": x_outside_max["position_um"],
        "outside_max_position_y_um": y_outside_max["position_um"],
        # Deprecated aliases: these now point to outside_max for old scripts only.
        "side_lobe_peak_x": float(x_outside_max["peak_rel"] * reference) if reference > 0 else float("nan"),
        "side_lobe_peak_y": float(y_outside_max["peak_rel"] * reference) if reference > 0 else float("nan"),
        "side_lobe_peak_x_rel_to_core": x_outside_max["peak_rel"],
        "side_lobe_peak_y_rel_to_core": y_outside_max["peak_rel"],
        "side_lobe_distance_x_um": x_outside_max["distance_um"],
        "side_lobe_distance_y_um": y_outside_max["distance_um"],
        "side_lobe_position_x_um": x_outside_max["position_um"],
        "side_lobe_position_y_um": y_outside_max["position_um"],
        "side_lobe_side_x": "outside_max",
        "side_lobe_side_y": "outside_max",
        "reference_intensity": reference,
        "reference_source": reference_source,
        "target_13p5_pixel_count": int(np.count_nonzero(mask_13)),
        "target_50_pixel_count": int(np.count_nonzero(mask_50)),
        "target_90_pixel_count": int(np.count_nonzero(mask_90)),
        "target_core_pixel_count": int(np.count_nonzero(mask_core)),
        "x_left_90_um": output_measurements["output_x_left_90_um"],
        "x_right_90_um": output_measurements["output_x_right_90_um"],
        "x_left_50_um": output_measurements["output_x_left_50_um"],
        "x_right_50_um": output_measurements["output_x_right_50_um"],
        "x_left_13p5_um": output_measurements["output_x_left_13p5_um"],
        "x_right_13p5_um": output_measurements["output_x_right_13p5_um"],
        "y_left_90_um": output_measurements["output_y_left_90_um"],
        "y_right_90_um": output_measurements["output_y_right_90_um"],
        "y_left_50_um": output_measurements["output_y_left_50_um"],
        "y_right_50_um": output_measurements["output_y_right_50_um"],
        "y_left_13p5_um": output_measurements["output_y_left_13p5_um"],
        "y_right_13p5_um": output_measurements["output_y_right_13p5_um"],
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
        "size_50_x": output_measurements["output_size_50_x_um"],
        "size_50_y": output_measurements["output_size_50_y_um"],
    }
    return metrics


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
