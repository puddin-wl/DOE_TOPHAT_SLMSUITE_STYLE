from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from src.config import DOEConfig, update_config
from src.grids import make_grid
from src.metrics import _center_connected_edges, target_intensity
from src.targets import make_target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview industrial target definitions without solving DOE phase.")
    parser.add_argument("--n", type=int, default=2048)
    parser.add_argument("--target-size-50-x-um", type=float, default=330.0)
    parser.add_argument("--target-size-50-y-um", type=float, default=116.0)
    parser.add_argument("--transition-width-13-90-x-um", type=float, default=12.0)
    parser.add_argument("--transition-width-13-90-y-um", type=float, default=16.0)
    parser.add_argument("--corner-radius-um", type=float, default=None)
    parser.add_argument("--controlled-tail-end-intensity", type=float, default=0.03)
    parser.add_argument("--controlled-tail-width-um", type=float, default=None)
    parser.add_argument("--out-root", default=None)
    return parser.parse_args()


def threshold_crossings(coord_um: np.ndarray, profile: np.ndarray) -> dict[float, tuple[float, float, float]]:
    return {level: _center_connected_edges(coord_um, profile, level) for level in (0.9, 0.5, 0.135)}


def save_target_image(path: Path, config: DOEConfig, grid, intensity: np.ndarray, title: str) -> None:
    crop = np.abs(grid.x_um_focus) <= config.plot_crop_um
    data = np.ma.masked_invalid(intensity[np.ix_(crop, crop)])
    x = grid.x_um_focus[crop]
    y = grid.y_um_focus[crop]
    fig, ax = plt.subplots(figsize=(6.4, 5.4), dpi=160)
    im = ax.imshow(
        data,
        extent=[float(x[0]), float(x[-1]), float(y[0]), float(y[-1])],
        origin="lower",
        cmap="viridis",
        vmin=0.0,
        vmax=1.0,
        interpolation="nearest",
    )
    ax.set_title(title)
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def region_mask(target, intensity: np.ndarray) -> np.ndarray:
    mask = np.full_like(intensity, 0.0, dtype=np.float64)
    finite = target.finite_mask
    mask[finite & (intensity < 0.135)] = 1.0
    mask[finite & (intensity >= 0.135) & (intensity < 0.9)] = 2.0
    mask[finite & (intensity >= 0.9)] = 3.0
    mask[target.noise_mask] = 4.0
    return mask


def save_mask_image(path: Path, config: DOEConfig, grid, mask: np.ndarray, title: str) -> None:
    crop = np.abs(grid.x_um_focus) <= config.plot_crop_um
    data = mask[np.ix_(crop, crop)]
    x = grid.x_um_focus[crop]
    y = grid.y_um_focus[crop]
    fig, ax = plt.subplots(figsize=(6.4, 5.4), dpi=160)
    im = ax.imshow(
        data,
        extent=[float(x[0]), float(x[-1]), float(y[0]), float(y[-1])],
        origin="lower",
        cmap="tab10",
        vmin=0.0,
        vmax=4.0,
        interpolation="nearest",
    )
    ax.set_title(title + "\n0 unused, 1 tail, 2 transition, 3 core, 4 free/noise")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_profile_comparison(path: Path, config: DOEConfig, grid, profiles: dict[str, np.ndarray]) -> None:
    cx = grid.n // 2
    cy = grid.n // 2
    x_view = np.abs(grid.x_um_focus) <= config.plot_crop_um
    y_view = np.abs(grid.y_um_focus) <= config.plot_crop_um
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.2), dpi=160)
    for name, intensity in profiles.items():
        axes[0].plot(grid.x_um_focus[x_view], intensity[cy, x_view], lw=1.4, label=name)
        axes[1].plot(grid.y_um_focus[y_view], intensity[y_view, cx], lw=1.4, label=name)
    for ax, coord, profile_axis in (
        (axes[0], grid.x_um_focus, "x"),
        (axes[1], grid.y_um_focus, "y"),
    ):
        for level, color in ((0.9, "tab:green"), (0.5, "tab:red"), (0.135, "tab:purple")):
            ax.axhline(level, color=color, lw=0.8, alpha=0.45, label=f"{level:g}" if profile_axis == "x" else None)
        for name, intensity in profiles.items():
            line = intensity[cy, :] if profile_axis == "x" else intensity[:, cx]
            crossings = threshold_crossings(coord, line)
            for level, color in ((0.9, "tab:green"), (0.5, "tab:red"), (0.135, "tab:purple")):
                left, right, _ = crossings[level]
                if np.isfinite(left) and np.isfinite(right):
                    ax.scatter([left, right], [level, level], s=16, color=color, zorder=5)
        ax.set_xlabel(f"{profile_axis} (um)")
        ax.set_ylabel("target intensity")
        ax.set_ylim(-0.02, 1.08)
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, fontsize=8)
    axes[0].set_title("x center profile")
    axes[1].set_title("y center profile")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    root = Path(args.out_root) if args.out_root else Path("artifacts") / f"target_preview_{datetime.now():%Y%m%d-%H%M%S}"
    root.mkdir(parents=True, exist_ok=True)
    base_config = update_config(
        DOEConfig(),
        n=args.n,
        target_width_um=args.target_size_50_x_um,
        target_height_um=args.target_size_50_y_um,
        transition_width_13_90_x_um=args.transition_width_13_90_x_um,
        transition_width_13_90_y_um=args.transition_width_13_90_y_um,
        corner_radius_um=args.corner_radius_um,
        controlled_tail_end_intensity=args.controlled_tail_end_intensity,
        controlled_tail_width_um=args.controlled_tail_width_um,
    )
    grid = make_grid(base_config)

    profiles: dict[str, np.ndarray] = {}
    for target_name in ("industrial_logistic", "industrial_rounded_logistic"):
        config = update_config(base_config, target=target_name)
        target = make_target(config, grid)
        intensity = target_intensity(target)
        profiles[target_name] = intensity
        save_target_image(root / f"{target_name}_intensity.png", config, grid, intensity, f"{target_name} target intensity")
        save_mask_image(root / f"{target_name}_regions.png", config, grid, region_mask(target, intensity), f"{target_name} regions")

    save_profile_comparison(root / "target_center_profile_comparison.png", base_config, grid, profiles)
    print(f"saved target preview: {root}")


if __name__ == "__main__":
    main()
