from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

from run_one import run_variant
from src.artifacts import variant_dir
from src.config import DOEConfig, update_config


MRAF_FACTORS = [0.35, 0.375, 0.40, 0.425, 0.45]

SUMMARY_COLUMNS = [
    "variant",
    "mraf_factor",
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
    "first_derivative_side_lobe_x_rel_to_core",
    "first_derivative_side_lobe_y_rel_to_core",
    "strongest_derivative_side_lobe_x_rel_to_core",
    "strongest_derivative_side_lobe_y_rel_to_core",
    "derivative_side_lobe_detection_count",
    "out_dir",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a small MRAF factor fine sweep.")
    parser.add_argument("--n", type=int, default=2048)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out-root", default=None)
    return parser.parse_args()


def finite_values(values: list[float]) -> list[float]:
    return [float(value) for value in values if math.isfinite(float(value))]


def finite_min(values: list[float]) -> float:
    finite = finite_values(values)
    return min(finite) if finite else float("nan")


def finite_max(values: list[float]) -> float:
    finite = finite_values(values)
    return max(finite) if finite else float("nan")


def derivative_detection_count(metrics: dict) -> int:
    keys = [
        "strongest_side_lobe_peak_x_left_rel_to_core",
        "strongest_side_lobe_peak_x_right_rel_to_core",
        "strongest_side_lobe_peak_y_left_rel_to_core",
        "strongest_side_lobe_peak_y_right_rel_to_core",
    ]
    return sum(math.isfinite(float(metrics[key])) for key in keys)


def first_derivative_peak(metrics: dict, axis: str) -> float:
    return finite_max(
        [
            metrics[f"first_side_lobe_peak_{axis}_left_rel_to_core"],
            metrics[f"first_side_lobe_peak_{axis}_right_rel_to_core"],
        ]
    )


def strongest_derivative_peak(metrics: dict, axis: str) -> float:
    return finite_max(
        [
            metrics[f"strongest_side_lobe_peak_{axis}_left_rel_to_core"],
            metrics[f"strongest_side_lobe_peak_{axis}_right_rel_to_core"],
        ]
    )


def row_from_summary(variant: str, mraf_factor: float, summary: dict) -> dict:
    metrics = summary["metrics"]
    return {
        "variant": variant,
        "mraf_factor": mraf_factor,
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
        "first_derivative_side_lobe_x_rel_to_core": first_derivative_peak(metrics, "x"),
        "first_derivative_side_lobe_y_rel_to_core": first_derivative_peak(metrics, "y"),
        "strongest_derivative_side_lobe_x_rel_to_core": strongest_derivative_peak(metrics, "x"),
        "strongest_derivative_side_lobe_y_rel_to_core": strongest_derivative_peak(metrics, "y"),
        "derivative_side_lobe_detection_count": derivative_detection_count(metrics),
        "out_dir": summary["out_dir"],
    }


def write_summary(root: Path, rows: list[dict]) -> None:
    with (root / "summary_mraf_fine.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def make_montage(root: Path, rows: list[dict], source_name: str, output_name: str) -> None:
    thumbs = []
    for row in rows:
        image_path = Path(row["out_dir"]) / source_name
        image = Image.open(image_path).convert("RGB")
        image.thumbnail((760, 520))
        canvas = Image.new("RGB", (760, 570), "white")
        draw = ImageDraw.Draw(canvas)
        label = (
            f"mraf={row['mraf_factor']}: "
            f"out50={row['output_size_50_x_um']:.1f}x{row['output_size_50_y_um']:.1f}, "
            f"rms90={row['rms_90']:.4g}"
        )
        draw.text((10, 8), label, fill=(0, 0, 0))
        canvas.paste(image, (0, 35))
        thumbs.append(canvas)

    cols = 2
    rows_count = math.ceil(len(thumbs) / cols)
    montage = Image.new("RGB", (cols * 760, rows_count * 570), "white")
    for index, thumb in enumerate(thumbs):
        montage.paste(thumb, ((index % cols) * 760, (index // cols) * 570))
    montage.save(root / output_name)


def selection_key_size(row: dict) -> tuple[float, float]:
    x = row["output_size_50_x_um"]
    y = row["output_size_50_y_um"]
    if not (math.isfinite(float(x)) and math.isfinite(float(y))):
        return (1e9, 1e9)
    return (abs(float(x) - 330.0) + abs(float(y) - 120.0), float(row["rms_90"]))


def selection_key_lobe(row: dict) -> tuple[int, float, float]:
    strongest = finite_max(
        [
            row["strongest_derivative_side_lobe_x_rel_to_core"],
            row["strongest_derivative_side_lobe_y_rel_to_core"],
        ]
    )
    if not math.isfinite(strongest):
        strongest = 0.0
    outside = max(float(row["outside_max_x_rel_to_core"]), float(row["outside_max_y_rel_to_core"]))
    return (int(row["derivative_side_lobe_detection_count"]), strongest, outside)


def main() -> None:
    args = parse_args()
    root = Path(args.out_root) if args.out_root else Path("artifacts") / f"mraf_fine_{datetime.now():%Y%m%d-%H%M%S}"
    root.mkdir(parents=True, exist_ok=True)
    rows = []

    for mraf_factor in MRAF_FACTORS:
        variant = f"mraf_{mraf_factor:.3f}".replace(".", "p")
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
            feedback_exponent=2.0,
            mraf_factor=mraf_factor,
            descending_edge_mode="none",
        )
        summary = run_variant(config, variant_dir(root, variant))
        row = row_from_summary(variant, mraf_factor, summary)
        rows.append(row)
        print(
            f"  out50={row['output_size_50_x_um']:.3f}x{row['output_size_50_y_um']:.3f}, "
            f"rms90={row['rms_90']:.6g}, "
            f"outside={row['outside_max_x_rel_to_core']:.3g}/{row['outside_max_y_rel_to_core']:.3g}, "
            f"deriv={row['strongest_derivative_side_lobe_x_rel_to_core']:.3g}/"
            f"{row['strongest_derivative_side_lobe_y_rel_to_core']:.3g}, "
            f"count={row['derivative_side_lobe_detection_count']}",
            flush=True,
        )

    write_summary(root, rows)
    make_montage(root, rows, "edge_spike_diagnostic.png", "edge_spike_mraf_fine_montage.png")
    make_montage(root, rows, "center_profiles_raw_norm.png", "center_profile_mraf_fine_montage.png")
    make_montage(root, rows, "edge_spike_diagnostic.png", "derivative_lobe_mraf_fine_montage.png")

    closest_size = min(rows, key=selection_key_size)
    lowest_rms = min(rows, key=lambda row: float(row["rms_90"]))
    lowest_lobe = min(rows, key=selection_key_lobe)
    print(f"saved: {root}")
    print(f"closest_size: {closest_size['variant']}")
    print(f"lowest_rms_90: {lowest_rms['variant']}")
    print(f"lowest_derivative_lobe: {lowest_lobe['variant']}")


if __name__ == "__main__":
    main()
