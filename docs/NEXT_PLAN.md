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
