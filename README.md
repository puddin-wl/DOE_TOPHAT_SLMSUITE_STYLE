# DOE_TOPHAT_SLMSUITE_STYLE

Minimal continuous-phase DOE solver for a 330 um x 120 um industrial 50%-intensity flat-top target.

This is a fresh Python project. It does not reuse MATLAB project code and does not include SLM hardware, camera feedback, calibration, LUT, or experimental closed-loop logic.

## Physics Defaults

- Wavelength: 532 nm
- Target 50% intensity size: 330 um x 120 um
- Default 13.5%-to-90% transition width target: 40 um
- Expanded input beam at DOE: Gaussian 1/e^2 intensity diameter = 5 mm
- DOE clear aperture: 15 mm centered circular aperture
- Aperture outside amplitude: exactly 0
- Propagation: DOE plane -> angular spectrum 200 mm -> lens/pupil -> Fourier transform to focal plane
- Lens focal length: 429 mm
- Default grid: N = 2048, focal-plane sampling = 2.5 um

The FFT compute window is not the real DOE size. It is chosen from the focal sampling:

```text
compute_window_mm = wavelength_mm * focal_length_mm / focus_sampling_mm
```

For N = 2048 and 2.5 um focal sampling, the compute window is about 91.3 mm. The physical DOE clear aperture remains 15 mm in the center, with zero padding outside.

The file `参数/3044.bgData` is treated only as an initial beam-shape diagnostic. The solver still uses the expanded 5 mm Gaussian at the DOE plane.

## Environment

Preferred Windows PowerShell setup:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If Python 3.11 is not installed, Python 3.13 also works with the listed dependencies:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

Smoke test:

```powershell
python run_one.py --n 512 --iterations 5 --target industrial_logistic --method wgs
```

Default-size short run:

```powershell
python run_one.py --n 2048 --iterations 50 --target industrial_logistic --method wgs
```

Minimal comparison:

```powershell
python run_compare_minimal.py --n 2048
```

Useful tuning knobs after the smoke test:

```powershell
python run_one.py --n 2048 --iterations 60 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-um 40
python run_one.py --n 2048 --iterations 60 --method wgs --target industrial_logistic --phase-init quadratic --feedback-exponent 2.0
python run_one.py --n 2048 --iterations 50 --method wgs --target industrial_logistic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16
```

Slmsuite-style WGS-Leonardo polish after an MRAF run:

```powershell
python run_one.py --n 2048 --iterations 60 --method wgs --target industrial_logistic --phase-init quadratic --feedback-exponent 2.0 --initial-phase-file artifacts\some_mraf_run\phase.npy
```

4096 review run:

```powershell
python run_one.py --n 4096 --focus-sampling-um 1.25 --iterations 20
```

## Algorithm Notes

The MRAF implementation follows the algorithmic idea used by `slmsuite` hologram solvers: a target region is constrained in the Fourier/focal plane, while pixels marked as noise/free region are not forced to zero.

Reference:

- https://github.com/holodyne/slmsuite
- `slmsuite/slmsuite/holography/algorithms/_hologram.py`
- slmsuite is MIT licensed. This project rewrites a small solver from the idea rather than copying slmsuite source code.

For the industrial logistic target, finite pixels are constrained:

- The straight rectangular distance field has `d = 0` at the 330 um x 120 um boundary.
- The intensity target is `I(d) = 1 / (1 + exp(d / s))`, where `s = transition_width_13_90_um / 4.055`.
- The constrained target amplitude is `sqrt(I)`, not `I`.
- Pixels below 13.5% target intensity are set to `NaN`, meaning MRAF free/noise region.

In MRAF, `NaN` target pixels keep a relaxed copy of their current complex focal field. They are not forced to zero. The DOE plane then restores only the input amplitude, `5 mm Gaussian x 15 mm aperture`, and keeps the returned phase.

The default initial phase is `quadratic`, selected from the minimal comparison because it gave the cleanest 2048 center profiles with the industrial logistic target. The default `mraf_factor` is 0.5 for the industrial target, because full preservation at 1.0 lets too much power remain in the free/noise field. The target weights and input amplitude are normalized in the slmsuite style. Optional `wgs` / `wgs-leonardo` updates target weights from the simulated focal-plane feedback; it is computational only and does not use camera feedback.

See `CORE_ALGORITHM.md` for the compact algorithm summary and pseudocode.

## Outputs

Each run writes to `artifacts/YYYYMMDD-HHMMSS/<variant>/`:

- `config.json`
- `phase.npy`
- `target.npy`
- `focal_intensity.npy`
- `metrics.json`
- `target.png`
- `masks.png`
- `phase.png`
- `focal_intensity.png`
- `focal_intensity_log.png`
- `roi_intensity.png`
- `center_profiles.png`

The center profiles are normalized by the simulated mean intensity in the high-target core and include 90%, 50%, and 13.5% reference lines. Metrics report `size_50_x/y_um`, `size_13p5_x/y_um`, `transition_width_13_90_x/y_um`, `efficiency_13p5`, `rms_core`, `rms_90`, and `rms_50_reference`.
The same metrics are also written with explicit `target_` and `output_` prefixes so the intended target edge width can be compared with the optimized focal-plane result. `center_profiles_raw_norm.png` marks the 90%, 50%, and 13.5% crossing points used for the size and transition calculations.
