from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from src.config import DOEConfig, update_config
from src.grids import make_grid
from src.metrics import target_intensity
from src.plotting import _profile_reference_intensity
from src.targets import TargetResult, make_target


FROZEN_DIR = Path("artifacts/mraf_fine_20260426-025728/mraf_0p400")
ROUNDED_DIR = Path("artifacts/rounded_logistic_single_20260426/rounded_logistic_single")
SMOOTH_DIR = Path("artifacts/smooth_tail_single_20260426-211623/smooth_tail_single")

CASES = [
    ("frozen_best", "industrial_logistic", FROZEN_DIR),
    ("old_rounded_single", "industrial_rounded_logistic", ROUNDED_DIR),
    ("failed_smooth_tail_single", "industrial_rounded_logistic_smooth_tail", SMOOTH_DIR),
]


def config_from_json(path: Path) -> DOEConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    fields = DOEConfig.__dataclass_fields__.keys()
    return update_config(DOEConfig(), **{key: payload[key] for key in fields if key in payload})


def as_float(value) -> float:
    return float(value) if value is not None else float("nan")


def case_target(artifact_dir: Path) -> tuple[DOEConfig, object, TargetResult, np.ndarray]:
    config = config_from_json(artifact_dir / "config.json")
    grid = make_grid(config)
    target = make_target(config, grid)
    intensity = target_intensity(target)
    return config, grid, target, intensity


def target_mask_row(label: str, target_type: str, artifact_dir: Path) -> dict:
    config, grid, target, intensity = case_target(artifact_dir)
    amplitude = target.amplitude
    finite = np.isfinite(amplitude)
    core = finite & (intensity >= 0.9)
    transition = finite & (intensity >= 0.135) & (intensity < 0.9)
    tail = finite & (intensity < 0.135)
    noise = ~finite
    pixel_area = grid.focus_sampling_um**2
    finite_intensity = intensity[finite]
    finite_amplitude = amplitude[finite]
    total_sum = float(np.nansum(intensity[finite]))
    tail_sum = float(np.nansum(intensity[tail]))
    return {
        "case_label": label,
        "target_type": target_type,
        "artifact_dir": str(artifact_dir),
        "finite_pixel_count": int(np.count_nonzero(finite)),
        "core_pixel_count": int(np.count_nonzero(core)),
        "transition_pixel_count": int(np.count_nonzero(transition)),
        "noise_or_free_pixel_count": int(np.count_nonzero(noise)),
        "nan_pixel_count": int(np.count_nonzero(np.isnan(amplitude))),
        "finite_area_um2": float(np.count_nonzero(finite) * pixel_area),
        "core_area_um2": float(np.count_nonzero(core) * pixel_area),
        "transition_area_um2": float(np.count_nonzero(transition) * pixel_area),
        "tail_area_um2": float(np.count_nonzero(tail) * pixel_area),
        "total_target_intensity_sum": total_sum,
        "core_target_intensity_sum": float(np.nansum(intensity[core])),
        "transition_target_intensity_sum": float(np.nansum(intensity[transition])),
        "tail_target_intensity_sum": tail_sum,
        "tail_power_fraction": tail_sum / total_sum if total_sum > 0 else float("nan"),
        "min_finite_target_amplitude": float(np.nanmin(finite_amplitude)) if finite_amplitude.size else float("nan"),
        "max_finite_target_amplitude": float(np.nanmax(finite_amplitude)) if finite_amplitude.size else float("nan"),
        "min_finite_target_intensity": float(np.nanmin(finite_intensity)) if finite_intensity.size else float("nan"),
        "max_finite_target_intensity": float(np.nanmax(finite_intensity)) if finite_intensity.size else float("nan"),
        "has_nan": bool(np.isnan(amplitude).any()),
        "has_inf": bool(np.isinf(amplitude).any() or np.isinf(intensity).any()),
        "has_negative_intensity": bool(np.nanmin(intensity) < -1e-12),
        "has_hermite_overshoot": bool(target_type.endswith("smooth_tail") and (np.nanmin(intensity[finite]) < -1e-12 or np.nanmax(intensity[finite]) > 1.0 + 1e-12)),
    }


