from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw

from src.artifacts import write_json
from src.config import DOEConfig, update_config
from src.grids import make_grid
from src.metrics import _center_connected_edges, _transition_width, target_intensity
from src.plotting import _profile_reference_intensity
from src.targets import make_target


FROZEN_DIR = Path("artifacts/mraf_fine_20260426-025728/mraf_0p400")
ROUNDED_DIR = Path("artifacts/rounded_logistic_single_20260426/rounded_logistic_single")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Target-only and result-only diagnosis for industrial_rounded_logistic.")
    parser.add_argument("--out-root", default=None)
    return parser.parse_args()


def config_from_json(path: Path) -> DOEConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    fields = DOEConfig.__dataclass_fields__.keys()
    return update_config(DOEConfig(), **{key: payload[key] for key in fields if key in payload})


def transition_settings(config: DOEConfig) -> tuple[float, float]:
    tx = config.transition_width_13_90_x_um or config.transition_width_13_90_um
    ty = config.transition_width_13_90_y_um or config.transition_width_13_90_um
    return float(tx), float(ty)


def crossings(coord_um: np.ndarray, profile: np.ndarray) -> dict[str, tuple[float, float, float]]:
    return {
        "90": _center_connected_edges(coord_um, profile, 0.9),
        "50": _center_connected_edges(coord_um, profile, 0.5),
        "13p5": _center_connected_edges(coord_um, profile, 0.135),
        "3": _center_connected_edges(coord_um, profile, 0.03),
    }


def region_spans(edges: dict[str, tuple[float, float, float]], side: str) -> dict[str, tuple[float, float]]:
    idx = 0 if side == "left" else 1
    edge90 = edges["90"][idx]
    edge13 = edges["13p5"][idx]
    edge3 = edges["3"][idx]
    if side == "left":
        return {
            "main transition": (edge13, edge90),
            "controlled tail": (edge3, edge13),
        }
    return {
        "main transition": (edge90, edge13),
        "controlled tail": (edge13, edge3),
    }


def shade_regions(ax: plt.Axes, edges: dict[str, tuple[float, float, float]]) -> None:
    colors = {"main transition": "tab:green", "controlled tail": "tab:orange"}
    for side in ("left", "right"):
        for label, span in region_spans(edges, side).items():
            if np.all(np.isfinite(span)):
                ax.axvspan(min(span), max(span), color=colors[label], alpha=0.12, label=label if side == "left" else None)


def save_profile_with_thresholds(path: Path, coord_um: np.ndarray, profile: np.ndarray, axis_label: str) -> dict:
    edges = crossings(coord_um, profile)
    fig, ax = plt.subplots(figsize=(8.2, 4.6), dpi=160)
    ax.plot(coord_um, profile, lw=1.6, label="rounded target")
    shade_regions(ax, edges)
    for level, key, color in ((0.9, "90", "tab:green"), (0.5, "50", "tab:red"), (0.135, "13p5", "tab:purple"), (0.03, "3", "tab:orange")):
        ax.axhline(level, color=color, lw=0.8, alpha=0.55, label=f"{level:g}")
        left, right, _ = edges[key]
        if np.isfinite(left) and np.isfinite(right):
            ax.scatter([left, right], [level, level], s=24, color=color, zorder=5)
            ax.axvline(left, color=color, lw=0.7, ls="--", alpha=0.35)
            ax.axvline(right, color=color, lw=0.7, ls="--", alpha=0.35)
    ax.set_xlim(-260 if axis_label == "x" else -170, 260 if axis_label == "x" else 170)
    ax.set_ylim(-0.03, 1.08)
    ax.set_xlabel(f"{axis_label} (um)")
    ax.set_ylabel("target intensity")
    ax.set_title(f"rounded target {axis_label} profile with thresholds")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return edges


