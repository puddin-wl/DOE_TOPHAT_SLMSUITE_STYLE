# Next Plan: Smoother Descending Edge Target

Date: 2026-04-26

Goal: test a small RTAD-style descending edge interface before any 4096 run.

Plan:
1. Keep the physical model unchanged: 532 nm, 429 mm focal length, 200 mm DOE-to-lens distance, 15 mm clear aperture, 5 mm 1/e^2 Gaussian illumination.
2. Keep base tuning fixed: method=wgs, target=industrial_logistic, phase_init=quadratic, target_size_50=330 x 116 um, transition=12/16 um, mraf_factor=0.4, feedback_exponent=2.0.
3. Add explicit descending-edge target parameters that extend the finite target outside the 13.5% crossing with a smooth low-intensity tail while keeping the outside region NaN/free.
4. Preserve legacy tail_to_free behavior as an alias, but document the new descending-edge interface as preferred.
5. Run only three small 2048 single-variable tests: descending edge tail width 20, 40, 60 um.
6. Judge results with derivative-based side-lobe metrics and plateau flatness, not old outside maximum alone.
7. Do not run 4096 and do not expand size precomp.

Outcome of first implementation:

- The explicit `descending_edge_mode=raised_cosine` interface was added and smoke-tested.
- A three-case 2048 test with widths 20, 40, 60 um was run.
- Width 20 remained size-valid but worsened `rms_90` and introduced derivative-detected side lobes.
- Widths 40 and 60 were unstable and collapsed output size.
- Keep the interface for future controlled experiments, but do not use it as the current best recipe.
- Current best remains `descending_edge_mode=none`, `mraf_factor=0.4`, `target_size_50=330 x 116 um`, `transition=12/16`.

## Next Plan: Derivative Side-Lobe Sensitivity Re-Analysis

Date: 2026-04-26

Scope:
- Do not run new DOE simulations.
- Do not run 4096.
- Stop raised-cosine descending-edge sweep.
- Re-analyze existing artifacts only.

Cases:
1. `artifacts/size_precomp/20260425-231857/wgs_size50_x330_y116` as `base_size_precomp_x330_y116`.
2. `artifacts/single_knob_20260426-0000/feedback_exp_08`.
3. `artifacts/single_knob_20260426-0000/mraf_04`.
4. `artifacts/single_knob_20260426-0000/mraf_06` as reject control.

Sensitivity grid:
- `side_lobe_smoothing_sigma_um = [2.5, 5.0, 7.5]`
- `side_lobe_prominence_threshold = [0.01, 0.02, 0.03]`
- `side_lobe_crossing_margin_um = [2.5, 5.0]`

Outputs:
- `summary_lobe_sensitivity.csv`
- Compare first and strongest derivative side-lobe peaks per case and setting.
- Keep `outside_max` as reference only.
- Decide whether `mraf_04` no-detected-lobe result is robust or only caused by the prominence threshold.

## Next Plan: MRAF Fine Sweep

Date: 2026-04-26

Scope:
- Run a small 2048-only DOE sweep.
- Do not run 4096.
- Do not continue descending-edge tests.
- Do not implement guard band.

Fixed parameters:
- `n=2048`
- `iterations=100`
- `method=wgs`
- `target=industrial_logistic`
- `phase_init=quadratic`
- `target_size_50_x/y=330/116 um`
- `transition_width_13_90_x/y=12/16 um`
- `feedback_exponent=2.0`
- `descending_edge_mode=none`

Sweep:
- `mraf_factor = [0.35, 0.375, 0.40, 0.425, 0.45]`

Outputs:
- `artifacts/mraf_fine_<timestamp>/summary_mraf_fine.csv`
- `edge_spike_mraf_fine_montage.png`
- `center_profile_mraf_fine_montage.png`
- `derivative_lobe_mraf_fine_montage.png` if practical.

Selection reporting:
1. Closest output size to 330 x 120.
2. Lowest `rms_90`.
3. Lowest derivative side-lobe.
4. Recommended next base case.

## Next Plan: Outside-Peak Detection and Target Definition Audit

Date: 2026-04-26

Scope:
- Do not run new DOE sweeps.
- Do not run 4096.
- Do not enable descending edge.
- Do not change transition, feedback exponent, or guard band behavior.
- Fix diagnostic logic and audit target definitions only.

