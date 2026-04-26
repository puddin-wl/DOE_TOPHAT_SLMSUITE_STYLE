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

## 2026-04-26 MRAF Fine Sweep

Ran the approved small 2048-only MRAF sweep. No 4096 run, no descending-edge continuation, and no guard band implementation.

Fixed parameters:

```text
n                              2048
iterations                     100
method                         wgs
target                         industrial_logistic
phase_init                     quadratic
target_size_50_x/y_um          330 / 116
transition_width_13_90_x/y_um  12 / 16
feedback_exponent              2.0
descending_edge_mode           none
```

Run:

```powershell
python run_sweep_mraf_fine.py
```

Outputs:

```text
artifacts\mraf_fine_20260426-025728\summary_mraf_fine.csv
artifacts\mraf_fine_20260426-025728\edge_spike_mraf_fine_montage.png
artifacts\mraf_fine_20260426-025728\center_profile_mraf_fine_montage.png
artifacts\mraf_fine_20260426-025728\derivative_lobe_mraf_fine_montage.png
```

Summary:

```text
mraf   output50_x/y     output_tw_x/y    eff13    rms90     std_x/std_y      outside_x/y   deriv_x/y  count
0.350  335.198/120.295  19.123/21.906   0.8887   0.018881  0.0578/0.1012   0.0927/0.0463 nan/nan    0
0.375  335.088/120.216  18.915/21.712   0.8872   0.018806  0.0580/0.1013   0.0957/0.0494 nan/nan    0
0.400  334.992/120.124  18.694/21.491   0.8852   0.018719  0.0581/0.1014   0.0997/0.0532 nan/nan    0
0.425  334.902/120.025  18.441/21.245   0.8827   0.018615  0.0581/0.1016   0.1050/0.0575 0.0941/nan 2
0.450  334.749/119.892  18.106/20.921   0.8790   0.018522  0.0583/0.1020   0.1125/0.0632 0.1001/nan 2
```

Selections requested separately:

```text
1. Closest output size to 330 x 120:
   mraf_factor = 0.45, output50 = 334.749 x 119.892 um.

2. Lowest rms_90:
   mraf_factor = 0.45, rms_90 = 0.018522.

3. Lowest derivative side-lobe:
   mraf_factor = 0.35 / 0.375 / 0.40 all have detection count 0 under the nominal derivative metric.
   Among these, 0.35 has the lowest outside_max reference: 0.0927 / 0.0463.

4. Comprehensive recommendation:
   mraf_factor = 0.40.
   It keeps derivative side-lobe detection count at 0 like 0.35/0.375, improves size and rms_90 versus 0.35/0.375, and avoids the new x-side derivative lobe that appears at 0.425/0.45.
```

Next-base decision:

```text
Use mraf_factor = 0.40 as the next base.
Do not use 0.45 as base yet: it is best for size and rms_90, but derivative side-lobe count becomes 2 and outside_max increases.
Do not use 0.35 as base unless side-lobe suppression becomes more important than size/rms; it is slightly oversized in x.
```

Target-size precomp decision:

```text
Yes, a small target_size_50_x precomp is useful before any final review.
All valid fine-sweep cases remain oversized in x by about 4.75 to 5.20 um, while y is already close to 120 um.
Recommended next small precomp around mraf_factor=0.40:
target_size_50_x_um = [325, 326, 327]
target_size_50_y_um = 116 fixed
```

Guard-band decision:

```text
Still no guard band needed.
The best balanced case has zero derivative side-lobe detections under the nominal metric, and the remaining issue is mostly x-size precomp rather than uncontrolled free-region spikes.
```

## 2026-04-26 Outside-Peak Metric And Target Definition Audit

No new DOE sweep was run for this update. The change is diagnostic-only plus target-definition documentation.

Side/outside peak detection correction:

```text
The earlier derivative-lobe fields used raw x/y coordinate direction.
That can confuse left and right edges because the outward direction is reversed at the left edge.
The corrected outside-peak metric converts each side to outward coordinate s measured away from the 13.5% crossing.
It then detects true outside intensity peaks where dI/ds changes from positive to negative.
```

New primary fields:

```text
first_outside_peak_x_rel_to_core
first_outside_peak_y_rel_to_core
strongest_outside_peak_x_rel_to_core
strongest_outside_peak_y_rel_to_core
outside_peak_detection_count
```

Legacy fields:

```text
first_side_lobe_peak_* and strongest_side_lobe_peak_* are retained for compatibility only.
Because those fields used the raw coordinate direction, the left-side detections can correspond to valleys rather than outward-coordinate peaks.
Use the outside_peak fields for decisions.
outside_max_x/y_rel_to_core is still kept as a reference-only max value, not a side-lobe definition.
```

The existing `mraf_fine_20260426-025728` artifacts were re-analyzed without rerunning DOE. The montage images now mark true outside intensity peaks.

Updated mraf fine summary under corrected outside-peak metric:

```text
mraf   output50_x/y     rms90     outside_max_x/y  outside_peak_x/y  outside_peak_count
0.350  335.198/120.295  0.018881 0.0927/0.0463    nan/nan           0
0.375  335.088/120.216  0.018806 0.0957/0.0494    nan/nan           0
0.400  334.992/120.124  0.018719 0.0997/0.0532    nan/nan           0
0.425  334.902/120.025  0.018615 0.1050/0.0575    0.0941/nan       2
0.450  334.749/119.892  0.018522 0.1125/0.0632    0.1001/nan       2
```

This correction does not change the previous practical recommendation:

```text
Use mraf_factor = 0.40 as the next base.
It has no true outside peak detections under the nominal metric, better size/rms than 0.35/0.375, and avoids the true outside x peaks appearing at 0.425/0.45.
```

Industrial logistic target audit:

```text
src/config.py default free_region_threshold_intensity = 0.135
src/config.py default descending_edge_mode = none
src/config.py default tail_to_free = false
src/config.py default descending_edge_end_intensity = 0.03
src/config.py default descending_edge_width_um = 0.0
```

With those defaults, `industrial_logistic` constrains only down to 13.5% intensity. Pixels below 13.5% become NaN/free region:

```text
base_intensity = min(ix, iy)
finite = base_intensity >= free_region_threshold_intensity
amplitude[finite] = sqrt(constrained_intensity[finite])
noise = ~finite
```

Therefore, for the current recommended recipe (`descending_edge_mode=none`, `tail_to_free=false`), 13.5% below is not controlled by the target; it is MRAF free/noise region.

Geometry note:

```text
industrial_logistic uses min(ix, iy), so it is a soft-edged rectangle with separable x/y logistic edges.
It is not a strict rounded-rectangle signed-distance target.
If a future target should match an LBTEK-style rounded rectangle, add a new industrial_rounded_logistic target instead of treating min(ix, iy) as rounded geometry.
```

## 2026-04-26 Rounded Logistic Target Preview

Current best recipe remains frozen:

```text
target                         industrial_logistic
target_size_50_x/y_um          330 / 116
transition_width_13_90_x/y_um  12 / 16
mraf_factor                    0.40
feedback_exponent              2.0
descending_edge_mode           none
tail_to_free                   false
```

No new DOE solve was run for this update. No sweep, no 4096, no guard band, and no change to current best results.

Target audit reminder:

```text
industrial_logistic uses base_intensity = min(ix, iy).
It is a soft-edged rectangle with separable x/y logistic edges, not a rounded-rectangle signed-distance target.
With free_region_threshold_intensity = 0.135, descending_edge_mode = none, and tail_to_free = false,
industrial_logistic constrains only down to 13.5%; below 13.5% is NaN/free region.
```

New candidate target added:

```text
industrial_rounded_logistic
```

Purpose:

