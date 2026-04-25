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