def write_target_mask_csv(out_root: Path) -> list[dict]:
    rows = [target_mask_row(*case) for case in CASES]
    path = out_root / "target_mask_power_comparison.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def write_solver_review(out_root: Path) -> None:
    text = """# Smooth-tail solver logic review

Files reviewed: `src/mraf.py`, `src/targets.py`, and `src/config.py`.

## NaN / finite target handling

- Target amplitudes use `NaN` to mark free/noise pixels.
- `apply_focal_constraint()` sets `noise = np.isnan(target_amplitude)` and `finite = ~noise`.
- Signal pixels are every finite pixel with nonzero target amplitude: `signal = finite & ~zero`.
- `normalized_target_weights()` converts `NaN` to 0 and normalizes all finite nonzero target amplitudes into one global target-weight vector.
- Therefore every finite nonzero target pixel participates in the signal constraint, including very low-amplitude 3%-13.5% smooth-tail pixels.

## MRAF / WGS behavior

- For WGS methods, `solve_phase()` still calls `apply_focal_constraint()` with `method="mraf"` and the configured `mraf_factor`.
- Finite signal pixels are replaced by `scale * weights[signal] * phase[signal]` every iteration.
- Noise/free pixels are relaxed as `mraf_factor * focal_field[noise]`; with `mraf_factor=0.40`, free/noise is damped, not preserved.
- WGS feedback is applied to all finite signal pixels through `update_weights_leonardo()`.

## Feedback formula and numerical guards

- WGS feedback computes a normalized current focal amplitude over signal pixels.
- The ratio is `feedback_signal / target_weights` on all finite signal pixels.
- Updated weights are multiplied by `ratio ** (-feedback_exponent)`.
- With `feedback_exponent=2.0`, pixels whose current amplitude is small relative to target can be strongly upweighted.
- Non-finite and non-positive ratios are reset to 1.0, but there is no explicit current-amplitude floor, no ratio clipping, and no weight clipping before renormalization.

## Smooth-tail risk

- The smooth-tail target expands the finite signal region below 13.5% down to 3% intensity.
- Those low-amplitude tail pixels are not weak constraints in the current solver; they are ordinary finite signal pixels.
- Because their target weights are small but nonzero, WGS feedback can still amplify them when current amplitude is locally low.
- The combination of many low-intensity finite pixels, exponent 2.0, no ratio clipping, and MRAF damping of free/noise pixels is a plausible solver failure path.
- This can redirect the iterative weight distribution away from the intended rectangular flat-top and into an unstable central-spot collapse.

## Postmortem conclusion

The likely issue is not rounded geometry alone. The current WGS/MRAF implementation treats the low-intensity smooth tail as a normal finite strong constraint. A safer future direction would require explicit mask-weighted constraints or weak-tail handling before any smooth-tail parameter sweep.
"""
    (out_root / "solver_logic_review.md").write_text(text, encoding="utf-8")


