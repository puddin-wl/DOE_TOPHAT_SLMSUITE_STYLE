# DOE_TOPHAT_SLMSUITE_STYLE

Minimal continuous-phase DOE solver for a 330 um x 120 um rectangular flat-top target.

This is a fresh Python project. It does not reuse MATLAB project code and does not include SLM hardware, camera feedback, calibration, LUT, or experimental closed-loop logic.

## Physics Defaults

- Wavelength: 532 nm
- Target ROI: 330 um x 120 um
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
python run_one.py --n 512 --iterations 3
```

Default-size short run:

```powershell
python run_one.py --n 2048 --iterations 20
```

Minimal comparison:

```powershell
python run_compare_minimal.py --n 2048
```

Useful tuning knobs after the smoke test:

```powershell
python run_one.py --n 2048 --iterations 50 --method mraf --target soft --phase-init quadratic --mraf-factor 0.5 --target-power-fraction 0.7
python run_one.py --n 2048 --iterations 50 --method mraf --target soft --phase-init quadratic --free-region-width-x-um 160 --free-region-width-y-um 160
```

Slmsuite-style WGS-Leonardo polish after an MRAF run:

```powershell
python run_one.py --n 2048 --iterations 60 --method wgs-leonardo --target soft --phase-init quadratic --mraf-factor 0.5 --feedback-exponent 2.0 --initial-phase-file artifacts\compare_slmsuite_20260425-165619\mraf_soft_quadratic\phase.npy
```

Rounded-rectangle RTAD target:

```powershell
python run_one.py --n 2048 --iterations 60 --method mraf --target rounded_rtad --phase-init quadratic --mraf-factor 1.0
python run_one.py --n 2048 --iterations 60 --method wgs-leonardo --target rounded_rtad --phase-init quadratic --mraf-factor 1.0 --feedback-exponent 2.0 --initial-phase-file <rounded_mraf_phase.npy>
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

For the soft target, finite pixels are constrained:

- Core: amplitude 1
- Edge: separable raised-cosine falloff in x/y
- A finite ring outside the edge: `NaN`, meaning MRAF free/noise region
- Outside that ring: zero/guard region

In MRAF, `NaN` target pixels keep their current complex focal field. They are not forced to zero. The DOE plane then restores only the input amplitude, `5 mm Gaussian x 15 mm aperture`, and keeps the returned phase.

The default free ring width is 120 um in x and y. The default `mraf_factor` is 0.5, so the free ring is relaxed but not zeroed. The target weights and input amplitude are normalized in the slmsuite style. Optional `wgs-leonardo` updates target weights from the simulated focal-plane feedback; it is computational only and does not use camera feedback. For the current 2048 tuning, `feedback_exponent=2.0` is the best tested value so far.

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

The ROI center profiles are normalized by their own mean inside the 330 um x 120 um ROI.
