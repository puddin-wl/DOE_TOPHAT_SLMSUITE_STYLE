from __future__ import annotations

import argparse
import csv
from pathlib import Path

from run_one import run_variant
from src.artifacts import timestamped_root, variant_dir
from src.config import DOEConfig, update_config


WIDTHS_UM = [20.0, 40.0, 60.0]

SUMMARY_COLUMNS = [
    "variant",
    "descending_edge_width_um",
    "output_size_50_x_um",
    "output_size_50_y_um",
    "output_transition_width_13_90_x_um",
    "output_transition_width_13_90_y_um",
    "rms_90",
    "center_profile_std_x",
    "center_profile_std_y",
    "outside_max_x_rel_to_core",
    "outside_max_y_rel_to_core",
    "strongest_side_lobe_peak_x_left_rel_to_core",
    "strongest_side_lobe_peak_x_right_rel_to_core",
    "strongest_side_lobe_peak_y_left_rel_to_core",
    "strongest_side_lobe_peak_y_right_rel_to_core",
    "first_side_lobe_peak_x_left_rel_to_core",
    "first_side_lobe_peak_x_right_rel_to_core",
    "first_side_lobe_peak_y_left_rel_to_core",
    "first_side_lobe_peak_y_right_rel_to_core",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run three small descending-edge RTAD-style tests.")
    parser.add_argument("--n", type=int, default=2048)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out-root", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.out_root) if args.out_root else timestamped_root("artifacts/descending_edge")
    root.mkdir(parents=True, exist_ok=True)
    rows = []

    for width_um in WIDTHS_UM:
        variant = f"desc_edge_w{width_um:.0f}"
        print(f"running {variant} ...", flush=True)
        config = update_config(
            DOEConfig(),
            n=args.n,
            iterations=args.iterations,
            seed=args.seed,
            method="wgs",
            target="industrial_logistic",
            phase_init="quadratic",
            target_width_um=330.0,
            target_height_um=116.0,
            transition_width_13_90_x_um=12.0,
            transition_width_13_90_y_um=16.0,
            mraf_factor=0.4,
            feedback_exponent=2.0,
            descending_edge_mode="raised_cosine",
            descending_edge_width_um=width_um,
            descending_edge_end_intensity=0.03,
        )
        summary = run_variant(config, variant_dir(root, variant))
        metrics = summary["metrics"]
        row = {"variant": variant, "descending_edge_width_um": width_um}
        row.update({key: metrics[key] for key in SUMMARY_COLUMNS if key not in row and key in metrics})
        rows.append(row)
        print(
            f"  out50={row['output_size_50_x_um']:.3f}x{row['output_size_50_y_um']:.3f}, "
            f"rms90={row['rms_90']:.6g}, "
            f"outside={row['outside_max_x_rel_to_core']:.3g}/{row['outside_max_y_rel_to_core']:.3g}, "
            f"strongest_xR/yR={row['strongest_side_lobe_peak_x_right_rel_to_core']:.3g}/"
            f"{row['strongest_side_lobe_peak_y_right_rel_to_core']:.3g}",
            flush=True,
        )

    summary_path = root / "summary_descending_edge.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"saved summary: {summary_path}")


if __name__ == "__main__":
    main()
