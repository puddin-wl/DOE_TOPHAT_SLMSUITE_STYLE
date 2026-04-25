from __future__ import annotations

import numpy as np

from .config import DOEConfig
from .grids import Grid


def wrap_phase(phase: np.ndarray) -> np.ndarray:
    return np.mod(phase, 2.0 * np.pi)


def initial_phase(config: DOEConfig, grid: Grid, rng: np.random.Generator | None = None) -> np.ndarray:
    rng = rng or np.random.default_rng(config.seed)
    name = config.phase_init.lower()

    aperture_radius = config.aperture_diameter_mm / 2.0
    x = grid.X_mm / aperture_radius
    y = grid.Y_mm / aperture_radius
    r = np.sqrt(x**2 + y**2)

    if name == "random":
        phase = rng.uniform(0.0, 2.0 * np.pi, size=(grid.n, grid.n))
    elif name == "quadratic":
        phase = np.pi * config.quadratic_strength * (x**2 + y**2)
    elif name == "astigmatic_quadratic":
        phase = np.pi * (
            config.astigmatic_strength_x * x**2 + config.astigmatic_strength_y * y**2
        )
    elif name == "conical_like":
        phase = 2.0 * np.pi * config.conical_strength * r
    else:
        raise ValueError(f"Unknown phase initializer: {config.phase_init!r}")

    return wrap_phase(phase)