def save_profile_derivatives(path: Path, coord_um: np.ndarray, profile: np.ndarray, edges: dict, axis_label: str) -> None:
    right50 = edges["50"][1]
    s = coord_um - right50
    mask = (s >= -35.0) & (s <= 80.0) & np.isfinite(profile)
    s_view = s[mask]
    p_view = profile[mask]
    d1 = np.gradient(p_view, s_view)
    d2 = np.gradient(d1, s_view)
    fig, axes = plt.subplots(3, 1, figsize=(8.0, 7.2), dpi=160, sharex=True)
    axes[0].plot(s_view, p_view, lw=1.5)
    axes[0].set_ylabel("I")
    axes[1].plot(s_view, d1, lw=1.2, color="tab:blue")
    axes[1].axhline(0, color="0.6", lw=0.8)
    axes[1].set_ylabel("dI/ds")
    axes[2].plot(s_view, d2, lw=1.2, color="tab:red")
    axes[2].axhline(0, color="0.6", lw=0.8)
    axes[2].set_ylabel("d2I/ds2")
    axes[2].set_xlabel(f"outward coordinate s from right 50% {axis_label} edge (um)")
    for ax in axes:
        for level, key, color in ((0.9, "90", "tab:green"), (0.5, "50", "tab:red"), (0.135, "13p5", "tab:purple"), (0.03, "3", "tab:orange")):
            pos = edges[key][1] - right50
            if np.isfinite(pos):
                ax.axvline(pos, color=color, lw=0.8, ls="--", alpha=0.55, label=f"{level:g}" if ax is axes[0] else None)
        ax.grid(alpha=0.25)
    axes[0].legend(frameon=False, fontsize=8, ncol=4)
    fig.suptitle(f"rounded target {axis_label} outward profile derivatives")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_overlay(path: Path, grid, logistic_i: np.ndarray, rounded_i: np.ndarray) -> None:
    center = grid.n // 2
    x_view = np.abs(grid.x_um_focus) <= 260
    y_view = np.abs(grid.y_um_focus) <= 170
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), dpi=160)
    axes[0].plot(grid.x_um_focus[x_view], logistic_i[center, x_view], label="industrial_logistic")
    axes[0].plot(grid.x_um_focus[x_view], rounded_i[center, x_view], label="industrial_rounded_logistic")
    axes[1].plot(grid.y_um_focus[y_view], logistic_i[y_view, center], label="industrial_logistic")
    axes[1].plot(grid.y_um_focus[y_view], rounded_i[y_view, center], label="industrial_rounded_logistic")
    for ax, label in zip(axes, ("x", "y")):
        for level, color in ((0.9, "tab:green"), (0.5, "tab:red"), (0.135, "tab:purple"), (0.03, "tab:orange")):
            ax.axhline(level, color=color, lw=0.8, alpha=0.45)
        ax.set_xlabel(f"{label} (um)")
        ax.set_ylabel("target intensity")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, fontsize=8)
    axes[0].set_title("x center profile overlay")
    axes[1].set_title("y center profile overlay")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def region_mask(target, intensity: np.ndarray) -> np.ndarray:
    mask = np.zeros_like(intensity, dtype=np.float64)
    finite = target.finite_mask
    mask[finite & (intensity < 0.135)] = 1.0
    mask[finite & (intensity >= 0.135) & (intensity < 0.9)] = 2.0
    mask[finite & (intensity >= 0.9)] = 3.0
    mask[target.noise_mask] = 4.0
    return mask


