# Core Algorithm Notes

This project is mostly a Gerchberg-Saxton phase retrieval loop with a slmsuite-style MRAF focal-plane constraint and optional computational WGS weight updates. It is a DOE design simulation only: no SLM hardware, camera feedback, calibration, LUT, or closed loop.

## Field Model

The DOE plane field is

```text
E_doe(x, y) = A_in(x, y) * exp(i * phase(x, y))
```

where

```text
A_in = Gaussian_5mm_1e2 * circular_aperture_15mm
```

The aperture outside the central 15 mm is exactly zero. The larger FFT window only provides focal-plane sampling and is not a physical DOE size.

## Forward And Backward Operators

Forward:

```text
DOE plane
  -> angular spectrum propagation by 200 mm
  -> 15 mm lens/pupil mask
  -> centered unitary FFT
  -> focal plane
```

Backward:

```text
focal plane
  -> inverse centered unitary FFT
  -> 15 mm pupil mask
  -> inverse angular spectrum propagation by 200 mm
  -> DOE plane
```

## Industrial Logistic Target

The current primary target treats 330 um x 120 um as the final 50% intensity size, not as a hard ROI or 90% boundary.

```text
dx = abs(x) - target_width_um / 2
dy = abs(y) - target_height_um / 2
d  = max(dx, dy)
```

At `d = 0`, the target intensity is 50%. The edge is monotonic logistic:

```text
I(d) = 1 / (1 + exp(d / s))
s = transition_width_13_90_um / 4.055
target_amplitude = sqrt(I)
```

Pixels with `I < 0.135` are written as `NaN`. They are the MRAF free/noise region and are not forced to zero. There is no rounded SDF, no rounded corner target, and no artificial shoulder/halo.

## MRAF Constraint

At each iteration, the current focal field is split by the target array:

```python
noise = np.isnan(target)
finite = ~noise
zero = finite & (target == 0)
signal = finite & ~zero
```

The target amplitude is converted into normalized weights:

```python
weights = nan_to_num(target, nan=0)
weights /= sqrt(sum(weights**2))
```

Then the focal-plane constraint is:

```python
phase_factor = exp(1j * angle(focal_field))

constrained[signal] = weights[signal] * phase_factor[signal]
constrained[zero] = 0
constrained[noise] = mraf_factor * focal_field[noise]
```

For the industrial target the default is:

```text
mraf_factor = 0.5
```

So the `NaN` free/noise region keeps a relaxed copy of its current complex focal field. It is not forced to zero; the factor only prevents the free field from dominating the backward phase update.

## WGS-Leonardo Update

Plain MRAF is the GS backbone. To flatten the profile, `method = "wgs"` or `"wgs-leonardo"` updates finite target weights from the simulated focal field:

```python
feedback = abs(focal_field)
feedback_signal = normalize(feedback[signal])
ratio = feedback_signal / target_weights_reference[signal]
weights[signal] *= ratio ** (-feedback_exponent)
weights = normalize(weights)
```

This is not hardware feedback. It uses only the simulated focal field in the current iteration.

## Iteration Loop

```python
phase = initial_phase()

for k in range(iterations):
    doe_field = input_amplitude * exp(1j * phase)
    focal_field = forward(doe_field)
    if method == "wgs":
        weights = update_weights_from_focal_feedback(weights, focal_field)
    focal_field = apply_mraf_constraint(focal_field, target)
    back_field = backward(focal_field)
    phase = angle(back_field)

final_field = forward(input_amplitude * exp(1j * phase))
```

The DOE plane always restores the physical input amplitude. Only phase is optimized.

The default initial phase is `quadratic`, selected after the industrial target comparison because it gave the cleanest 2048 center profiles.

## Industrial Metrics

Metrics now follow intensity thresholds rather than old ROI-only RMS:

- `size_50_x_um`, `size_50_y_um`: center-profile 50% width, target 330 um x 120 um.
- `size_13p5_x_um`, `size_13p5_y_um`: center-profile 13.5% width.
- `transition_width_13_90_x_um`, `transition_width_13_90_y_um`: average left/right edge distance from 90% to 13.5%.
- `efficiency_13p5`: power inside the finite `I_target >= 13.5%` target region.
- `rms_core`, `rms_90`, `rms_50_reference`: normalized uniformity metrics over progressively larger target-intensity regions.
