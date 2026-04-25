# DOE_TOPHAT_SLMSUITE_STYLE

Minimal continuous-phase DOE solver for a 330 um x 120 um industrial 50%-intensity rectangular flat-top target.

This is a fresh Python DOE design project. It does not reuse MATLAB code and does not include SLM hardware, camera feedback, calibration, LUT, or experimental closed-loop logic.

## Current Defaults

- Wavelength: 532 nm
- Focal length: 429 mm
- DOE to lens distance: 200 mm
- DOE clear aperture: 15 mm circular aperture
- Input beam: 5 mm Gaussian intensity 1/e^2 diameter
- Target size: `size_50_x/y = 330 x 120 um`
- Default grid: `N = 2048`, focal sampling `2.5 um`
- Default solver: `method=wgs`, `phase_init=quadratic`, `mraf_factor=0.5`
- Default target: `industrial_logistic`
- Default `tail_to_free=false`

The 15 mm aperture is the DOE clear aperture. It is not a 15 mm uniform input beam. The solver uses a 5 mm 1/e^2 intensity Gaussian beam clipped by the 15 mm aperture.

The file `参数/3044.bgData` is treated only as an initial beam-shape diagnostic. The solver still uses the expanded 5 mm Gaussian at the DOE plane.

## Environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Recommended Runs

Smoke test:

```powershell
python run_one.py --n 512 --iterations 2 --target industrial_logistic --method wgs
```

Sharp candidate:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5
```

Balanced candidate:

```powershell
python run_one.py --n 2048 --iterations 50 --method wgs --target industrial_logistic --transition-width-13-90-x-um 16 --transition-width-13-90-y-um 20 --mraf-factor 0.5
```

Tail-to-free diagnostic:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5 --tail-to-free --tail-end-intensity 0.03 --tail-width-um 12
```

## Outputs

Each run writes to `artifacts/YYYYMMDD-HHMMSS/<variant>/` or to the `--out-root` directory.

Key files:

- `config.json`
- `metrics.json`
- `phase.npy`
- `target.npy`
- `focal_intensity.npy`
- `target.png`
- `masks.png`
- `input_amplitude.png`
- `input_intensity.png`
- `phase.png`
- `phase_with_beam_overlay.png`
- `focal_intensity.png`
- `focal_intensity_log.png`
- `roi_intensity.png`
- `center_profiles.png`
- `center_profiles_flatness.png`
- `center_profiles_raw_norm.png`
- `edge_diagnostic_profiles.png`
- `edge_spike_diagnostic.png`

Small size precomp sweeps also write a root-level `summary.csv`.

Artifact selection rule:

1. Keep `size_50_x/y` close to `330 x 120 um`.
2. Compare `transition_width_13_90_x/y`.
3. Check `rms_90` and `center_profile_std_x/y`.
4. Check `side_lobe_peak_x/y_rel_to_core`.
5. Inspect `edge_diagnostic_profiles.png` for boundary ringing or small symmetric side lobes.

## Documentation

Full workflow and tuning guide:

```text
docs/WORKFLOW_AND_TUNING.md
```

Compact algorithm notes:

```text
CORE_ALGORITHM.md
```

Recent result notes:

```text
RESULTS.md
```
