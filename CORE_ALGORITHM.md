# Core Algorithm Notes

This project is mostly a Gerchberg-Saxton phase retrieval loop with a slmsuite-style MRAF focal-plane constraint. The surrounding Python files are just grid setup, plotting, metrics, and artifact saving.

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

## Soft Target Layout

The soft rectangle uses four regions:

```text
core region:
  target amplitude = 1

soft edge:
  target amplitude = raised-cosine falloff in x and y

free/noise ring:
  target amplitude = NaN
  this region is not forced to zero

outer guard:
  target amplitude = 0
```

The important fix is that the `NaN` free region is only a finite ring around the soft target, not the whole focal plane.

## Rounded RTAD Target

The rounded RTAD target uses a signed distance field for a rounded rectangle:

```python
qx = abs(x) - (core_width / 2 - corner_radius)
qy = abs(y) - (core_height / 2 - corner_radius)
outside = sqrt(max(qx, 0)**2 + max(qy, 0)**2)
inside = min(max(qx, qy), 0)
d = outside + inside - corner_radius
```

The amplitude is:

```text
d <= 0                         A = 1
0 < d <= shoulder_width         A = shoulder_level
shoulder < d <= shoulder+fall   A = shoulder_level * 0.5 * (1 + cos(pi*t))
next noise_band                 A = NaN
far outside                     A = 0 guard by default
```

The NaN band is the MRAF free/noise region and is never forced to zero. The far outer guard exists only to prevent whole-frame energy dumping; it can be disabled with `--rounded-rtad-no-outer-zero-guard`.

## MRAF Constraint

At each iteration, the current focal field is split by the target array:

```python
noise = np.isnan(target)
finite = ~noise
zero = finite & (target == 0)
signal = finite & ~zero
```

The target amplitude is converted into normalized weights before iteration:

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

Default values:

```text
mraf_factor = 0.5
```

So the noise ring is relaxed but not zeroed. Only the outer guard region is forced to zero.

## Optional WGS-Leonardo Polish

Plain MRAF is the GS backbone. To flatten the ROI profile, the project also supports a computational WGS-Leonardo update similar to slmsuite's weighted GS path:

```python
feedback = abs(focal_field)
feedback_signal = normalize(feedback[signal])
ratio = feedback_signal / target_weights_reference[signal]
weights[signal] *= ratio ** (-feedback_exponent)
weights = normalize(weights)
```

Default:

```text
feedback_exponent = 2.0
```

This is not hardware feedback. It uses only the simulated focal field in the current iteration.

## Iteration Loop

The whole solver is:

```python
phase = initial_phase()

for k in range(iterations):
    doe_field = input_amplitude * exp(1j * phase)
    focal_field = forward(doe_field)
    if method == "wgs-leonardo":
        weights = update_weights_from_focal_feedback(weights, focal_field)
    focal_field = apply_mraf_constraint(focal_field, target)
    back_field = backward(focal_field)
    phase = angle(back_field)

final_field = forward(input_amplitude * exp(1j * phase))
```

The DOE plane always restores the physical input amplitude. Only phase is optimized.

## Why The First Version Looked Bad

The first version made every pixel outside the soft target a `NaN` free region. For a 2048 grid that meant about 99.7 percent of the focal plane was unconstrained. Some runs sent almost all power into that free region, creating a false result that had a low normalized profile standard deviation but almost no useful ROI efficiency.

The corrected version uses:

- finite soft signal target near the desired rectangle
- finite-width free/noise ring for edge relaxation
- outer zero/guard region to keep power from escaping
- comparison ranking that rejects "flat but dark" solutions using efficiency and size gates