```text
1. Use rounded-rectangle signed distance field geometry instead of min(ix, iy).
2. Keep target_size_50_x/y_um as the 50% FWHM dimensions.
3. Keep transition_width_13_90_x/y_um as 13.5%-90% edge controls.
4. Continue weak target control below 13.5% down to controlled_tail_end_intensity before entering free/noise region.
5. Reduce future outside peak / shoulder risk by combining rounded geometry with a controlled low-intensity tail.
```

New target controls:

```text
corner_radius_um                  default: min(transition_width_13_90_x_um, transition_width_13_90_y_um) when not explicitly set
controlled_tail_end_intensity     default: 0.03
controlled_tail_width_um          default: 2 * min(transition_width_13_90_x_um, transition_width_13_90_y_um)
```

Preview command, target-only and no `solve_phase`:

```powershell
python preview_targets.py --n 2048 --target-size-50-x-um 330 --target-size-50-y-um 116 --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --out-root artifacts\target_preview_rounded_20260426
```

Preview outputs:

```text
artifacts\target_preview_rounded_20260426\industrial_logistic_intensity.png
artifacts\target_preview_rounded_20260426\industrial_rounded_logistic_intensity.png
artifacts\target_preview_rounded_20260426\target_center_profile_comparison.png
artifacts\target_preview_rounded_20260426\industrial_logistic_regions.png
artifacts\target_preview_rounded_20260426\industrial_rounded_logistic_regions.png
```

Interpretation:

```text
The center x/y profiles preserve the intended 50%, 90%, and 13.5% crossings.
The rounded target changes corner geometry and adds a controlled tail region below 13.5% before free/noise.
This target is only a future candidate; it is not promoted over the frozen current best recipe until a separate small DOE test is explicitly requested.
```

## 2026-04-26 Rounded Logistic Single-Case Validation

Ran exactly one new 2048 DOE case for `industrial_rounded_logistic`. No sweep, no 4096, no guard band, no feedback/MRAF changes, and legacy descending edge remained off.

Pre-run checks:

```text
run_one.py supports target=industrial_rounded_logistic.
controlled_tail_end_intensity and controlled_tail_width_um are present in DOEConfig and serialize through config.to_dict().
Target preview center profile confirms 50% size is preserved: x=330.0 um, y=116.016 um.
Target preview effective 13.5%-90% widths with controlled tail are x=13.997 um, y=17.867 um, slightly wider than the nominal 12/16 logistic edge because the rounded target continues a controlled tail below 13.5%.
```

Run:

```powershell
python run_one.py --n 2048 --iterations 100 --method wgs --target industrial_rounded_logistic --phase-init quadratic --target-size-50-x-um 330 --target-size-50-y-um 116 --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.40 --feedback-exponent 2.0 --descending-edge-mode none --out-root artifacts\rounded_logistic_single_20260426 --variant-name rounded_logistic_single
```

Outputs:

```text
artifacts\rounded_logistic_single_20260426\rounded_logistic_single
artifacts\rounded_logistic_single_20260426\rounded_logistic_single\metrics.json
artifacts\rounded_logistic_single_20260426\rounded_logistic_single\edge_spike_diagnostic.png
artifacts\rounded_logistic_single_20260426\rounded_logistic_single\center_profiles.png
artifacts\rounded_logistic_single_20260426\rounded_logistic_single\focal_intensity.png
artifacts\rounded_logistic_single_20260426\compare_frozen_vs_rounded.csv
```

Comparison against frozen best:

```text
target                         output50_x/y    trans_x/y      rms90     eff13    std_x/std_y     outside_x/y     first_peak_x/y  strongest_peak_x/y  count
industrial_logistic             334.992/120.124 18.694/21.491 0.018719 0.8852  0.0581/0.1014  0.0997/0.0532  nan/nan         nan/nan            0
industrial_rounded_logistic     335.202/120.996 19.645/23.924 0.020215 0.8942  0.0580/0.0999  0.0800/0.0668  nan/nan         nan/nan            0
```