Tasks:
1. Convert left/right profile sides into an outward coordinate measured away from the 13.5% target edge.
2. Detect true outside intensity peaks where dI/ds changes from positive to negative in outward coordinate.
3. Add first/strongest outside peak metrics and detection count.
4. Update edge diagnostic montage markers to show true outside intensity peaks.
5. Audit industrial_logistic defaults: free_region_threshold_intensity, descending_edge_mode, tail_to_free, descending_edge end/width.
6. Document that industrial_logistic uses min(ix, iy), i.e. a soft-edged rectangle, not a rounded-rectangle signed-distance target.

## Next Plan: industrial_rounded_logistic Target Preview

Date: 2026-04-26

Scope:
- Freeze current best recipe: `mraf_factor=0.40`, `target=industrial_logistic`, no new DOE solve.
- Do not run sweeps.
- Do not run 4096.
- Do not change MRAF factor, feedback exponent, transition, guard band, or legacy descending-edge behavior.
- Add a candidate target definition and target-only visualization.

Tasks:
1. Add `industrial_rounded_logistic` target using rounded-rectangle signed distance field.
2. Keep `target_size_50_x/y_um` as the 50% FWHM dimensions.
3. Keep transition width parameters as 13.5%-90% edge controls.
4. Add controlled tail parameters below 13.5% for the new rounded target only.
5. Preserve existing `industrial_logistic` behavior.
6. Add `preview_targets.py` to render target intensity, center profiles, threshold crossings, and region masks without running `solve_phase`.

## Next Plan: Single Rounded Target Validation

Date: 2026-04-26

Scope:
- Run exactly one new 2048 DOE case: `target=industrial_rounded_logistic`.
- Do not sweep.
- Do not run 4096.
- Do not change `mraf_factor=0.40` or `feedback_exponent=2.0`.
- Do not enable legacy descending edge or guard band.
- Compare against frozen best `industrial_logistic + mraf_factor=0.40`.

Pre-run confirmations:
1. `run_one.py` supports `target=industrial_rounded_logistic`.
2. `controlled_tail_end_intensity` and `controlled_tail_width_um` are serialized in `config.json`.
3. Target preview center profiles preserve 50% size and 13.5%-90% transition intent.

Run:
- `variant_name=rounded_logistic_single`
- fixed recipe from frozen best except target type.

## Next Plan: industrial_rounded_logistic Shape Diagnosis

Date: 2026-04-26

Scope:
- Do not run new DOE solve_phase.
- Do not sweep.
- Do not run 4096.
- Do not change frozen best recipe, MRAF factor, feedback exponent, descending edge, or guard band.
- Analyze target shape and existing frozen/rounded outputs only.

Tasks:
1. Inspect `industrial_rounded_logistic` SDF, corner radius, controlled tail defaults, effective threshold crossings, and derivative continuity.
2. Generate target-only diagnostic plots for rounded target profiles, derivatives, overlay, and region masks.
3. Read existing frozen best and rounded single-case artifacts only; generate output profile comparison plots and montage.
4. Write `diagnosis_summary.json` with mechanism explanations.
5. Update `RESULTS.md` with an explanation-only section, not an optimization recommendation.

## Next Plan: Smooth-Tail Rounded Target Preview

Date: 2026-04-26

Scope:
- Do not run solve_phase.
- Do not sweep.
- Do not run 4096.
- Do not change frozen best recipe, MRAF factor, feedback exponent, descending edge, or guard band behavior.
- Add a target-only candidate and diagnostics only.

Tasks:
1. Add `industrial_rounded_logistic_smooth_tail` while preserving existing targets.
2. Keep rounded-rectangle SDF geometry and preserve 50% FWHM target sizing.
3. Keep transition width parameters as nominal 13.5%-90% controls.
4. Add x/y controlled tail width parameters with defaults x=2*transition_x and y=1*transition_y.
5. Implement a Hermite smooth tail that matches intensity and slope at 13.5% and ends near zero slope at the tail end.
6. Extend CLI and target preview/diagnosis paths for target-only validation.
7. Generate target-only plots and `diagnosis_summary_smooth_tail.json` without reading or running a new DOE solve.
8. Update `RESULTS.md` to record smooth-tail as a candidate target only.

## Next Plan: Smooth-Tail Single-Case Validation

Date: 2026-04-26

Scope:
- Run exactly one 2048 DOE solve: `target=industrial_rounded_logistic_smooth_tail`.
- Do not sweep.
- Do not run 4096.
- Do not change frozen best recipe, MRAF factor, feedback exponent, descending edge, or guard band behavior.
- Compare the new smooth-tail single case against existing frozen best and old rounded single artifacts only.

