from __future__ import annotations

import numpy as np

from .config import DOEConfig
from .grids import Grid


def fft2c(field: np.ndarray) -> np.ndarray:
    return np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(field), norm="ortho"))


def ifft2c(field: np.ndarray) -> np.ndarray:
    return np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(field), norm="ortho"))


def angular_spectrum_kernel(config: DOEConfig, grid: Grid, distance_mm: float) -> np.ndarray:
    wavelength_mm = config.wavelength_mm
    inside = (1.0 / wavelength_mm) ** 2 - grid.FX_cyc_per_mm**2 - grid.FY_cyc_per_mm**2
    kz = 2.0 * np.pi * np.sqrt(np.maximum(inside, 0.0))
    kernel = np.exp(1j * kz * distance_mm)
    kernel[inside < 0.0] = 0.0
    return kernel


def angular_spectrum(field: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    return ifft2c(fft2c(field) * kernel)


class Propagator:
    def __init__(self, config: DOEConfig, grid: Grid, pupil_mask: np.ndarray):
        self.config = config
        self.grid = grid
        self.pupil_mask = pupil_mask.astype(np.float64)
        self.asm_forward_kernel = angular_spectrum_kernel(config, grid, config.asm_distance_mm)
        self.asm_backward_kernel = angular_spectrum_kernel(config, grid, -config.asm_distance_mm)

    def forward(self, doe_field: np.ndarray) -> np.ndarray:
        lens_field = angular_spectrum(doe_field, self.asm_forward_kernel)
        lens_field = lens_field * self.pupil_mask
        return fft2c(lens_field)

    def backward(self, focal_field: np.ndarray) -> np.ndarray:
        lens_field = ifft2c(focal_field) * self.pupil_mask
        return angular_spectrum(lens_field, self.asm_backward_kernel)
