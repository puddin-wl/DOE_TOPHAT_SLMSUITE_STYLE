# Current DOE Results

This repository keeps large run artifacts out of git. The local artifact images and arrays are under `artifacts/`, while this file records the current reproducible result.

## Best 2048 Result So Far

Run:

```powershell
python run_one.py --n 2048 --iterations 60 --method wgs-leonardo --target soft --phase-init quadratic --mraf-factor 0.5 --feedback-exponent 2.0 --initial-phase-file artifacts\compare_slmsuite_20260425-165619\mraf_soft_quadratic\phase.npy
```

Local output:

```text
artifacts\tune_wgs4_20260425-173318\wgs60_exp20_mraf05
```

Metrics:

```text
rms_in_roi                 0.0509485
efficiency_in_roi          0.791118
size_50_x                  340 um
size_50_y                  135 um
center_profile_p2p_x       0.237198
center_profile_p2p_y       0.196406
center_profile_std_x       0.0275223
center_profile_std_y       0.0428646
```

Configuration notes:

```text
N                           2048
focus_sampling_um           2.5
method                      wgs-leonardo
base target                 soft rectangle
initial phase               quadratic phase from previous MRAF result
mraf_factor                 0.5
feedback_exponent           2.0
signal / noise / zero px    11297 / 30912 / 4152095
noise region forced zero    false
aperture outside amplitude  0.0
```

## Interpretation

Plain MRAF reached a useful but visibly rippled result:

```text
MRAF soft quadratic, 60 iterations
rms_in_roi                 0.184628
efficiency_in_roi          0.847186
size_50_x / size_50_y       320 um / 125 um
center_profile_std_x/y      0.144822 / 0.113546
```

The WGS-Leonardo computational weighting step is currently the important improvement. It keeps the MRAF free/noise ring behavior but updates signal weights from the simulated focal field to suppress regular profile ripple. A short 2048 sweep found steady but diminishing improvement from `feedback_exponent=0.8` to `2.0`; `2.0` is the current best tested point.

## Rounded RTAD Check

Rounded RTAD target was added with:

```text
core_width_um       310
core_height_um      95
corner_radius_um    25
shoulder_width_um   20
shoulder_level      0.75
fall_width_um       50
noise_band_um       80
```

The target shape is now a rounded rectangle with a constant shoulder and raised-cosine falloff. The NaN free/noise band is preserved by MRAF (`mraf_factor=1.0`) and is not forced to zero.

Best rounded RTAD check so far:

```text
artifacts\rounded_rtad_wgs_20260425-180034\wgs_rounded_rtad_guard

rms_in_roi                 0.100386
efficiency_in_roi          0.190475
size_50_x / size_50_y       40 um / 135 um
center_profile_p2p_x/y      0.278559 / 0.267121
center_profile_std_x/y      0.0415751 / 0.0605249
```

The rounded RTAD profile is smoother than plain rounded MRAF, but it currently sends too much energy into halo/free regions. It should be retained as the industrial-shape target, but the next tuning should adjust `core_height_um`, `shoulder_level`, `fall_width_um`, and `noise_band_um` rather than continuing to tune WGS exponent.
