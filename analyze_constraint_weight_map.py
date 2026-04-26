from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from src.artifacts import write_json
from src.config import DOEConfig, update_config
from src.grids import make_grid
from src.metrics import target_intensity
from src.targets import TargetResult, make_target


TARGETS = (
    "industrial_logistic",
    "industrial_rounded_logistic_smooth_tail",
    "industrial_rounded_logistic_weak_tail",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose target constraint weight maps without solve_phase.")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--out-root", default=None)
    return parser.parse_args()


def base_config() -> DOEConfig:
    return update_config(
        DOEConfig(),
        n=2048,
        target_width_um=330.0,
        target_height_um=116.0,
        transition_width_13_90_x_um=12.0,
        transition_width_13_90_y_um=16.0,
        controlled_tail_end_intensity=0.03,
        controlled_tail_width_x_um=24.0,
        controlled_tail_width_y_um=16.0,
        core_constraint_weight=1.0,
        transition_constraint_weight=0.7,
        tail_constraint_weight=0.1,
    )


def build_targets():
    config = base_config()
    grid = make_grid(config)
    built = []
    for target_type in TARGETS:
        target_config = update_config(config, target=target_type)
        built.append((target_type, target_config, make_target(target_config, grid), grid))
    return built


def masks(target: TargetResult, intensity: np.ndarray, threshold: float = 0.135):
    finite = target.finite_mask
    tail = finite & (intensity < threshold)
    core = finite & (intensity >= 0.9)
    transition = finite & (intensity >= threshold) & (intensity < 0.9)
    free = ~finite
    return finite, core, transition, tail, free


def default_weight(target: TargetResult) -> np.ndarray:
    if target.constraint_weight is not None:
        return target.constraint_weight
    return np.where(target.finite_mask, 1.0, 0.0)


def row_for(target_type: str, target: TargetResult, grid) -> dict:
    intensity = target_intensity(target)
    finite, core, transition, tail, free = masks(target, intensity)
    weight = default_weight(target)
    pixel_area = grid.focus_sampling_um**2
    total_sum = float(np.nansum(intensity[finite]))
    tail_sum = float(np.nansum(intensity[tail]))

    def mean_or_nan(mask):
        return float(np.mean(weight[mask])) if np.any(mask) else float("nan")

    return {
        "target_type": target_type,
        "finite_pixel_count": int(np.count_nonzero(finite)),
        "core_pixel_count": int(np.count_nonzero(core)),
        "transition_pixel_count": int(np.count_nonzero(transition)),
        "tail_pixel_count": int(np.count_nonzero(tail)),
        "free_pixel_count": int(np.count_nonzero(free)),
        "finite_area_um2": float(np.count_nonzero(finite) * pixel_area),
        "core_area_um2": float(np.count_nonzero(core) * pixel_area),
        "transition_area_um2": float(np.count_nonzero(transition) * pixel_area),
        "tail_area_um2": float(np.count_nonzero(tail) * pixel_area),
        "total_target_intensity_sum": total_sum,
        "core_target_intensity_sum": float(np.nansum(intensity[core])),
        "transition_target_intensity_sum": float(np.nansum(intensity[transition])),
        "tail_target_intensity_sum": tail_sum,
        "tail_power_fraction": tail_sum / total_sum if total_sum > 0 else float("nan"),
        "mean_constraint_weight": mean_or_nan(finite),
        "core_mean_weight": mean_or_nan(core),
        "transition_mean_weight": mean_or_nan(transition),
        "tail_mean_weight": mean_or_nan(tail),
        "min_weight": float(np.min(weight)),
        "max_weight": float(np.max(weight)),
    }