def failed_artifact_review(out_root: Path) -> dict:
    config = json.loads((SMOOTH_DIR / "config.json").read_text(encoding="utf-8"))
    metrics = json.loads((SMOOTH_DIR / "metrics.json").read_text(encoding="utf-8"))
    focal = np.load(SMOOTH_DIR / "focal_intensity.npy")
    target_amp_path = SMOOTH_DIR / "target_amplitude.npy"
    target_amp = np.load(target_amp_path if target_amp_path.exists() else SMOOTH_DIR / "target.npy")
    phase = np.load(SMOOTH_DIR / "phase.npy")
    cfg = config_from_json(SMOOTH_DIR / "config.json")
    grid = make_grid(cfg)
    peak_index = np.unravel_index(int(np.nanargmax(focal)), focal.shape)
    center = grid.n // 2
    radius25 = np.hypot(*np.meshgrid(grid.x_um_focus, grid.y_um_focus)) <= 25.0
    radius100 = np.hypot(*np.meshgrid(grid.x_um_focus, grid.y_um_focus)) <= 100.0
    total = float(np.nansum(focal))
    review = {
        "config_summary": {
            "target": config.get("target"),
            "n": config.get("n"),
            "iterations": config.get("iterations"),
            "method": config.get("method"),
            "phase_init": config.get("phase_init"),
            "target_size_50_x_um": config.get("target_width_um"),
            "target_size_50_y_um": config.get("target_height_um"),
            "transition_width_13_90_x_um": config.get("transition_width_13_90_x_um"),
            "transition_width_13_90_y_um": config.get("transition_width_13_90_y_um"),
            "mraf_factor": config.get("mraf_factor"),
            "feedback_exponent": config.get("feedback_exponent"),
            "descending_edge_mode": config.get("descending_edge_mode"),
            "controlled_tail_end_intensity": config.get("controlled_tail_end_intensity"),
            "controlled_tail_width_x_um": config.get("controlled_tail_width_x_um"),
            "controlled_tail_width_y_um": config.get("controlled_tail_width_y_um"),
            "last_iteration": config.get("last_iteration"),
        },
        "metrics_summary": {
            "output_size_50_x_um": metrics.get("output_size_50_x_um"),
            "output_size_50_y_um": metrics.get("output_size_50_y_um"),
            "rms_90": metrics.get("rms_90"),
            "efficiency_13p5": metrics.get("efficiency_13p5"),
            "outside_peak_detection_count": metrics.get("outside_peak_detection_count"),
            "outside_max_x_rel_to_core": metrics.get("outside_max_x_rel_to_core"),
            "outside_max_y_rel_to_core": metrics.get("outside_max_y_rel_to_core"),
        },
        "focal_intensity_stats": {
            "min": float(np.nanmin(focal)),
            "max": float(np.nanmax(focal)),
            "mean": float(np.nanmean(focal)),
            "sum": total,
        },
        "target_amplitude_stats": {
            "finite_count": int(np.count_nonzero(np.isfinite(target_amp))),
            "nan_count": int(np.count_nonzero(np.isnan(target_amp))),
            "min_finite": float(np.nanmin(target_amp[np.isfinite(target_amp)])),
            "max_finite": float(np.nanmax(target_amp[np.isfinite(target_amp)])),
        },
        "phase_stats": {
            "min": float(np.nanmin(phase)),
            "max": float(np.nanmax(phase)),
            "std": float(np.nanstd(phase)),
        },
        "has_nan_or_inf": bool(
            np.isnan(focal).any()
            or np.isinf(focal).any()
            or np.isnan(target_amp[np.isfinite(target_amp)]).any()
            or np.isinf(target_amp[np.isfinite(target_amp)]).any()
            or np.isnan(phase).any()
            or np.isinf(phase).any()
        ),
        "focal_peak_location": {
            "row": int(peak_index[0]),
            "col": int(peak_index[1]),
            "x_um": float(grid.x_um_focus[peak_index[1]]),
            "y_um": float(grid.y_um_focus[peak_index[0]]),
        },
        "focal_peak_value": float(np.nanmax(focal)),
        "energy_concentration_ratio_25um": float(np.nansum(focal[radius25]) / total),
        "energy_concentration_ratio_100um": float(np.nansum(focal[radius100]) / total),
        "output50_central_spot_like": bool(metrics.get("output_size_50_x_um", 999) < 100 and metrics.get("output_size_50_y_um", 999) < 100),
        "failure_classification": "central spot collapse / target shape not formed",
    }
    (out_root / "failed_smooth_tail_artifact_review.json").write_text(json.dumps(review, indent=2), encoding="utf-8")
    return review


def normalized_output(artifact_dir: Path):
    config, grid, target, target_i = case_target(artifact_dir)
    focal = np.load(artifact_dir / "focal_intensity.npy")
    ref = _profile_reference_intensity(target, focal)
    norm = focal / ref if ref > 0 else focal
    return config, grid, target_i, norm


def save_failed_focal_with_contours(out_root: Path) -> None:
    config, grid, target_i, focal = normalized_output(SMOOTH_DIR)
    crop = np.abs(grid.x_um_focus) <= 300
    data = focal[np.ix_(crop, crop)]
    target_crop = target_i[np.ix_(crop, crop)]
    x = grid.x_um_focus[crop]
    y = grid.y_um_focus[crop]
    fig, ax = plt.subplots(figsize=(6.5, 5.6), dpi=160)
    im = ax.imshow(data, extent=[float(x[0]), float(x[-1]), float(y[0]), float(y[-1])], origin="lower", cmap="magma")
    ax.contour(x, y, target_crop, levels=[0.03, 0.135, 0.5, 0.9], colors=["cyan", "purple", "white", "lime"], linewidths=0.8)
    ax.set_title("failed smooth-tail focal intensity with target contours")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="output I / core mean")
    fig.tight_layout()
    fig.savefig(out_root / "failed_smooth_tail_focal_with_target_contours.png")
    plt.close(fig)


