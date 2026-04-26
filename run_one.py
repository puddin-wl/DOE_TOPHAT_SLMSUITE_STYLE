from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from src.artifacts import save_arrays, timestamped_root, variant_dir, write_json
from src.config import DOEConfig, update_config
from src.grids import gaussian_aperture_amplitude, lens_pupil_mask, load_bgdata_summary, make_grid
from src.metrics import compute_metrics
from src.mraf import solve_phase
from src.phase_init import initial_phase
from src.plotting import save_all_plots
from src.propagation import Propagator
from src.targets import make_target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one continuous-phase DOE solve.")
    parser.add_argument("--n", type=int, default=None)
    parser.add_argument("--focus-sampling-um", type=float, default=None)
    parser.add_argument("--iterations", type=int, default=None)
    parser.add_argument("--method", choices=["gs", "mraf", "wgs", "wgs-leonardo"], default=None)
    parser.add_argument(
        "--target",
        choices=[
            "hard",
            "soft",
            "industrial_logistic",
            "industrial_rounded_logistic",
            "industrial_rounded_logistic_smooth_tail",
        ],
        default=None,
    )
    parser.add_argument("--target-size-50-x-um", type=float, default=None)
    parser.add_argument("--target-size-50-y-um", type=float, default=None)
    parser.add_argument("--corner-radius-um", type=float, default=None)
    parser.add_argument(
        "--phase-init",
        choices=["random", "quadratic", "astigmatic_quadratic", "conical_like"],
        default=None,
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--mraf-factor", type=float, default=None)
    parser.add_argument("--target-power-fraction", type=float, default=None)
    parser.add_argument("--feedback-exponent", type=float, default=None)
    parser.add_argument("--transition-width-13-90-um", type=float, default=None)
    parser.add_argument("--transition-width-13-90-x-um", type=float, default=None)
    parser.add_argument("--transition-width-13-90-y-um", type=float, default=None)
    parser.add_argument("--free-region-threshold-intensity", type=float, default=None)
    parser.add_argument("--descending-edge-mode", choices=["none", "raised_cosine"], default=None)
    parser.add_argument("--descending-edge-width-um", type=float, default=None)
    parser.add_argument("--descending-edge-end-intensity", type=float, default=None)
    parser.add_argument("--controlled-tail-end-intensity", type=float, default=None)
    parser.add_argument("--controlled-tail-width-um", type=float, default=None)
    parser.add_argument("--controlled-tail-width-x-um", type=float, default=None)
    parser.add_argument("--controlled-tail-width-y-um", type=float, default=None)
    parser.add_argument("--tail-to-free", action="store_true", default=None)
    parser.add_argument("--tail-end-intensity", type=float, default=None)
    parser.add_argument("--tail-width-um", type=float, default=None)
    parser.add_argument("--side-lobe-search-width-um", type=float, default=None)
    parser.add_argument("--free-region-width-x-um", type=float, default=None)
    parser.add_argument("--free-region-width-y-um", type=float, default=None)
    parser.add_argument("--initial-phase-file", default=None)
    parser.add_argument("--out-root", default=None)
    parser.add_argument("--variant-name", default=None)
    return parser.parse_args()


def run_variant(config: DOEConfig, out_dir: Path) -> dict:
    grid = make_grid(config)
    input_amplitude, aperture = gaussian_aperture_amplitude(config, grid)
    target = make_target(config, grid)
    pupil = lens_pupil_mask(config, grid)
    propagator = Propagator(config, grid, pupil)
    initial_phase_file = getattr(config, "initial_phase_file", None)
    if initial_phase_file:
        phase0 = np.load(initial_phase_file)
        if phase0.shape != (config.n, config.n):
            raise ValueError(
                f"Initial phase shape {phase0.shape} does not match grid {(config.n, config.n)}"
            )
    else:
        phase0 = initial_phase(config, grid, np.random.default_rng(config.seed))

    result = solve_phase(config, input_amplitude, phase0, target.amplitude, propagator)
    metrics = compute_metrics(config, grid, target, result.focal_intensity)

    config_payload = config.to_dict()
    if initial_phase_file:
        config_payload["initial_phase_file"] = str(initial_phase_file)
    config_payload["clear_aperture_diameter_mm"] = config.aperture_diameter_mm
    config_payload["gaussian_1e2_intensity_diameter_mm"] = config.gaussian_1e2_diameter_mm
    config_payload["aperture_inside_is_uniform"] = False
    config_payload["aperture_outside_amplitude"] = 0.0
    config_payload["beam_shape_diagnostic"] = load_bgdata_summary(config.beam_shape_file, Path.cwd())
    config_payload["input_beam_definition"] = {
        "type": "Gaussian intensity beam clipped by DOE clear aperture",
        "gaussian_1e2_intensity_diameter_mm": config.gaussian_1e2_diameter_mm,
        "gaussian_1e2_intensity_radius_w_mm": config.gaussian_1e2_diameter_mm / 2.0,
        "intensity_formula": "I(r)=exp(-2*r^2/w^2)",
        "amplitude_formula": "A(r)=sqrt(I)=exp(-r^2/w^2)",
        "clear_aperture_diameter_mm": config.aperture_diameter_mm,
        "aperture_outside_amplitude": 0.0,
        "aperture_inside_is_uniform": False,
    }
    config_payload["aperture_nonzero_pixels"] = int(np.count_nonzero(aperture))
    config_payload["aperture_outside_amplitude_max"] = float(
        np.max(np.abs(input_amplitude[~aperture])) if np.any(~aperture) else 0.0
    )
    config_payload["mraf_noise_region_forced_zero"] = bool(
        any(step["noise_region_forced_zero"] for step in result.history)
    )
    config_payload["last_iteration"] = result.history[-1] if result.history else {}

    write_json(out_dir / "config.json", config_payload)
    write_json(out_dir / "metrics.json", metrics)
    save_arrays(out_dir, result.phase, target.amplitude, result.focal_intensity)
    save_all_plots(
        out_dir,
        config,
        grid,
        target,
        result.phase,
        result.focal_intensity,
        aperture,
        input_amplitude=input_amplitude,
    )

    return {"config": config_payload, "metrics": metrics, "out_dir": str(out_dir)}


def main() -> None:
    args = parse_args()
    config = update_config(
        DOEConfig(),
        n=args.n,
        focus_sampling_um=args.focus_sampling_um,
        iterations=args.iterations,
        method=args.method,
        target=args.target,
        target_width_um=args.target_size_50_x_um,
        target_height_um=args.target_size_50_y_um,
        corner_radius_um=args.corner_radius_um,
        phase_init=args.phase_init,
        seed=args.seed,
        mraf_factor=args.mraf_factor,
        target_power_fraction=args.target_power_fraction,
        feedback_exponent=args.feedback_exponent,
        transition_width_13_90_um=args.transition_width_13_90_um,
        transition_width_13_90_x_um=args.transition_width_13_90_x_um,
        transition_width_13_90_y_um=args.transition_width_13_90_y_um,
        free_region_threshold_intensity=args.free_region_threshold_intensity,
        descending_edge_mode=args.descending_edge_mode,
        descending_edge_width_um=args.descending_edge_width_um,
        descending_edge_end_intensity=args.descending_edge_end_intensity,
        controlled_tail_end_intensity=args.controlled_tail_end_intensity,
        controlled_tail_width_um=args.controlled_tail_width_um,
        controlled_tail_width_x_um=args.controlled_tail_width_x_um,
        controlled_tail_width_y_um=args.controlled_tail_width_y_um,
        tail_to_free=args.tail_to_free,
        tail_end_intensity=args.tail_end_intensity,
        tail_width_um=args.tail_width_um,
        side_lobe_search_width_um=args.side_lobe_search_width_um,
        free_region_width_x_um=args.free_region_width_x_um,
        free_region_width_y_um=args.free_region_width_y_um,
    )
    if args.initial_phase_file:
        config.initial_phase_file = args.initial_phase_file
    name = args.variant_name or f"{config.method}_{config.target}_{config.phase_init}"
    root = Path(args.out_root) if args.out_root else timestamped_root()
    out_dir = variant_dir(root, name)
    summary = run_variant(config, out_dir)
    print(f"saved: {summary['out_dir']}")
    print(f"compute_window_mm: {summary['config']['compute_window_mm']:.6f}")
    print(f"doe_sampling_um: {summary['config']['doe_sampling_mm'] * 1000.0:.6f}")
    print(f"focus_sampling_um: {summary['config']['focus_sampling_um']:.6f}")
    print(
        "target_size_50_x/y_um: "
        f"{summary['metrics']['target_size_50_x_um']:.6g} / "
        f"{summary['metrics']['target_size_50_y_um']:.6g}"
    )
    print(f"output_size_50_x/y_um: {summary['metrics']['size_50_x_um']:.6g} / {summary['metrics']['size_50_y_um']:.6g}")
    print(
        "target_transition_13_90_x/y_um: "
        f"{summary['metrics']['target_transition_width_13_90_x_um']:.6g} / "
        f"{summary['metrics']['target_transition_width_13_90_y_um']:.6g}"
    )
    print(
        "output_transition_13_90_x/y_um: "
        f"{summary['metrics']['transition_width_13_90_x_um']:.6g} / "
        f"{summary['metrics']['transition_width_13_90_y_um']:.6g}"
    )
    print(f"rms_core: {summary['metrics']['rms_core']:.6g}")
    print(f"rms_90: {summary['metrics']['rms_90']:.6g}")
    print(f"rms_50_reference: {summary['metrics']['rms_50_reference']:.6g}")
    print(f"efficiency_13p5: {summary['metrics']['efficiency_13p5']:.6g}")
    print(
        "outside_max_rel_x/y: "
        f"{summary['metrics']['outside_max_x_rel_to_core']:.6g} / "
        f"{summary['metrics']['outside_max_y_rel_to_core']:.6g}"
    )
    print(
        "strongest_derivative_side_lobe_x_right/y_right: "
        f"{summary['metrics']['strongest_side_lobe_peak_x_right_rel_to_core']:.6g} / "
        f"{summary['metrics']['strongest_side_lobe_peak_y_right_rel_to_core']:.6g}"
    )
    print(
        "center_profile_std_x/y: "
        f"{summary['metrics']['center_profile_std_x']:.6g} / "
        f"{summary['metrics']['center_profile_std_y']:.6g}"
    )


if __name__ == "__main__":
    main()