Conclusion by the requested rules:

```text
The rounded target has outside_peak_detection_count = 0, same as frozen best.
It lowers outside_max_x from 0.0997 to 0.0800, but outside_max_y increases from 0.0532 to 0.0668.
It increases efficiency_13p5, but output size and rms_90 are worse: y size grows to 120.996 um and rms_90 rises from 0.018719 to 0.020215.
Therefore it is a candidate, not a replacement for the frozen best.
Frozen best remains industrial_logistic + mraf_factor=0.40.
```

## 2026-04-26 industrial_rounded_logistic Shape Diagnosis

This is a target-only and result-only diagnosis. No new DOE solve was run, no sweep was added, no 4096 run was started, and the frozen best recipe remains unchanged:

```text
target = industrial_logistic
mraf_factor = 0.40
feedback_exponent = 2.0
descending_edge_mode = none
```

Diagnostic command:

```powershell
python analyze_rounded_shape.py
```

Diagnostic output:

```text
artifacts\target_shape_diagnostics_20260426-205945
artifacts\target_shape_diagnostics_20260426-205945\diagnosis_summary.json
artifacts\target_shape_diagnostics_20260426-205945\rounded_target_x_profile_with_thresholds.png
artifacts\target_shape_diagnostics_20260426-205945\rounded_target_y_profile_with_thresholds.png
artifacts\target_shape_diagnostics_20260426-205945\rounded_target_x_profile_derivatives.png
artifacts\target_shape_diagnostics_20260426-205945\rounded_target_y_profile_derivatives.png
artifacts\target_shape_diagnostics_20260426-205945\logistic_vs_rounded_profile_overlay.png
artifacts\target_shape_diagnostics_20260426-205945\rounded_target_region_masks.png
artifacts\target_shape_diagnostics_20260426-205945\output_x_profile_frozen_vs_rounded.png
artifacts\target_shape_diagnostics_20260426-205945\output_y_profile_frozen_vs_rounded.png
artifacts\target_shape_diagnostics_20260426-205945\outside_region_frozen_vs_rounded.png
artifacts\target_shape_diagnostics_20260426-205945\edge_spike_frozen_vs_rounded_montage.png
```

Target definition audit:

```text
industrial_rounded_logistic uses a rounded-rectangle signed distance field instead of base_intensity = min(ix, iy).
corner_radius_um was left at 0 in config, so the effective default is min(transition_x, transition_y) = 12 um.
controlled_tail_end_intensity = 0.03.
controlled_tail_width_um was left unset, so the effective default is 2 * min(transition_x, transition_y) = 24 um.
The target 50% profile size is preserved: x = 330.000 um, y = 116.016 um.
The effective 13.5%-90% target widths are x = 13.997 um and y = 17.867 um, wider than nominal 12/16 um.
```

Mechanism interpretation:

```text
The rounded target is still only a candidate. Its purpose is rounded geometry plus weak control below 13.5%, not immediate replacement of the frozen best.
The x outside_max reduction from 0.0997 to 0.0800 is consistent with reduced high-spatial-frequency corner content and weak tail control below the 13.5% edge.
The y outside_max increase from 0.0532 to 0.0668 is plausible because the y dimension is short; the transition and 24 um controlled tail occupy a larger fraction of the target height, so energy can spread outside the y edge.
The output50 increase and slightly worse rms_90 are also consistent with the rounded target's wider effective transition and extra low-intensity constrained tail.
The efficiency increase from 0.8852 to 0.8942 likely comes from constraining and accepting more energy in the low-intensity tail region rather than from a uniformly better plateau.
```

Two-corner / two-bend diagnosis:

```text
The target profile itself contains a two-stage edge: plateau -> main logistic transition -> controlled tail -> free/noise region.
This can create two visible bends: one around the high-intensity shoulder of the main logistic transition and another near the 13.5% handoff into the controlled tail.
The main logistic-to-tail join is not strictly C1 continuous in the current implementation; the tail-to-free boundary ends the constrained target at 3% and then becomes NaN/free.
Therefore the two platform-side angles are likely at least partly target-shape driven, not only a solve artifact.
```

Next-step note, not an optimization decision:

```text
Keep frozen best as the current baseline.
Keep industrial_rounded_logistic as a candidate.
If work continues, investigate target-shape details first, especially smoother main-to-tail continuity and y-direction tail proportion, before sweeping algorithm parameters.
Do not promote rounded target over frozen best unless it later matches or improves outside peaks, size, and rms together.
```

## 2026-04-26 Smooth-Tail Rounded Target Preview

This is target-only work. No DOE solve, no sweep, no 4096 run, no guard band, and no frozen-best recipe change were made. The frozen best remains `industrial_logistic + mraf_factor=0.40 + feedback_exponent=2.0 + descending_edge_mode=none`.

New candidate target:

```text
industrial_rounded_logistic_smooth_tail
```

Purpose:

```text
Keep rounded-rectangle SDF geometry.
Keep target_size_50_x/y_um as 50% FWHM size.
Keep transition_width_13_90_x/y_um as nominal 13.5%-90% controls.
Continue weak control below 13.5% down to controlled_tail_end_intensity = 0.03.
Replace the raised-cosine tail handoff with a Hermite-style smooth tail that matches the logistic slope at 13.5% and approaches zero slope at the tail end.
Use separate default tail widths: x = 2 * transition_x = 24 um, y = 1 * transition_y = 16 um.
```

Target-only diagnostic command:

```powershell
python analyze_rounded_shape.py --smooth-tail-only
```

Target-only diagnostic output:

```text
artifacts\target_shape_smooth_tail_20260426-210956
artifacts\target_shape_smooth_tail_20260426-210956\diagnosis_summary_smooth_tail.json
artifacts\target_shape_smooth_tail_20260426-210956\smooth_tail_target_intensity.png
artifacts\target_shape_smooth_tail_20260426-210956\smooth_tail_regions.png
artifacts\target_shape_smooth_tail_20260426-210956\smooth_tail_x_profile_with_thresholds.png
artifacts\target_shape_smooth_tail_20260426-210956\smooth_tail_y_profile_with_thresholds.png
artifacts\target_shape_smooth_tail_20260426-210956\smooth_tail_x_profile_derivatives.png
artifacts\target_shape_smooth_tail_20260426-210956\smooth_tail_y_profile_derivatives.png
artifacts\target_shape_smooth_tail_20260426-210956\logistic_vs_rounded_vs_smooth_tail_profile_overlay.png
```

Summary from `diagnosis_summary_smooth_tail.json`:

```text
corner_radius_um_used                 12.0
controlled_tail_width_x_um_used       24.0
controlled_tail_width_y_um_used       16.0
controlled_tail_end_intensity         0.03
nominal_transition_x/y_um             12.0 / 16.0
effective_transition_x/y_um           12.295 / 16.159
x_profile_50_width_um                 330.000
y_profile_50_width_um                 116.016
max_abs_slope_jump_at_13p5_x/y        0.02018 / 0.01077
```

Interpretation:

```text
The smooth-tail candidate fixes the main problem found in the previous rounded target diagnosis: the 13.5% handoff no longer intentionally resets the slope to near zero.
The effective 13.5%-90% widths are now much closer to nominal 12/16 than the previous rounded target's 13.997/17.867.
The y tail default is now 16 um instead of 24 um, reducing the target-only risk that the short y dimension is over-extended by a wide low-intensity tail.
The tail-to-free boundary is still the end of the constrained target at 3%, followed by NaN/free region; it is not an infinite continuous intensity function.
This target is only a candidate. It should not replace the frozen best unless a later explicitly requested single-case DOE validation improves outside peaks, size, and rms together.
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