def save_region_mask(path: Path, config: DOEConfig, grid, target, intensity: np.ndarray) -> None:
    crop = np.abs(grid.x_um_focus) <= config.plot_crop_um
    data = region_mask(target, intensity)[np.ix_(crop, crop)]
    x = grid.x_um_focus[crop]
    y = grid.y_um_focus[crop]
    fig, ax = plt.subplots(figsize=(6.2, 5.4), dpi=160)
    im = ax.imshow(data, extent=[float(x[0]), float(x[-1]), float(y[0]), float(y[-1])], origin="lower", cmap="tab10", vmin=0, vmax=4)
    ax.set_title("rounded target region mask\n1 tail, 2 main transition, 3 core, 4 free/NaN")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def load_output_profile(artifact_dir: Path):
    config = config_from_json(artifact_dir / "config.json")
    grid = make_grid(config)
    target = make_target(config, grid)
    intensity = np.load(artifact_dir / "focal_intensity.npy")
    reference = _profile_reference_intensity(target, intensity)
    norm = intensity / reference if reference > 0 else intensity
    center = grid.n // 2
    return config, grid, norm[center, :], norm[:, center]


def save_output_comparison(path: Path, axis: str, frozen, rounded) -> None:
    _, grid_f, x_f, y_f = frozen
    _, grid_r, x_r, y_r = rounded
    coord_f = grid_f.x_um_focus if axis == "x" else grid_f.y_um_focus
    coord_r = grid_r.x_um_focus if axis == "x" else grid_r.y_um_focus
    prof_f = x_f if axis == "x" else y_f
    prof_r = x_r if axis == "x" else y_r
    view_f = np.abs(coord_f) <= 650
    view_r = np.abs(coord_r) <= 650
    fig, ax = plt.subplots(figsize=(9.0, 4.6), dpi=160)
    ax.plot(coord_f[view_f], prof_f[view_f], label="frozen industrial_logistic")
    ax.plot(coord_r[view_r], prof_r[view_r], label="rounded candidate")
    for level, color in ((0.9, "tab:green"), (0.5, "tab:red"), (0.135, "tab:purple")):
        ax.axhline(level, color=color, lw=0.8, alpha=0.45)
    ax.set_xlabel(f"{axis} (um)")
    ax.set_ylabel("output I / core mean")
    ax.set_title(f"output {axis} center profile: frozen vs rounded")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_outside_region_comparison(path: Path, frozen, rounded) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.2), dpi=160)
    for row, (axis, side) in enumerate((("x", "right"), ("y", "right"))):
        for col, (label, data) in enumerate((("frozen", frozen), ("rounded", rounded))):
            _, grid, x_prof, y_prof = data
            coord = grid.x_um_focus if axis == "x" else grid.y_um_focus
            prof = x_prof if axis == "x" else y_prof
            edges = crossings(coord, prof)
            edge = edges["13p5"][1]
            view = (coord >= edge - 40) & (coord <= edge + 220) if np.isfinite(edge) else np.abs(coord) <= 250
            ax = axes[row, col]
            ax.plot(coord[view], prof[view], lw=1.4)
            ax.axhline(0.135, color="tab:purple", lw=0.8, alpha=0.45)
            if np.isfinite(edge):
                ax.axvline(edge, color="tab:purple", lw=0.9, ls="--", alpha=0.6)
            ax.set_title(f"{label} {axis} outside region")
            ax.set_xlabel(f"{axis} (um)")
            ax.set_ylabel("I / core mean")
            ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_montage(path: Path) -> None:
    items = [
        ("frozen", FROZEN_DIR / "edge_spike_diagnostic.png"),
        ("rounded", ROUNDED_DIR / "edge_spike_diagnostic.png"),
    ]
    thumbs = []
    for label, image_path in items:
        image = Image.open(image_path).convert("RGB")
        image.thumbnail((900, 700))
        canvas = Image.new("RGB", (900, 750), "white")
        ImageDraw.Draw(canvas).text((10, 8), label, fill=(0, 0, 0))
        canvas.paste(image, (0, 35))
        thumbs.append(canvas)
    out = Image.new("RGB", (1800, 750), "white")
    out.paste(thumbs[0], (0, 0))
    out.paste(thumbs[1], (900, 0))
    out.save(path)


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_root) if args.out_root else Path("artifacts") / f"target_shape_diagnostics_{datetime.now():%Y%m%d-%H%M%S}"
    out_root.mkdir(parents=True, exist_ok=True)

    rounded_config = config_from_json(ROUNDED_DIR / "config.json")
    grid = make_grid(rounded_config)
    rounded_target = make_target(rounded_config, grid)
    rounded_i = target_intensity(rounded_target)
    logistic_config = update_config(rounded_config, target="industrial_logistic")
    logistic_target = make_target(logistic_config, grid)
    logistic_i = target_intensity(logistic_target)
    center = grid.n // 2

    x_edges = save_profile_with_thresholds(out_root / "rounded_target_x_profile_with_thresholds.png", grid.x_um_focus, rounded_i[center, :], "x")
    y_edges = save_profile_with_thresholds(out_root / "rounded_target_y_profile_with_thresholds.png", grid.y_um_focus, rounded_i[:, center], "y")
    save_profile_derivatives(out_root / "rounded_target_x_profile_derivatives.png", grid.x_um_focus, rounded_i[center, :], x_edges, "x")
    save_profile_derivatives(out_root / "rounded_target_y_profile_derivatives.png", grid.y_um_focus, rounded_i[:, center], y_edges, "y")
    save_overlay(out_root / "logistic_vs_rounded_profile_overlay.png", grid, logistic_i, rounded_i)
    save_region_mask(out_root / "rounded_target_region_masks.png", rounded_config, grid, rounded_target, rounded_i)

    frozen_output = load_output_profile(FROZEN_DIR)
    rounded_output = load_output_profile(ROUNDED_DIR)
    save_output_comparison(out_root / "output_x_profile_frozen_vs_rounded.png", "x", frozen_output, rounded_output)
    save_output_comparison(out_root / "output_y_profile_frozen_vs_rounded.png", "y", frozen_output, rounded_output)
    save_outside_region_comparison(out_root / "outside_region_frozen_vs_rounded.png", frozen_output, rounded_output)
    save_montage(out_root / "edge_spike_frozen_vs_rounded_montage.png")

    tx, ty = transition_settings(rounded_config)
    corner_radius = rounded_config.corner_radius_um if rounded_config.corner_radius_um > 0 else min(tx, ty)
    controlled_tail_width = rounded_config.controlled_tail_width_um or 2.0 * min(tx, ty)
    summary = {
        "corner_radius_um_used": corner_radius,
        "controlled_tail_width_um_used": controlled_tail_width,
        "controlled_tail_end_intensity": rounded_config.controlled_tail_end_intensity,
        "nominal_transition_x_um": tx,
        "nominal_transition_y_um": ty,
        "effective_transition_x_um": _transition_width(x_edges["90"], x_edges["13p5"]),
        "effective_transition_y_um": _transition_width(y_edges["90"], y_edges["13p5"]),
        "x_profile_50_width_um": x_edges["50"][2],
        "y_profile_50_width_um": y_edges["50"][2],
        "derivative_continuity_main_to_tail": "not C1: logistic slope at 13.5% changes to raised-cosine tail slope near zero; sampled crossing forms a shoulder",
        "derivative_continuity_tail_to_free": "tail slope approaches zero at 3%, but the target then becomes NaN/free, so the constrained target ends rather than continuing as a C1 intensity function",
        "suspected_reason_for_two_corners": "two-stage profile: flat plateau -> main logistic transition -> controlled low-intensity tail -> free/noise region",
        "suspected_reason_for_x_outside_max_reduction": "rounded corners reduce high-spatial-frequency corner content and the controlled tail weakly constrains energy below 13.5%",
        "suspected_reason_for_y_outside_max_increase": "the y dimension is short, so transition and controlled tail occupy a larger fraction of the target height, encouraging more energy spread outside the y edge",
        "recommendation": "keep frozen best as current baseline; keep rounded target as candidate; investigate target shape before further optimization",
    }
    write_json(out_root / "diagnosis_summary.json", summary)
    print(f"saved diagnosis: {out_root}")


if __name__ == "__main__":
    main()
