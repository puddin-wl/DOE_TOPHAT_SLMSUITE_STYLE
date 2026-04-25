# DOE Results Log

Note: the entries below are legacy pre-industrial-target runs that used the old soft rectangle / ROI RMS definition. The current code now uses the industrial 50% size target, logistic intensity edge, 13.5% free/noise threshold, and the new metrics described in `CORE_ALGORITHM.md`.

This repository keeps large run artifacts out of git. The local artifact images and arrays are under `artifacts/`, while this file records the current reproducible result.

## 2026-04-25 Engineering Tuning Update

This pass intentionally did not change the core physical model or large algorithm. It adds a small repeatable size-precomp sweep, clearer aperture/beam labeling, and an edge spike diagnostic for deciding the next tuning step before any 4096 final review.

New files / updated outputs:

```text
run_sweep_size_precomp.py
docs/MY_TUNING_RUNBOOK.md
edge_spike_diagnostic.png in every new run artifact folder
summary.csv in the size precomp sweep root
```

Smoke test run completed:

```powershell
python run_one.py --n 512 --iterations 2 --target industrial_logistic --method wgs
```

Smoke output:

```text
artifacts\20260425-231830\wgs_industrial_logistic_quadratic
```

Size precomp sweep run completed:

```powershell
python run_sweep_size_precomp.py --n 2048 --iterations 80
```

Sweep output:

```text
artifacts\size_precomp\20260425-231857
artifacts\size_precomp\20260425-231857\summary.csv
```

Fixed sweep settings:

```text
method                         wgs
target                         industrial_logistic
phase_init                     quadratic
transition_width_13_90_x_um    12
transition_width_13_90_y_um    16
mraf_factor                    0.5
iterations                     80
target_size_50_x_um            326, 328, 330
target_size_50_y_um            116, 118, 120
```

Sorted summary, ranked by output 50% size closeness to 330 x 120, then `rms_90`, then center-profile std sum. Variants with `nan` size are treated as failed size-crossing cases and moved to the bottom:

```text
rank variant              target50   output50_x/y_um    output_tw_x/y_um  eff13     rms90     std_x/std_y      side_lobe_x/y
1    wgs_size50_x330_y116 330 x 116  333.849 / 119.568  16.877 / 19.726  0.842812  0.019471  0.0610 / 0.0999  0.179 / 0.110
2    wgs_size50_x326_y120 326 x 120  327.231 / 117.842  13.843 / 14.250  0.444609  0.021258  0.0632 / 0.1431  0.946 / 1.409
3    wgs_size50_x330_y120 330 x 120  333.889 / 123.246  16.818 / 20.475  0.864224  0.020766  0.0600 / 0.1083  0.164 / 0.106
4    wgs_size50_x326_y118 326 x 118  325.758 / 116.542  12.705 / 13.694  0.249189  0.030700  0.0736 / 0.1145  1.749 / 1.582
5    wgs_size50_x328_y120 328 x 120   44.769 /  20.990  13.622 /160.053  0.016771  2.329879  4.3399 / 0.7126 45.092 /32.080
6    wgs_size50_x326_y116 326 x 116  nan / nan          nan / nan        0.030847  2.406915  0.4686 / 0.4118 28.837 /17.464
7    wgs_size50_x328_y118 328 x 118  nan / nan          nan / nan        0.015754  2.973376  1.6719 / 0.4455 86.499 /54.350
8    wgs_size50_x328_y116 328 x 116  nan / nan          nan / nan        0.019712  3.165449  0.3274 / 0.9048 nan / nan
9    wgs_size50_x330_y118 330 x 118  nan / nan          nan / nan        0.016596  4.036339  0.2491 / 0.1974 nan / nan
```

Current recommendation from this sweep:

1. Use `wgs_size50_x330_y116` as the next 2048 diagnostic base if size closeness and `rms_90` are prioritized. It lands closest to 330 x 120 among valid cases: 333.85 x 119.57 um.
2. Keep `wgs_size50_x330_y120` as the high-efficiency comparison. It is slightly oversized in y but has the lowest side-lobe peaks and highest `efficiency_13p5` among valid cases.
3. Do not promote `x328` cases yet; several failed to form reliable 50% crossings under the fixed sharp-edge settings.
4. Next small parameter set should vary one knob at a time around `target_size_50_x/y = 330/116`, not run a giant sweep.