def run_checks() -> None:
    built = build_targets()
    target_map = {target_type: target for target_type, _, target, _ in built}
    logistic = target_map["industrial_logistic"]
    weak = target_map["industrial_rounded_logistic_weak_tail"]
    weak_i = target_intensity(weak)
    finite, core, transition, tail, free = masks(weak, weak_i)
    weight = weak.constraint_weight
    assert logistic.constraint_weight is None, "industrial_logistic should not create constraint_weight"
    assert weak.constraint_weight is not None, "weak-tail target must create constraint_weight"
    assert weight.shape == weak.amplitude.shape, "constraint_weight shape mismatch"
    assert np.nanmin(weight) >= 0.0 and np.nanmax(weight) <= 1.0, "weights must be in [0,1]"
    assert np.all(weight[free] == 0.0), "free/noise weights must be 0"
    assert np.mean(weight[tail]) < np.mean(weight[core]), "tail weight must be lower than core weight"
    finite_amp = weak.amplitude[np.isfinite(weak.amplitude)]
    assert finite_amp.size > 0 and np.nanmin(finite_amp) >= 0.0, "finite amplitude must be nonnegative"
    assert not np.isinf(finite_amp).any(), "finite amplitude must not contain Inf"
    assert np.array_equal(np.isnan(weak.amplitude), weak.noise_mask), "NaN should only appear in free/noise region"
    print("constraint weight checks passed")


def save_weight_map(out_root: Path, target: TargetResult, grid) -> None:
    weight = default_weight(target)
    crop = np.abs(grid.x_um_focus) <= 260
    data = weight[np.ix_(crop, crop)]
    x = grid.x_um_focus[crop]
    fig, ax = plt.subplots(figsize=(6.2, 5.4), dpi=160)
    im = ax.imshow(data, extent=[float(x[0]), float(x[-1]), float(x[0]), float(x[-1])], origin="lower", cmap="viridis", vmin=0, vmax=1)
    ax.set_title("weak-tail constraint weight map")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="constraint weight")
    fig.tight_layout()
    fig.savefig(out_root / "constraint_weight_map_weak_tail.png")
    plt.close(fig)


def save_intensity_comparison(out_root: Path, built) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), dpi=160)
    for ax, (target_type, _, target, grid) in zip(axes, built):
        intensity = target_intensity(target)
        crop = np.abs(grid.x_um_focus) <= 260
        data = np.ma.masked_invalid(intensity[np.ix_(crop, crop)])
        x = grid.x_um_focus[crop]
        im = ax.imshow(data, extent=[float(x[0]), float(x[-1]), float(x[0]), float(x[-1])], origin="lower", cmap="magma", vmin=0, vmax=1)
        ax.set_title(target_type)
        ax.set_xlabel("x (um)")
        ax.set_ylabel("y (um)")
    fig.suptitle("target intensity: logistic vs smooth-tail vs weak-tail")
    fig.tight_layout()
    fig.savefig(out_root / "target_intensity_logistic_vs_smooth_vs_weak_tail.png")
    plt.close(fig)


def save_weighted_regions(out_root: Path, target: TargetResult, grid) -> None:
    intensity = target_intensity(target)
    finite, core, transition, tail, free = masks(target, intensity)
    region = np.zeros_like(intensity)
    region[tail] = 1
    region[transition] = 2
    region[core] = 3
    region[free] = 4
    crop = np.abs(grid.x_um_focus) <= 260
    data = region[np.ix_(crop, crop)]
    x = grid.x_um_focus[crop]
    fig, ax = plt.subplots(figsize=(6.2, 5.4), dpi=160)
    im = ax.imshow(data, extent=[float(x[0]), float(x[-1]), float(x[0]), float(x[-1])], origin="lower", cmap="tab10", vmin=0, vmax=4)
    ax.set_title("weak-tail weighted regions\n1 tail, 2 transition, 3 core, 4 free")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(out_root / "target_weighted_regions_weak_tail.png")
    plt.close(fig)


