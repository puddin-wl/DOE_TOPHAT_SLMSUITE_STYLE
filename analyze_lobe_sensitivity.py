from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

from src.config import DOEConfig, update_config
from src.grids import make_grid
from src.metrics import _reference_intensity, side_lobe_analysis_for_profile, target_intensity
from src.targets import make_target


CASES = [
    (
        "base_size_precomp_x330_y116",
        Path("artifacts/size_precomp/20260425-231857/wgs_size50_x330_y116"),
    ),
    ("feedback_exp_08", Path("artifacts/single_knob_20260426-0000/feedback_exp_08")),
    ("mraf_04", Path("artifacts/single_knob_20260426-0000/mraf_04")),
    ("mraf_06", Path("artifacts/single_knob_20260426-0000/mraf_06")),
]

SMOOTHING_SIGMA_UM = [2.5, 5.0, 7.5]
PROMINENCE_THRESHOLDS = [0.01, 0.02, 0.03]
CROSSING_MARGINS_UM = [2.5, 5.0]

SUMMARY_COLUMNS = [
    "case",
    "smoothing_sigma_um",
    "prominence_threshold",
    "crossing_margin_um",
    "outside_max_x_left_rel_to_core",
    "outside_max_x_right_rel_to_core",
    "outside_max_y_left_rel_to_core",
    "outside_max_y_right_rel_to_core",
    "outside_max_x_rel_to_core",
    "outside_max_y_rel_to_core",
    "first_side_lobe_peak_x_left_rel_to_core",
    "first_side_lobe_peak_x_right_rel_to_core",
    "first_side_lobe_peak_y_left_rel_to_core",
    "first_side_lobe_peak_y_right_rel_to_core",
    "strongest_side_lobe_peak_x_left_rel_to_core",
    "strongest_side_lobe_peak_x_right_rel_to_core",
    "strongest_side_lobe_peak_y_left_rel_to_core",
    "strongest_side_lobe_peak_y_right_rel_to_core",
    "first_side_lobe_distance_x_left_um",
    "first_side_lobe_distance_x_right_um",
    "first_side_lobe_distance_y_left_um",
    "first_side_lobe_distance_y_right_um",
    "strongest_side_lobe_distance_x_left_um",
    "strongest_side_lobe_distance_x_right_um",
    "strongest_side_lobe_distance_y_left_um",
    "strongest_side_lobe_distance_y_right_um",
    "detected_derivative_lobes_count",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Re-analyze derivative side-lobe sensitivity from existing artifacts.")
    parser.add_argument("--out-root", default="artifacts/lobe_sensitivity_20260426")
    return parser.parse_args()


def config_from_json(path: Path) -> DOEConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    fields = DOEConfig.__dataclass_fields__.keys()
    kwargs = {key: payload[key] for key in fields if key in payload}
    return update_config(DOEConfig(), **kwargs)


def finite_or_nan(value: float) -> float:
    return float(value) if math.isfinite(float(value)) else float("nan")


def stronger_peak(left: dict, right: dict) -> float:
    peaks = [left["peak_rel"], right["peak_rel"]]
    finite = [float(value) for value in peaks if math.isfinite(float(value))]
    return max(finite) if finite else float("nan")


def add_lobe_fields(row: dict, axis: str, analysis: dict) -> None:
    left = analysis["derivative_left"]
    right = analysis["derivative_right"]
    outside_left = analysis["outside_max_left"]
    outside_right = analysis["outside_max_right"]
    row[f"outside_max_{axis}_left_rel_to_core"] = outside_left["peak_rel"]
    row[f"outside_max_{axis}_right_rel_to_core"] = outside_right["peak_rel"]
    row[f"outside_max_{axis}_rel_to_core"] = stronger_peak(outside_left, outside_right)
    for kind in ("first", "strongest"):
        row[f"{kind}_side_lobe_peak_{axis}_left_rel_to_core"] = left[kind]["peak_rel"]
        row[f"{kind}_side_lobe_peak_{axis}_right_rel_to_core"] = right[kind]["peak_rel"]
        row[f"{kind}_side_lobe_distance_{axis}_left_um"] = left[kind]["distance_um"]
        row[f"{kind}_side_lobe_distance_{axis}_right_um"] = right[kind]["distance_um"]


def count_detected(row: dict) -> int:
    keys = [
        "strongest_side_lobe_peak_x_left_rel_to_core",
        "strongest_side_lobe_peak_x_right_rel_to_core",
        "strongest_side_lobe_peak_y_left_rel_to_core",
        "strongest_side_lobe_peak_y_right_rel_to_core",
    ]
    return sum(math.isfinite(float(row[key])) for key in keys)


def analyze_case(case_name: str, artifact_dir: Path) -> list[dict]:
    config = config_from_json(artifact_dir / "config.json")
    grid = make_grid(config)
    target = make_target(config, grid)
    intensity = np.load(artifact_dir / "focal_intensity.npy")
    reference, _ = _reference_intensity(config, target, intensity)
    norm_intensity = intensity / reference if reference > 0 else np.zeros_like(intensity)
    center = grid.n // 2
    x_profile = norm_intensity[center, :]
    y_profile = norm_intensity[:, center]

    rows = []
    for sigma_um in SMOOTHING_SIGMA_UM:
        for prominence in PROMINENCE_THRESHOLDS:
            for margin_um in CROSSING_MARGINS_UM:
                x_analysis = side_lobe_analysis_for_profile(
                    grid.x_um_focus,
                    x_profile,
                    config.free_region_threshold_intensity,
                    config.side_lobe_search_width_um,
                    sigma_um,
                    margin_um,
                    prominence,
                )
                y_analysis = side_lobe_analysis_for_profile(
                    grid.y_um_focus,
                    y_profile,
                    config.free_region_threshold_intensity,
                    config.side_lobe_search_width_um,
                    sigma_um,
                    margin_um,
                    prominence,
                )
                row = {
                    "case": case_name,
                    "smoothing_sigma_um": sigma_um,
                    "prominence_threshold": prominence,
                    "crossing_margin_um": margin_um,
                }
                add_lobe_fields(row, "x", x_analysis)
                add_lobe_fields(row, "y", y_analysis)
                row["detected_derivative_lobes_count"] = count_detected(row)
                rows.append(row)
    return rows


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for case_name, artifact_dir in CASES:
        if not artifact_dir.exists():
            raise FileNotFoundError(artifact_dir)
        rows.extend(analyze_case(case_name, artifact_dir))

    summary_path = out_root / "summary_lobe_sensitivity.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"saved: {summary_path}")
    for case_name, _ in CASES:
        case_rows = [row for row in rows if row["case"] == case_name]
        counts = [row["detected_derivative_lobes_count"] for row in case_rows]
        print(f"{case_name}: detected counts min/max = {min(counts)} / {max(counts)}")


if __name__ == "__main__":
    main()