Recommended next commands:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5 --feedback-exponent 1.6 --target-size-50-x-um 330 --target-size-50-y-um 116
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.6 --feedback-exponent 2.0 --target-size-50-x-um 330 --target-size-50-y-um 116
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 14 --transition-width-13-90-y-um 18 --mraf-factor 0.5 --feedback-exponent 2.0 --target-size-50-x-um 330 --target-size-50-y-um 116
```

Do not run 4096 yet. First inspect `edge_spike_diagnostic.png` for `wgs_size50_x330_y116` and `wgs_size50_x330_y120`, then decide whether the next change should be feedback exponent, MRAF factor, or slightly wider transition.

## 2026-04-26 Single-Knob Ripple / Spike Check

External interpretation used for this pass:

```text
MRAF can leak energy into the noise/free region by design.
Sharp top-hat edges can create ringing/fringing.
Do not force all outside background to zero, because that can damage MRAF signal-region fidelity.
```

The size precomp sweep is now treated only as size calibration. The base case is selected strictly by `output_size_50_x/y` closeness to 330 x 120, not by ripple or side-lobe metrics:

```text
base case: artifacts\size_precomp\20260425-231857\wgs_size50_x330_y116
target_size_50_x/y_um: 330 / 116
output_size_50_x/y_um: 333.849 / 119.568
size error |x-330|+|y-120|: 4.281 um
```

Four single-variable 2048 tests were run around that base. No size-precomp expansion and no 4096 run were performed.

Run root:

```text
artifacts\single_knob_20260426-0000
artifacts\single_knob_20260426-0000\summary_single_knob.csv
artifacts\single_knob_20260426-0000\edge_spike_montage.png
artifacts\single_knob_20260426-0000\center_profile_montage.png
```

Commands:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 14 --transition-width-13-90-y-um 18 --mraf-factor 0.5 --target-size-50-x-um 330 --target-size-50-y-um 116 --out-root artifacts\single_knob_20260426-0000 --variant-name transition_14_18
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5 --feedback-exponent 0.8 --target-size-50-x-um 330 --target-size-50-y-um 116 --out-root artifacts\single_knob_20260426-0000 --variant-name feedback_exp_08
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.4 --target-size-50-x-um 330 --target-size-50-y-um 116 --out-root artifacts\single_knob_20260426-0000 --variant-name mraf_04
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.6 --target-size-50-x-um 330 --target-size-50-y-um 116 --out-root artifacts\single_knob_20260426-0000 --variant-name mraf_06
```

Comparison:

```text
case                      output50_x/y    output_tw_x/y   rms90     std_x/std_y      side_peak_x/y   side_dist_x/y
base_size_precomp_x330_y116 333.849/119.568 16.877/19.726 0.019471 0.0610/0.0999 0.1789/0.1100 25.203/28.634
transition_14_18             nan/nan         nan/nan       3.169267 5.0046/0.0564 23.882/3.531  62.146/109.410
feedback_exp_08              333.624/119.330 17.597/21.832 0.021443 0.0651/0.1059 0.1353/0.1008 74.679/1.868
mraf_04                      334.950/120.079 18.829/21.659 0.018981 0.0585/0.1018 0.1186/0.0967 0.635/1.879
mraf_06                       52.596/22.545  14.508/17.557 4.349864 1.1737/0.2915 35.651/56.395 186.967/79.296
```

Visual read from `edge_spike_diagnostic.png` and `center_profiles_raw_norm.png` montages:

```text
transition_14_18: failed size crossing and severe x-profile blow-up. Reject.
feedback_exp_08: valid size, slightly weaker outside side-lobe peaks than base, but platform ripple is not visibly better and rms_90 is slightly worse.
mraf_04: best result in this set. The far outside spike is visibly reduced; side-lobe peaks drop from 0.179/0.110 to 0.119/0.097. Platform periodic ripple is not visibly worse and x std improves slightly.
mraf_06: unstable / invalid output. Reject.
```

Decision:

```text
Do not implement weak dark guard band yet.
Reason: the required condition was not met; mraf_factor=0.4 gives a clear enough side-spike reduction without adding a new target/noise constraint.
Next candidate: target_size_50_x/y = 330/116, transition = 12/16, feedback_exponent = 2.0, mraf_factor = 0.4.
```

Recommended next command, still 2048 only:

```powershell
python run_one.py --n 2048 --iterations 100 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.4 --feedback-exponent 2.0 --target-size-50-x-um 330 --target-size-50-y-um 116
```

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