def save_profiles(out_root: Path, target: TargetResult, grid) -> None:
    intensity = target_intensity(target)
    weight = default_weight(target)
    center = grid.n // 2
    for axis, coord, profile_i, profile_w in (
        ("x", grid.x_um_focus, intensity[center, :], weight[center, :]),
        ("y", grid.y_um_focus, intensity[:, center], weight[:, center]),
    ):
        view = np.abs(coord) <= (260 if axis == "x" else 170)
        fig, ax1 = plt.subplots(figsize=(8.6, 4.8), dpi=160)
        ax1.plot(coord[view], profile_i[view], label="target intensity", color="tab:blue")
        for level, color in ((0.9, "tab:green"), (0.5, "tab:red"), (0.135, "tab:purple"), (0.03, "tab:cyan")):
            ax1.axhline(level, color=color, lw=0.8, alpha=0.45)
        ax1.set_xlabel(f"{axis} (um)")
        ax1.set_ylabel("target intensity")
        ax2 = ax1.twinx()
        ax2.plot(coord[view], profile_w[view], label="constraint weight", color="tab:orange", ls="--")
        ax2.set_ylabel("constraint weight")
        ax2.set_ylim(-0.05, 1.05)
        ax1.grid(alpha=0.25)
        lines = ax1.get_lines() + ax2.get_lines()
        ax1.legend(lines, [line.get_label() for line in lines], frameon=False, fontsize=8)
        ax1.set_title(f"weak-tail {axis} profile: intensity and constraint weight")
        fig.tight_layout()
        fig.savefig(out_root / f"{axis}_profile_intensity_and_weight.png")
        plt.close(fig)


def write_csv(out_root: Path, rows: list[dict]) -> None:
    path = out_root / "target_mask_weight_comparison.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_summary(out_root: Path, weak_row: dict) -> None:
    summary = {
        "weak_tail_core_weight": 1.0,
        "weak_tail_transition_weight": 0.7,
        "weak_tail_tail_weight": 0.1,
        "weak_tail_free_weight": 0.0,
        "tail_weight_fraction_of_core": 0.1,
        "whether_old_targets_are_backward_compatible": "yes: old targets return constraint_weight=None and the solver keeps the old path when no weight map is supplied",
        "whether_frozen_best_behavior_should_change": "no: industrial_logistic returns constraint_weight=None, so frozen best should use the exact legacy solver behavior",
        "weak_tail_finite_pixel_count": weak_row["finite_pixel_count"],
        "weak_tail_tail_pixel_count": weak_row["tail_pixel_count"],
        "weak_tail_mean_constraint_weight": weak_row["mean_constraint_weight"],
        "recommended_next_step": "Do not run sweep yet. If code review confirms old targets are unchanged, next step is one single-case validation of industrial_rounded_logistic_weak_tail.",
    }
    write_json(out_root / "constraint_weight_summary.json", summary)


def main() -> None:
    args = parse_args()
    if args.check_only:
        run_checks()
        return

    out_root = Path(args.out_root) if args.out_root else Path("artifacts") / f"constraint_weight_map_diagnostics_{datetime.now():%Y%m%d-%H%M%S}"
    out_root.mkdir(parents=True, exist_ok=True)
    built = build_targets()
    rows = [row_for(target_type, target, grid) for target_type, _, target, grid in built]
    weak_target = next(target for target_type, _, target, _ in built if target_type == "industrial_rounded_logistic_weak_tail")
    weak_grid = next(grid for target_type, _, _, grid in built if target_type == "industrial_rounded_logistic_weak_tail")
    weak_row = next(row for row in rows if row["target_type"] == "industrial_rounded_logistic_weak_tail")

    write_csv(out_root, rows)
    write_summary(out_root, weak_row)
    save_weight_map(out_root, weak_target, weak_grid)
    save_intensity_comparison(out_root, built)
    save_weighted_regions(out_root, weak_target, weak_grid)
    save_profiles(out_root, weak_target, weak_grid)
    print(f"saved constraint weight diagnostics: {out_root}")


if __name__ == "__main__":
    main()
