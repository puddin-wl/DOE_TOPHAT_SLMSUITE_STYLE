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