Fixed run:
- `n=2048`
- `iterations=100`
- `method=wgs`
- `phase_init=quadratic`
- `target_size_50_x/y=330/116 um`
- `transition_width_13_90_x/y=12/16 um`
- `mraf_factor=0.40`
- `feedback_exponent=2.0`
- `descending_edge_mode=none`
- `controlled_tail_end_intensity=0.03`
- `controlled_tail_width_x/y=24/16 um`

Outputs:
1. Save normal single-case artifacts under `artifacts/smooth_tail_single_<timestamp>/smooth_tail_single`.
2. Generate `compare_frozen_rounded_smooth_tail.csv` from existing metrics plus the new single case.
3. Generate profile, edge-spike, and focal-intensity three-way comparison plots.
4. Update `RESULTS.md` with validation results while keeping frozen best as baseline.

## Next Plan: Smooth-Tail Failure Postmortem

Date: 2026-04-26

Scope:
- Do not run solve_phase.
- Do not sweep.
- Do not run 4096.
- Do not change frozen best recipe, MRAF factor, feedback exponent, descending edge, guard band, or target definitions.
- Analyze existing artifacts and source code only.

Objects:
1. Frozen best: `artifacts/mraf_fine_20260426-025728/mraf_0p400`.
2. Old rounded single: `artifacts/rounded_logistic_single_20260426/rounded_logistic_single`.
3. Failed smooth-tail single: `artifacts/smooth_tail_single_20260426-211623/smooth_tail_single`.

Tasks:
1. Compare target masks, finite/core/transition/tail/free areas, target intensity sums, and invalid-value flags.
2. Review `src/mraf.py`, `src/targets.py`, and `src/config.py` for NaN handling, finite-pixel constraints, WGS feedback, floors/clipping, and low-intensity-tail risk.
3. Inspect failed smooth-tail artifacts: config, metrics, focal intensity, target amplitude, phase, peak location, and central energy concentration.
4. Generate visual evidence showing central-spot collapse and target mask/power differences.
5. Write `postmortem_summary.json` and update `RESULTS.md` without recommending smooth-tail sweeps.

## Next Plan: Weak-Tail / Mask-Weighted WGS Preparation

Date: 2026-04-26

Current baseline:
- Frozen best remains `industrial_logistic + method=wgs + mraf_factor=0.40 + feedback_exponent=2.0 + descending_edge_mode=none`.
- Do not replace the baseline in this task.

Scope:
- Do not run solve_phase.
- Do not sweep.
- Do not run 4096.
- Do not enable descending_edge.
- Do not add guard band.
- Do not change MRAF factor or feedback exponent.
- Prepare weak-tail / mask-weighted constraint code and diagnostics only.

Tasks:
1. Extend `TargetResult` with optional `constraint_weight` while keeping old targets backward compatible.
2. Add `industrial_rounded_logistic_weak_tail`, reusing smooth-tail geometry but assigning low weight to the 13.5%-3% tail.
3. Add config knobs for core/transition/tail constraint weights and a weight-map enable flag.
4. Modify solver plumbing so old targets with no weight map follow the exact old path, while weighted targets can weakly blend constraints and WGS feedback.
5. Add `analyze_constraint_weight_map.py` for target-only / solver-only diagnostics and `--check-only` smoke checks.
6. Generate constraint-weight diagnostics without running DOE.
7. Update `RESULTS.md` with preparation status and keep rounded/tail experiments paused until weighted solver is reviewed.

Next allowed experiment after this task:
- One single-case validation of `industrial_rounded_logistic_weak_tail`, only if diagnostics pass.

Forbidden next actions:
- Sweep.
- 4096 run.
- `descending_edge` tests.
- Guard band.
- Replacing frozen baseline.

## Next Plan: Weak-Tail Single-Case Validation

Date: 2026-04-26

Scope:
- First confirm backward compatibility for old targets and weighted behavior for `industrial_rounded_logistic_weak_tail`.
- If compatibility passes, run exactly one 2048 DOE solve: `target=industrial_rounded_logistic_weak_tail`.
- Do not sweep.
- Do not run 4096.
- Do not change frozen best recipe, MRAF factor, feedback exponent, descending edge, or guard band behavior.
- Do not run the failed ordinary smooth-tail finite target again.

Fixed weak-tail run:
- `n=2048`
- `iterations=100`
- `method=wgs`
- `phase_init=quadratic`
- `target_size_50_x/y=330/116 um`
- `transition_width_13_90_x/y=12/16 um`
- `mraf_factor=0.40`
- `feedback_exponent=2.0`
- `descending_edge_mode=none`
- `controlled_tail_end_intensity=0.03`
- `controlled_tail_width_x/y=24/16 um`
- `constraint weights core/transition/tail=1.0/0.7/0.1`

