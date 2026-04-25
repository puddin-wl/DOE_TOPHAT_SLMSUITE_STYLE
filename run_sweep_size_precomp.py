from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

from run_one import run_variant
from src.artifacts import timestamped_root, variant_dir
from src.config import DOEConfig, update_config


TARGET_SIZE_50_X_UM = [326.0, 328.0, 330.0]
TARGET_SIZE_50_Y_UM = [116.0, 118.0, 120.0]

SUMMARY_COLUMNS = [
    "variant",
    "target_size_50_x_um",
    "target_size_50_y_um",
    "output_size_50_x_um",
    "output_size_50_y_um",
    "output_transition_width_13_90_x_um",
    "output_transition_width_13_90_y_um",
    "efficiency_13p5",
    "rms_90",
    "center_profile_std_x",
    "center_profile_std_y",
    "outside_max_x_rel_to_core",
    "outside_max_y_rel_to_core",
    "outside_max_distance_x_um",
    "outside_max_distance_y_um",
    "strongest_side_lobe_peak_x_left_rel_to_core",
    "strongest_side_lobe_peak_x_right_rel_to_core",
    "strongest_side_lobe_peak_y_left_rel_to_core",
    "strongest_side_lobe_peak_y_right_rel_to_core",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a small 3x3 industrial_logistic size precomp sweep.")
    parser.add_argument("--n", type=int, default=2048)
    parser.add_argument("--focus-sampling-um", type=float, default=2.5)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out-root", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.out_root) if args.out_root else timestamped_root("artifacts/size_precomp")
    root.mkdir(parents=True, exist_ok=True)

    rows = []
    for size_x in TARGET_SIZE_50_X_UM:
        for size_y in TARGET_SIZE_50_Y_UM:
            variant = f"wgs_size50_x{size_x:.0f}_y{size_y:.0f}"
            print(f"running {variant} ...", flush=True)
            config = update_config(
                DOEConfig(),
                n=args.n,
                focus_sampling_um=args.focus_sampling_um,
                iterations=args.iterations,
                seed=args.seed,
                method="wgs",
                target="industrial_logistic",
                phase_init="quadratic",
                target_width_um=size_x,
                target_height_um=size_y,
                transition_width_13_90_x_um=12.0,
                transition_width_13_90_y_um=16.0,
                mraf_factor=0.5,
            )
            summary = run_variant(config, variant_dir(root, variant))
            metrics = summary["metrics"]
            row = {
                "variant": variant,
                "target_size_50_x_um": size_x,
                "target_size_50_y_um": size_y,
                "output_size_50_x_um": metrics["output_size_50_x_um"],
                "output_size_50_y_um": metrics["output_size_50_y_um"],
                "output_transition_width_13_90_x_um": metrics["output_transition_width_13_90_x_um"],
                "output_transition_width_13_90_y_um": metrics["output_transition_width_13_90_y_um"],
                "efficiency_13p5": metrics["efficiency_13p5"],
                "rms_90": metrics["rms_90"],
                "center_profile_std_x": metrics["center_profile_std_x"],
                "center_profile_std_y": metrics["center_profile_std_y"],
                "outside_max_x_rel_to_core": metrics["outside_max_x_rel_to_core"],
                "outside_max_y_rel_to_core": metrics["outside_max_y_rel_to_core"],
                "outside_max_distance_x_um": metrics["outside_max_distance_x_um"],
                "outside_max_distance_y_um": metrics["outside_max_distance_y_um"],
                "strongest_side_lobe_peak_x_left_rel_to_core": metrics[
                    "strongest_side_lobe_peak_x_left_rel_to_core"
                ],
                "strongest_side_lobe_peak_x_right_rel_to_core": metrics[
                    "strongest_side_lobe_peak_x_right_rel_to_core"
                ],
                "strongest_side_lobe_peak_y_left_rel_to_core": metrics[
                    "strongest_side_lobe_peak_y_left_rel_to_core"
                ],
                "strongest_side_lobe_peak_y_right_rel_to_core": metrics[
                    "strongest_side_lobe_peak_y_right_rel_to_core"
                ],
            }
            rows.append(row)
            print(
                "  "
                f"out50={row['output_size_50_x_um']:.3f}x{row['output_size_50_y_um']:.3f} um, "
                f"tw={row['output_transition_width_13_90_x_um']:.3f}x{row['output_transition_width_13_90_y_um']:.3f} um, "
                f"rms90={row['rms_90']:.6g}, "
                f"eff13={row['efficiency_13p5']:.6g}",
                flush=True,
            )

    summary_path = root / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    ranked = sorted(rows, key=_ranking_key)
    print(f"saved sweep root: {root}")
    print(f"saved summary: {summary_path}")
    print("ranked by |size50-330x120|, rms_90, profile std sum:")
    for row in ranked:
        print(
            f"  {row['variant']}: "
            f"out50={row['output_size_50_x_um']:.3f}x{row['output_size_50_y_um']:.3f}, "
            f"rms90={row['rms_90']:.6g}, "
            f"std={row['center_profile_std_x'] + row['center_profile_std_y']:.6g}, "
            f"outside_max={row['outside_max_x_rel_to_core']:.3g}/{row['outside_max_y_rel_to_core']:.3g}"
        )


def _finite_or_penalty(value: float, penalty: float = 1e9) -> float:
    return float(value) if math.isfinite(float(value)) else penalty


def _ranking_key(row: dict) -> tuple[float, float, float]:
    size_error = abs(_finite_or_penalty(row["output_size_50_x_um"]) - 330.0) + abs(
        _finite_or_penalty(row["output_size_50_y_um"]) - 120.0
    )
    flatness = _finite_or_penalty(row["center_profile_std_x"]) + _finite_or_penalty(
        row["center_profile_std_y"]
    )
    return (size_error, _finite_or_penalty(row["rms_90"]), flatness)


if __name__ == "__main__":
    main()
