# Current DOE Results

This repository keeps large run artifacts out of git. The local artifact images and arrays are under `artifacts/`, while this file records the current reproducible result.

## Best 2048 Result So Far

Run:

```powershell
python run_one.py --n 2048 --iterations 60 --method wgs-leonardo --target soft --phase-init quadratic --mraf-factor 0.5 --feedback-exponent 0.8 --initial-phase-file artifacts\compare_slmsuite_20260425-165619\mraf_soft_quadratic\phase.npy
```

Local output:

```text
artifacts\wgs_quadratic_20260425-171336\wgs_leonardo_mraf_soft_quadratic
```

Metrics:

```text
rms_in_roi                 0.0530755
efficiency_in_roi          0.795279
size_50_x                  340 um
size_50_y                  135 um
center_profile_p2p_x       0.264285
center_profile_p2p_y       0.198795
center_profile_std_x       0.0309731
center_profile_std_y       0.0432374
```

Configuration notes:

```text
N                           2048
focus_sampling_um           2.5
method                      wgs-leonardo
base target                 soft rectangle
initial phase               quadratic phase from previous MRAF result
mraf_factor                 0.5
feedback_exponent           0.8
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

The WGS-Leonardo computational weighting step is currently the important improvement. It keeps the MRAF free/noise ring behavior but updates signal weights from the simulated focal field to suppress regular profile ripple.