def save_failed_profiles(out_root: Path) -> None:
    config, grid, target_i, focal = normalized_output(SMOOTH_DIR)
    center = grid.n // 2
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), dpi=160)
    for ax, coord, output, target, axis in [
        (axes[0], grid.x_um_focus, focal[center, :], target_i[center, :], "x"),
        (axes[1], grid.y_um_focus, focal[:, center], target_i[:, center], "y"),
    ]:
        view = np.abs(coord) <= 400
        ax.plot(coord[view], output[view], label="failed output", lw=1.2)
        ax.plot(coord[view], target[view], label="target intensity", lw=1.2)
        for level, color in [(0.9, "tab:green"), (0.5, "tab:red"), (0.135, "tab:purple"), (0.03, "tab:cyan")]:
            ax.axhline(level, color=color, lw=0.8, alpha=0.45)
        ax.set_title(f"failed smooth-tail {axis} center profile")
        ax.set_xlabel(f"{axis} (um)")
        ax.set_ylabel("normalized intensity")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_root / "failed_smooth_tail_x_y_profiles_with_target.png")
    plt.close(fig)


def save_mask_comparison(out_root: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), dpi=160)
    for ax, (_, target_type, artifact_dir) in zip(axes, CASES):
        config, grid, target, intensity = case_target(artifact_dir)
        mask = np.zeros_like(intensity)
        finite = np.isfinite(target.amplitude)
        mask[finite & (intensity < 0.135)] = 1
        mask[finite & (intensity >= 0.135) & (intensity < 0.9)] = 2
        mask[finite & (intensity >= 0.9)] = 3
        mask[~finite] = 4
        crop = np.abs(grid.x_um_focus) <= 260
        data = mask[np.ix_(crop, crop)]
        x = grid.x_um_focus[crop]
        ax.imshow(data, extent=[float(x[0]), float(x[-1]), float(x[0]), float(x[-1])], origin="lower", cmap="tab10", vmin=0, vmax=4)
        ax.set_title(target_type)
        ax.set_xlabel("x (um)")
        ax.set_ylabel("y (um)")
    fig.suptitle("target masks: 1 tail, 2 transition, 3 core, 4 free/NaN")
    fig.tight_layout()
    fig.savefig(out_root / "target_mask_comparison_frozen_rounded_smooth.png")
    plt.close(fig)


def save_power_distribution(out_root: Path, rows: list[dict]) -> None:
    labels = [row["target_type"].replace("industrial_", "") for row in rows]
    core = [row["core_target_intensity_sum"] for row in rows]
    transition = [row["transition_target_intensity_sum"] for row in rows]
    tail = [row["tail_target_intensity_sum"] for row in rows]
    x = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(9.0, 4.8), dpi=160)
    ax.bar(x, core, label="core >=90%")
    ax.bar(x, transition, bottom=core, label="13.5%-90%")
    ax.bar(x, tail, bottom=np.array(core) + np.array(transition), label="tail <13.5%")
    ax.set_xticks(x, labels, rotation=15, ha="right")
    ax.set_ylabel("target intensity sum")
    ax.set_title("target power distribution comparison")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_root / "target_power_distribution_comparison.png")
    plt.close(fig)


def save_focal_comparison(out_root: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), dpi=160)
    for ax, (_, target_type, artifact_dir) in zip(axes, CASES):
        config, grid, _, focal = normalized_output(artifact_dir)
        crop = np.abs(grid.x_um_focus) <= 300
        data = focal[np.ix_(crop, crop)]
        x = grid.x_um_focus[crop]
        im = ax.imshow(data, extent=[float(x[0]), float(x[-1]), float(x[0]), float(x[-1])], origin="lower", cmap="magma", vmin=0, vmax=np.nanpercentile(data, 99.5))
        ax.set_title(target_type)
        ax.set_xlabel("x (um)")
        ax.set_ylabel("y (um)")
    fig.suptitle("focal intensity comparison: smooth-tail collapses to central spot")
    fig.tight_layout()
    fig.savefig(out_root / "focal_intensity_comparison_frozen_rounded_smooth.png")
    plt.close(fig)


