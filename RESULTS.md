# DOE Results Log

Note: the entries below are legacy pre-industrial-target runs that used the old soft rectangle / ROI RMS definition. The current code now uses the industrial 50% size target, logistic intensity edge, 13.5% free/noise threshold, and the new metrics described in `CORE_ALGORITHM.md`.

This repository keeps large run artifacts out of git. The local artifact images and arrays are under `artifacts/`, while this file records the current reproducible result.

## Current Industrial Transition Check

Best aggressive edge candidate from the first focused 2048 sweep:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5
```

Local output:

```text
artifacts\transition_sweep_20260425-2052\twx12_twy16_mraf05_i80
```

Metrics:

```text
target_transition_width_13_90_x/y_um   12.3 / 16.2
output_transition_width_13_90_x/y_um   16.8 / 20.5
output_size_50_x/y_um                  333.9 / 123.2
efficiency_13p5                        0.864
rms_90                                 0.0208
center_profile_std_x/y                 0.0600 / 0.1083
```

The earlier 40 um baseline is confirmed to be target-limited rather than propagation-broadened:

```text
target_transition_width_13_90_x/y_um   40.1 / 40.1
output_transition_width_13_90_x/y_um   38.9 / 37.8
```

Finite tail diagnostic for `transition x/y = 12/16`, `mraf_factor = 0.5`, `iterations = 80`:

```text
artifact root:
artifacts\tail_diagnostic_20260425-2206

case                 output_tw_x/y   size50_x/y    eff13   rms90   side_lobe_rel_x/y
baseline false       16.8 / 20.5     333.9 / 123.2 0.864   0.0208  0.164 / 0.106
tail 3%, width 12    16.8 / 20.7     333.6 / 123.6 0.842   0.0218  0.185 / 0.107
tail 1%, width 12    17.0 / 18.5     334.6 / 122.3 0.815   0.0207  0.183 / 0.174
```

In this first test, the finite tail did not reduce the side-lobe peak. Keep `tail_to_free=false` as the current recommendation unless a later sweep finds a better tail width/end intensity.

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
