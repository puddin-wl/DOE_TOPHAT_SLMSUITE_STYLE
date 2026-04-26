from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import DOEConfig
from .propagation import Propagator


@dataclass
class SolverResult:
    phase: np.ndarray
    focal_field: np.ndarray
    focal_intensity: np.ndarray
    history: list[dict] = field(default_factory=list)


def _safe_phase_factor(field: np.ndarray) -> np.ndarray:
    amplitude = np.abs(field)
    return np.exp(1j * np.angle(field)) * (amplitude > 0)


def normalized_target_weights(target_amplitude: np.ndarray) -> np.ndarray:
    weights = np.nan_to_num(target_amplitude, nan=0.0, posinf=0.0, neginf=0.0).astype(
        np.float64,
        copy=True,
    )
    norm = np.sqrt(np.sum(weights**2))
    if norm > 0:
        weights /= norm
    return weights


def apply_focal_constraint(
    focal_field: np.ndarray,
    target_amplitude: np.ndarray,
    method: str,
    mraf_factor: float = 1.0,
    target_power_fraction: float | None = None,
    target_weights: np.ndarray | None = None,
) -> tuple[np.ndarray, dict]:
    method = method.lower()
    noise = np.isnan(target_amplitude)
    finite = ~noise
    zero = finite & (np.abs(target_amplitude) == 0.0)
    signal = finite & ~zero
    constrained = np.array(focal_field, copy=True)
    phase = _safe_phase_factor(focal_field)

    weights = target_weights if target_weights is not None else normalized_target_weights(target_amplitude)
    signal_power = float(np.sum(np.abs(focal_field[signal]) ** 2))
    zero_power = float(np.sum(np.abs(focal_field[zero]) ** 2))
    noise_power = float(np.sum(np.abs(focal_field[noise]) ** 2))
    total_power = float(np.sum(np.abs(focal_field) ** 2))
    target_norm = float(np.sum(weights[signal] ** 2))
    scale = 1.0
    if target_power_fraction is not None:
        desired_power = total_power * float(target_power_fraction)
        scale = np.sqrt(desired_power / target_norm) if target_norm > 0 else 1.0

    constrained[signal] = scale * weights[signal] * phase[signal]
    constrained[zero] = 0.0

    if method == "gs":
        constrained[noise] = 0.0
    elif method == "mraf":
        constrained[noise] = mraf_factor * focal_field[noise]
    else:
        raise ValueError(f"Unknown method: {method!r}")

    stats = {
        "signal_pixels": int(np.count_nonzero(signal)),
        "noise_pixels": int(np.count_nonzero(noise)),
        "zero_pixels": int(np.count_nonzero(zero)),
        "finite_pixels": int(np.count_nonzero(finite)),
        "target_scale": float(scale),
        "target_weights_norm": float(np.sqrt(np.sum(weights**2))),
        "signal_power_before": signal_power,
        "noise_power_before": noise_power,
        "zero_power_before": zero_power,
        "total_power_before": total_power,
        "noise_region_forced_zero": bool(
            np.any(noise) and (method == "gs" or (method == "mraf" and mraf_factor == 0))
        ),
        "noise_region_preserved": bool(np.any(noise) and method == "mraf" and mraf_factor == 1.0),
        "noise_region_relaxed_not_zero": bool(
            np.any(noise) and method == "mraf" and 0.0 < mraf_factor < 1.0
        ),
        "zero_region_forced_zero": bool(np.any(zero)),
    }
    return constrained, stats


def update_weights_leonardo(
    weights: np.ndarray,
    focal_field: np.ndarray,
    target_weights: np.ndarray,
    signal_mask: np.ndarray,
    exponent: float,
) -> np.ndarray:
    feedback = np.abs(focal_field)
    feedback_signal = np.zeros_like(weights)
    feedback_signal[signal_mask] = feedback[signal_mask]

    feedback_norm = np.sqrt(np.sum(feedback_signal[signal_mask] ** 2))
    if feedback_norm <= 0:
        return weights
    feedback_signal[signal_mask] /= feedback_norm

    ratio = np.ones_like(weights)
    valid = signal_mask & (target_weights > 0)
    ratio[valid] = feedback_signal[valid] / target_weights[valid]
    ratio[~np.isfinite(ratio)] = 1.0
    ratio[ratio <= 0] = 1.0

    updated = np.array(weights, copy=True)
    updated[valid] *= ratio[valid] ** (-exponent)
    updated[~signal_mask] = 0.0
    norm = np.sqrt(np.sum(updated**2))
    if norm > 0:
        updated /= norm
    return updated


def solve_phase(
    config: DOEConfig,
    input_amplitude: np.ndarray,
    initial_phase: np.ndarray,
    target_amplitude: np.ndarray,
    propagator: Propagator,
) -> SolverResult:
    phase = np.array(initial_phase, copy=True)
    history: list[dict] = []
    target_weights = normalized_target_weights(target_amplitude)
    signal_mask = np.isfinite(target_amplitude) & (np.abs(target_amplitude) > 0.0)
    target_weights_reference = np.array(target_weights, copy=True)
    method = config.method.lower()
    use_wgs = method in {"wgs", "wgs-leonardo", "wgs_mraf_leonardo", "wgs-mraf-leonardo"}

    for iteration in range(config.iterations):
        doe_field = input_amplitude * np.exp(1j * phase)
        focal_field = propagator.forward(doe_field)
        if use_wgs and iteration > 0:
            target_weights = update_weights_leonardo(
                target_weights,
                focal_field,
                target_weights_reference,
                signal_mask,
                config.feedback_exponent,
            )
        constrained_focal, stats = apply_focal_constraint(
            focal_field,
            target_amplitude,
            method="mraf" if use_wgs else config.method,
            mraf_factor=config.mraf_factor,
            target_power_fraction=config.target_power_fraction,
            target_weights=target_weights,
        )
        back_field = propagator.backward(constrained_focal)
        phase = np.angle(back_field)
        history.append({"iteration": iteration + 1, "wgs_enabled": use_wgs, **stats})

    final_field = propagator.forward(input_amplitude * np.exp(1j * phase))
    final_intensity = np.abs(final_field) ** 2
    return SolverResult(
        phase=np.mod(phase, 2.0 * np.pi),
        focal_field=final_field,
        focal_intensity=final_intensity,
        history=history,
    )
