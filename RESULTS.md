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

## 2026-04-26 Derivative-Based Side-Lobe Metric Fix

The previous `side_lobe_peak_*` metric was risky because it simply used the maximum value outside the 13.5% crossing. That can mislabel a monotonic tail, edge shoulder, or small ripple as a side lobe. Going forward, use derivative-based side-lobe metrics for conclusions. The old max-style measurement is retained only as `outside_max_x/y_rel_to_core`; deprecated `side_lobe_peak_*` aliases point to that outside maximum only for script compatibility.

New side-lobe logic:

```text
1. Normalize x/y center profiles by core mean.
2. Smooth the profile with a Gaussian kernel.
3. Interpolate left/right or lower/upper 13.5% crossings.
4. Start searching after a small crossing margin.
5. Detect local maxima using first-derivative positive-to-negative behavior.
6. Reject tiny ripple peaks using a prominence threshold.
```

Current detection settings written into `metrics.json`:

```text
side_lobe_smoothing_sigma_um       5.0
side_lobe_smoothing_sigma_px       2.0
side_lobe_crossing_margin_um       5.0
side_lobe_prominence_threshold     0.02
```

The existing `single_knob_20260426-0000` artifacts were re-analyzed without rerunning the DOE solver. Updated files:

```text
artifacts\single_knob_20260426-0000\summary_single_knob_derivative_metrics.csv
artifacts\single_knob_20260426-0000\edge_spike_derivative_montage.png
```

Derivative-based comparison:

```text
case             output50_x/y    rms90     outside_max_x/y  strongest_deriv_xL/xR  strongest_deriv_yL/yR
base             333.849/119.568 0.019471 0.1789/0.1100    0.1593/0.1593        0.0998/0.0998
transition_14_18 nan/nan         3.169267 23.882/3.531     21.229/4.240         2.913/3.320
feedback_exp_08  333.624/119.330 0.021443 0.1353/0.0609    0.1312/0.1312        nan/nan
mraf_04          334.950/120.079 0.018981 0.0969/0.0500    nan/nan              nan/nan
mraf_06           52.596/22.545  4.349864 35.651/56.395    33.113/31.777       49.723/53.045
```

Updated interpretation:

```text
transition_14_18 remains rejected: invalid size crossing and very large derivative peaks.
feedback_exp_08 reduces outside_max compared with base, but still has x derivative peaks around 0.131 and slightly worse rms_90.
mraf_04 is still the best candidate: outside_max drops and no derivative-based local side-lobe peak exceeds the current prominence threshold on x or y.
mraf_06 remains rejected: invalid output size and very large derivative peaks.
```

The old statement that “side_lobe_peak dropped” should now be read as “outside_max dropped.” The stronger conclusion is that `mraf_factor=0.4` removes detectable derivative-based side-lobe peaks at the current smoothing/prominence settings while preserving the best `rms_90` in this small test.

## 2026-04-26 Descending-Edge RTAD-Style Smoke Sweep

Based on the RTAD / descending-edge idea from the 2025 flat-top paper, a preferred explicit interface was added:

```text
--descending-edge-mode none|raised_cosine
--descending-edge-width-um
--descending-edge-end-intensity
```

This keeps the 13.5% internal industrial-logistic target unchanged, extends a smooth low-intensity raised-cosine tail outside the 13.5% crossing, and keeps the region outside that tail as NaN/free. The old `tail_to_free` path remains available as a legacy alias.

Implementation smoke test:

```powershell
python run_one.py --n 512 --iterations 2 --method wgs --target industrial_logistic --phase-init quadratic --target-size-50-x-um 330 --target-size-50-y-um 116 --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.4 --descending-edge-mode raised_cosine --descending-edge-width-um 20 --descending-edge-end-intensity 0.03 --out-root artifacts\smoke_descending_edge --variant-name smoke_desc_edge_w20
```

Small 2048 test run, no 4096:

```powershell
python run_descending_edge_tests.py --n 2048 --iterations 80 --out-root artifacts\descending_edge_20260426-rtad
```

Outputs:

```text
artifacts\descending_edge_20260426-rtad\summary_descending_edge.csv
artifacts\descending_edge_20260426-rtad\descending_edge_montage.png
```

Comparison against current base `mraf_factor=0.4`:

```text
case          output50_x/y    output_tw_x/y  rms90     std_x/std_y    outside_max_x/y  strongest_deriv_xR/yR
base mraf0.4  334.950/120.079 18.829/21.659 0.018981 0.0585/0.1018 0.0969/0.0500    nan/nan
edge width 20 332.991/120.577 42.471/21.220 0.084324 0.1071/0.1042 0.3370/0.1898    0.3077/0.1020
edge width 40  25.499/29.676  27.361/9.862  1.707211 0.7181/0.4969 34.659/57.943   32.661/49.769
edge width 60  38.252/28.755   6.319/6.159  3.102237 1.1211/0.7620 3.991/18.358    3.543/17.440
```

Decision:

```text
The simple raised-cosine descending-edge tail is not an improvement in this configuration.
20 um remains size-valid but worsens rms_90 and creates derivative-detected side lobes.
40/60 um are unstable and collapse the output size.
Keep the interface for future controlled experiments, but do not use descending_edge_mode=raised_cosine as the current best recipe.
Current best remains: target_size_50_x/y=330/116, transition=12/16, mraf_factor=0.4, feedback_exponent=2.0, descending_edge_mode=none.
```

## 2026-04-26 Derivative Side-Lobe Sensitivity Re-Analysis

No new DOE simulation was run for this check. Existing artifacts were re-analyzed with different derivative side-lobe detection settings.

Cases:

```text
base_size_precomp_x330_y116  artifacts\size_precomp\20260425-231857\wgs_size50_x330_y116
feedback_exp_08              artifacts\single_knob_20260426-0000\feedback_exp_08
mraf_04                      artifacts\single_knob_20260426-0000\mraf_04
mraf_06                      artifacts\single_knob_20260426-0000\mraf_06
```

Sensitivity grid:

```text
side_lobe_smoothing_sigma_um       2.5, 5.0, 7.5
side_lobe_prominence_threshold     0.01, 0.02, 0.03
side_lobe_crossing_margin_um       2.5, 5.0
```

Outputs:

```text
artifacts\lobe_sensitivity_20260426\summary_lobe_sensitivity.csv
artifacts\lobe_sensitivity_20260426\summary_lobe_sensitivity_by_case.csv
```

Per-case sensitivity summary:

```text
case                         settings  detected_count_min/max  no-detect settings  strongest_peak_min/max  outside_max_x/y
base_size_precomp_x330_y116  18        4 / 4                   0                   0.0899 / 0.1734       0.1789 / 0.1100
feedback_exp_08              18        2 / 4                   0                   0.0601 / 0.1342       0.1353 / 0.0710
mraf_04                      18        0 / 4                   10                  0.0490 / 0.0942       0.0969 / 0.0623
mraf_06                      18        4 / 4                   0                   29.3616 / 55.4944     35.6509 / 56.3951
```

Answers:

```text
1. Is mraf_04 still better than base under stricter settings?
   Yes. Base always has derivative side lobes in all four directions for all 18 settings.
   mraf_04 has lower outside_max and lower derivative peaks when peaks are detected.
   Even at the strictest low-prominence settings, mraf_04 peaks top out at about 0.0942, below base's max 0.1734.

2. Is mraf_04 nan/nan a true no-local-peak result or prominence filtering?
   It is partly prominence/smoothing sensitive, not an absolute absence of any local peak.
   At sigma=5.0 or 7.5 with prominence >=0.02, no derivative side lobe is detected.
   At sigma=2.5 and/or prominence=0.01, small local peaks are detected around 0.0490 to 0.0942.
   Interpretation: mraf_04 suppresses the lobes below the nominal threshold, but weak residual local peaks exist under stricter detection.

3. Can mraf_04 be used as the next mraf fine-sweep base?
   Yes. It remains the best base for the next small sweep because it is size-valid, has the best rms_90 from the previous single-knob test, and is robustly better than base/feedback_exp_08/mraf_06 in this sensitivity check.
```

Approved next small DOE run, only after this sensitivity check:

```powershell
python run_one.py --n 2048 --iterations 100 --method wgs --target industrial_logistic --phase-init quadratic --target-size-50-x-um 330 --target-size-50-y-um 116 --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --feedback-exponent 2.0 --mraf-factor 0.35 --descending-edge-mode none
python run_one.py --n 2048 --iterations 100 --method wgs --target industrial_logistic --phase-init quadratic --target-size-50-x-um 330 --target-size-50-y-um 116 --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --feedback-exponent 2.0 --mraf-factor 0.40 --descending-edge-mode none
python run_one.py --n 2048 --iterations 100 --method wgs --target industrial_logistic --phase-init quadratic --target-size-50-x-um 330 --target-size-50-y-um 116 --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --feedback-exponent 2.0 --mraf-factor 0.45 --descending-edge-mode none
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