def save_center_profile_comparison(out_root: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), dpi=160)
    for _, target_type, artifact_dir in CASES:
        config, grid, _, focal = normalized_output(artifact_dir)
        center = grid.n // 2
        for ax, coord, profile, axis in [
            (axes[0], grid.x_um_focus, focal[center, :], "x"),
            (axes[1], grid.y_um_focus, focal[:, center], "y"),
        ]:
            view = np.abs(coord) <= 650
            ax.plot(coord[view], profile[view], lw=1.1, label=target_type)
            ax.set_xlabel(f"{axis} (um)")
            ax.set_ylabel("output I / core mean")
            ax.grid(alpha=0.25)
    axes[0].set_title("x center profile comparison")
    axes[1].set_title("y center profile comparison")
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_root / "center_profile_comparison_frozen_rounded_smooth.png")
    plt.close(fig)


def write_postmortem_summary(out_root: Path, rows: list[dict], artifact_review: dict) -> None:
    area_comparison = {
        row["target_type"]: {
            "finite_area_um2": row["finite_area_um2"],
            "tail_area_um2": row["tail_area_um2"],
        }
        for row in rows
    }
    tail_fraction = {row["target_type"]: row["tail_power_fraction"] for row in rows}
    summary = {
        "frozen_best_artifact_dir": str(FROZEN_DIR),
        "old_rounded_artifact_dir": str(ROUNDED_DIR),
        "smooth_tail_artifact_dir": str(SMOOTH_DIR),
        "smooth_tail_failure_confirmed": True,
        "failure_classification": "central spot collapse / target shape not formed",
        "likely_primary_cause": "current WGS/MRAF treats low-intensity smooth tail as ordinary finite target constraint, causing unstable feedback / wrong energy allocation",
        "likely_secondary_causes": [
            "WGS feedback applies to all finite nonzero target pixels, including 3%-13.5% tail pixels",
            "feedback_exponent=2.0 amplifies low-current finite pixels without explicit ratio clipping",
            "mraf_factor=0.40 damps free/noise pixels while the expanded finite tail remains strongly constrained",
            "smooth-tail target has many more finite low-intensity pixels than industrial_logistic",
        ],
        "target_finite_area_comparison": area_comparison,
        "target_tail_power_fraction": tail_fraction,
        "solver_feedback_risk_summary": "NaN pixels are free/noise, but all finite nonzero amplitudes become signal pixels. The WGS ratio update has guards for nonfinite/nonpositive ratios, but no current floor or clipping. Low-intensity tail pixels can therefore behave as ordinary finite constraints rather than weak penalties.",
        "artifact_review_highlights": {
            "output50_x_um": artifact_review["metrics_summary"]["output_size_50_x_um"],
            "output50_y_um": artifact_review["metrics_summary"]["output_size_50_y_um"],
            "rms_90": artifact_review["metrics_summary"]["rms_90"],
            "efficiency_13p5": artifact_review["metrics_summary"]["efficiency_13p5"],
            "outside_peak_detection_count": artifact_review["metrics_summary"]["outside_peak_detection_count"],
            "energy_concentration_ratio_25um": artifact_review["energy_concentration_ratio_25um"],
            "energy_concentration_ratio_100um": artifact_review["energy_concentration_ratio_100um"],
        },
        "recommended_next_step": "do not sweep smooth-tail parameters; keep frozen best; if continuing rounded/tail direction, implement weak-tail constraint or mask-weighted WGS first",
        "not_recommended_actions": [
            "sweep smooth-tail tail_width",
            "sweep mraf_factor",
            "enable descending_edge",
            "run 4096",
            "replace frozen best",
        ],
    }
    (out_root / "postmortem_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    out_root = Path("artifacts") / f"smooth_tail_failure_postmortem_{datetime.now():%Y%m%d-%H%M%S}"
    out_root.mkdir(parents=True, exist_ok=True)
    rows = write_target_mask_csv(out_root)
    write_solver_review(out_root)
    artifact_review = failed_artifact_review(out_root)
    save_failed_focal_with_contours(out_root)
    save_failed_profiles(out_root)
    save_mask_comparison(out_root)
    save_power_distribution(out_root, rows)
    save_focal_comparison(out_root)
    save_center_profile_comparison(out_root)
    write_postmortem_summary(out_root, rows, artifact_review)
    print(f"saved postmortem: {out_root}")


if __name__ == "__main__":
    main()
