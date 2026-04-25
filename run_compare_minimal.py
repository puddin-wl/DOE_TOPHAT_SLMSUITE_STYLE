from __future__ import annotations

import argparse
from pathlib import Path

from src.artifacts import timestamped_root, variant_dir, write_json
from src.config import DOEConfig, update_config
from run_one import run_variant


VARIANTS = [
    ("gs_hard_random", {"method": "gs", "target": "hard", "phase_init": "random"}),
    ("mraf_hard_random", {"method": "mraf", "target": "hard", "phase_init": "random"}),
    ("mraf_soft_quadratic", {"method": "mraf", "target": "soft", "phase_init": "quadratic"}),
    ("mraf_rounded_rtad_quadratic", {"method": "mraf", "target": "rounded_rtad", "phase_init": "quadratic"}),
    (
        "wgs_rounded_rtad_quadratic",
        {"method": "wgs-leonardo", "target": "rounded_rtad", "phase_init": "quadratic"},
    ),
    ("wgs_mraf_soft_quadratic", {"method": "wgs-leonardo", "target": "soft", "phase_init": "quadratic"}),
    (
        "mraf_soft_astigmatic_quadratic",
        {"method": "mraf", "target": "soft", "phase_init": "astigmatic_quadratic"},
    ),
    (
        "wgs_mraf_soft_astigmatic_quadratic",
        {"method": "wgs-leonardo", "target": "soft", "phase_init": "astigmatic_quadratic"},
    ),
    ("mraf_soft_conical_like", {"method": "mraf", "target": "soft", "phase_init": "conical_like"}),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the minimal DOE comparison set.")
    parser.add_argument("--n", type=int, default=2048)
    parser.add_argument("--focus-sampling-um", type=float, default=2.5)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--mraf-factor", type=float, default=None)
    parser.add_argument("--target-power-fraction", type=float, default=None)
    parser.add_argument("--feedback-exponent", type=float, default=None)
    parser.add_argument("--free-region-width-x-um", type=float, default=None)
    parser.add_argument("--free-region-width-y-um", type=float, default=None)
    parser.add_argument("--rtad-only", action="store_true")
    parser.add_argument("--min-efficiency", type=float, default=0.05)
    parser.add_argument("--min-size50-fraction", type=float, default=0.7)
    parser.add_argument("--max-size50-fraction", type=float, default=1.5)
    parser.add_argument("--soft-only", action="store_true")
    parser.add_argument("--out-root", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.out_root) if args.out_root else timestamped_root()
    summaries = []

    variants = [
        item
        for item in VARIANTS
        if (not args.soft_only or item[1]["target"] == "soft")
        and (not args.rtad_only or item[1]["target"] == "rounded_rtad")
    ]
    for name, overrides in variants:
        print(f"running {name} ...", flush=True)
        config = update_config(
            DOEConfig(),
            n=args.n,
            focus_sampling_um=args.focus_sampling_um,
            iterations=args.iterations,
            seed=args.seed,
            mraf_factor=args.mraf_factor,
            target_power_fraction=args.target_power_fraction,
            feedback_exponent=args.feedback_exponent,
            free_region_width_x_um=args.free_region_width_x_um,
            free_region_width_y_um=args.free_region_width_y_um,
            **overrides,
        )
        summary = run_variant(config, variant_dir(root, name))
        metrics = summary["metrics"]
        valid = (
            metrics["efficiency_in_roi"] >= args.min_efficiency
            and args.min_size50_fraction * config.target_eval_width_um
            <= metrics["size_50_x"]
            <= args.max_size50_fraction * config.target_eval_width_um
            and args.min_size50_fraction * config.target_eval_height_um
            <= metrics["size_50_y"]
            <= args.max_size50_fraction * config.target_eval_height_um
        )
        summaries.append({"name": name, **metrics, "valid_candidate": valid, "out_dir": summary["out_dir"]})
        print(
            f"  rms={summary['metrics']['rms_in_roi']:.6g}, "
            f"eff={summary['metrics']['efficiency_in_roi']:.6g}, "
            f"size50={summary['metrics']['size_50_x']:.6g}x{summary['metrics']['size_50_y']:.6g}, "
            f"std_x={summary['metrics']['center_profile_std_x']:.6g}, "
            f"std_y={summary['metrics']['center_profile_std_y']:.6g}, "
            f"valid={valid}",
            flush=True,
        )

    valid_summaries = [item for item in summaries if item["valid_candidate"]]
    best_pool = valid_summaries if valid_summaries else summaries
    best = min(best_pool, key=lambda item: item["center_profile_flatness_score"])
    write_json(
        root / "compare_summary.json",
        {
            "variants": summaries,
            "selection_rules": {
                "min_efficiency": args.min_efficiency,
                "min_size50_fraction": args.min_size50_fraction,
                "max_size50_fraction": args.max_size50_fraction,
            },
            "best_valid_by_profile_std_sum": best,
            "valid_candidates_found": bool(valid_summaries),
        },
    )
    print(f"saved comparison root: {root}")
    print(
        "best_valid_by_profile_std_sum: "
        f"{best['name']} "
        f"(std_x={best['center_profile_std_x']:.6g}, "
        f"std_y={best['center_profile_std_y']:.6g}, "
        f"eff={best['efficiency_in_roi']:.6g}, "
        f"size50={best['size_50_x']:.6g}x{best['size_50_y']:.6g}, "
        f"score={best['center_profile_flatness_score']:.6g})"
    )


if __name__ == "__main__":
    main()