Failure gate:
- Stop if output collapses, `output50_x < 100`, `output50_y < 70`, `efficiency_13p5 < 0.20`, `rms_90 > 0.5`, or outside peaks appear with no rectangular shape.

Decision policy:
- Frozen best remains the current engineering baseline.
- If weak-tail fails, do not sweep weak-tail parameters; return to solver design review.
- If weak-tail forms a candidate, next step is at most one tiny weight-only single-parameter validation.

## Outcome: Weak-Tail Single-Case Validation

Date: 2026-04-26

Result:
- Compatibility check passed: old targets keep `constraint_weight=None`, and weak-tail returns a valid weight map.
- One weak-tail single case was run at 2048 / 100 iterations.
- Failure gate did not trigger: weak-tail avoided the smooth-tail central-spot collapse.
- Weak-tail is candidate only, not a replacement: output size expanded to about 402 x 137.9 um and efficiency fell to 0.6318.
- Frozen best remains `industrial_logistic + mraf_factor=0.40 + feedback_exponent=2.0 + descending_edge_mode=none`.

Next allowed step:
- At most one very small weight-only single-parameter validation, if explicitly requested.
- Candidate knob should be a weight-map knob only, not transition, MRAF factor, feedback exponent, or target size.

If weak-tail had failed, the next step would have been solver design review. Since it did not collapse but is oversized, do not sweep broadly; treat this as a candidate requiring careful weight-only review.

Still forbidden:
- Sweep.
- 4096 run.
- `descending_edge`.
- Guard band.
- Replacing the frozen baseline.
- Transition / MRAF / feedback sweeps.

## Next Plan: Weak-Tail Target-Size Precomp Single Case

Date: 2026-04-26

Scope:
- Run exactly one 2048 DOE solve for `industrial_rounded_logistic_weak_tail` with target-size precompensation.
- Do not sweep.
- Do not run 4096.
- Do not change frozen best recipe, MRAF factor, feedback exponent, transition widths, weights, descending edge, or guard band behavior.
- Do not replace the frozen baseline.

Reason:
- The first weak-tail case avoided central-spot collapse and reduced outside maxima, but output size expanded to about 402.0 x 137.9 um.
- Precompensate target size once using approximate scale factors 402/330 and 137.9/116.

Fixed precomp run:
- `n=2048`
- `iterations=100`
- `method=wgs`
- `phase_init=quadratic`
- `target=industrial_rounded_logistic_weak_tail`
- `target_size_50_x/y=271/101 um`
- `transition_width_13_90_x/y=12/16 um`
- `mraf_factor=0.40`
- `feedback_exponent=2.0`
- `descending_edge_mode=none`
- `controlled_tail_end_intensity=0.03`
- `controlled_tail_width_x/y=24/16 um`
- `constraint weights core/transition/tail=1.0/0.7/0.1`

Failure gate:
- Stop if output collapses, `output50_x < 100`, `output50_y < 70`, `efficiency_13p5 < 0.20`, `rms_90 > 0.5`, or outside peaks appear with no rectangular shape.

Decision policy:
- Frozen best remains the current engineering baseline.
- If precomp fails, stop weak-tail and return to solver/target design review.
- If precomp is only a candidate, next step is at most one tiny target-size-only correction.
- If precomp is strong, still keep frozen best until a later explicit confirmation experiment.

## Outcome: Weak-Tail Precomp Single-Case Validation

Date: 2026-04-26

Result:
- One target-size precompensated weak-tail case was run with target 271 x 101 um.
- Failure gate did not trigger; the solver did not collapse to a central spot.
- X output size corrected well to about 330.1 um.
- Y output size is too small at about 104.6 um.
- Efficiency remains low at about 0.655, below the 0.80 candidate threshold.
- Derivative outside peaks appeared in x with detection count 2.
- This is candidate only, not a strong candidate and not a replacement for frozen best.

Next allowed step:
- At most one very small target-size-only correction, if explicitly requested.
- Do not adjust MRAF factor, feedback exponent, transition widths, or weights in the next step.

If continuing, the only reasonable single correction is size-only, likely increasing target_size_50_y while keeping the rest fixed. Do not launch a size sweep.

Still forbidden:
- Sweep.
- 4096 run.
- `descending_edge`.
- Guard band.
- MRAF sweep.
- Feedback sweep.
- Transition sweep.
- Weight sweep.
- Replacing the frozen baseline.
