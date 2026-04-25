# My DOE Tuning Runbook

This runbook is for practical DOE tuning in this repository. It is intentionally detailed so future runs can be adjusted, inspected, and compared without changing the core solver or inventing a new algorithm.

## 1. Current Physical Model

The current model is fixed unless there is a deliberate optical-system change:

- Wavelength: 532 nm.
- Focal length: 429 mm.
- DOE-to-lens propagation distance: 200 mm.
- DOE clear aperture: 15 mm diameter circular aperture.
- Lens pupil: 15 mm diameter circular pupil.
- Input illumination: 5 mm intensity 1/e^2 Gaussian diameter.
- Target type: `industrial_logistic`.
- Target nominal 50% intensity size: 330 um x 120 um.
- Aperture outside amplitude: exactly 0.
- Aperture inside amplitude: Gaussian, not uniform.
- Solver phase: continuous phase over the 15 mm DOE clear aperture.

The forward model is:

```text
DOE field = Gaussian input amplitude * aperture mask * exp(i * phase)
DOE plane -> 200 mm angular spectrum propagation -> lens/pupil -> focused FFT plane
```

PowerShell smoke test:

```powershell
python run_one.py --n 512 --iterations 2 --target industrial_logistic --method wgs
```

## 2. 5 mm Gaussian Beam vs 15 mm DOE Aperture

The 15 mm number is the DOE clear aperture, not the input beam diameter. The code computes phase over the 15 mm usable DOE aperture, but the illumination inside that aperture is a 5 mm 1/e^2 intensity Gaussian.

That means the central area receives strong illumination, the aperture edge is physically available but weakly illuminated, outside the 15 mm aperture amplitude is zero, and inside the aperture amplitude is not a top-hat. The FFT compute window can be larger than 15 mm; that is numerical sampling, not physical DOE size.

When reading plots, `phase.png` shows phase inside the 15 mm aperture, `phase_with_beam_overlay.png` overlays the 5 mm and 15 mm circles, and `input_amplitude.png` / `input_intensity.png` show the Gaussian clipping directly.

PowerShell command to inspect latest config:

```powershell
Get-ChildItem artifacts -Recurse -Filter config.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content
```

## 3. Main Parameters

### Grid and Runtime

- `--n`: numerical grid size. Use 512 for smoke tests, 2048 for tuning, and only later 4096 for final review.
- `--focus-sampling-um`: focal-plane sampling. Current default is 2.5 um.
- `--iterations`: iterative solver iterations. Current tuning uses 80 for small sweeps.
- `--seed`: fixed seed for comparable runs.

Example 2048 single run:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5
```

### Target Size

- `--target-size-50-x-um`: x-axis target size at 50% intensity.
- `--target-size-50-y-um`: y-axis target size at 50% intensity.

Important: 330 um x 120 um is the desired output 50% intensity size, not a hard ROI. The `industrial_logistic` target is smooth and its 50% contour is the nominal rectangle size.

Small size precomp sweep command:

```powershell
python run_sweep_size_precomp.py --n 2048 --iterations 80
```

Optional fixed output directory:

```powershell
python run_sweep_size_precomp.py --n 2048 --iterations 80 --out-root artifacts\size_precomp_manual
```

### Edge Transition

- `--transition-width-13-90-x-um`: x edge distance between 90% and 13.5% intensity.
- `--transition-width-13-90-y-um`: y edge distance between 90% and 13.5% intensity.
- Smaller values produce sharper requested edges but often increase ringing and side lobes.
- Larger values reduce edge stress but may produce a softer output and larger measured transition.

Current fixed size precomp values:

```text
x transition = 12 um
y transition = 16 um
```

### MRAF and WGS

- `--method wgs`: uses WGS-style feedback plus an MRAF-like focal constraint.
- `--mraf-factor`: controls how much existing field is retained in the noise/free region. `0.5` is the current fixed tuning value.
- `--feedback-exponent`: WGS feedback strength. Default is `2.0`.
- `--target-power-fraction`: optional power allocation into the finite target; leave unset unless specifically diagnosing efficiency/size behavior.

Command to test a lower feedback exponent after size precomp:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5 --feedback-exponent 1.6 --target-size-50-x-um 328 --target-size-50-y-um 118
```

### Tail-to-Free

- `--tail-to-free`: adds a controlled tail from the 13.5% finite boundary down to a lower free boundary.
- `--tail-end-intensity`: tail endpoint intensity, default `0.03`.
- `--tail-width-um`: tail width, default `12`.

Do not enable this by default. Use it only when the 13.5% boundary appears too abrupt or the edge spike diagnostic shows repeated narrow peaks right at the free boundary.

Tail diagnostic command:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5 --target-size-50-x-um 328 --target-size-50-y-um 118 --tail-to-free --tail-end-intensity 0.03 --tail-width-um 12
```

## 4. Recommended Tuning Order

Do not start with a huge sweep. The goal is to learn which knob causes which output change.

### Step 1: Smoke Test

```powershell
python run_one.py --n 512 --iterations 2 --target industrial_logistic --method wgs
```

### Step 2: Small Size Precomp Sweep

```powershell
python run_sweep_size_precomp.py --n 2048 --iterations 80
```

Open the latest summary:

```powershell
Get-ChildItem artifacts\size_precomp -Recurse -Filter summary.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content
```

Sort by closeness to output 330 x 120 and then by flatness:

```powershell
$s = Get-ChildItem artifacts\size_precomp -Recurse -Filter summary.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Import-Csv $s.FullName | Sort-Object @{Expression={[math]::Abs([double]$_.output_size_50_x_um-330)+[math]::Abs([double]$_.output_size_50_y_um-120)}}, @{Expression={[double]$_.rms_90}}, @{Expression={[double]$_.center_profile_std_x+[double]$_.center_profile_std_y}} | Format-Table variant,target_size_50_x_um,target_size_50_y_um,output_size_50_x_um,output_size_50_y_um,rms_90,center_profile_std_x,center_profile_std_y,side_lobe_peak_x_rel_to_core,side_lobe_peak_y_rel_to_core
```

### Step 3: Inspect Best 2-3 Variants

```powershell
explorer artifacts\size_precomp
```

Inspect `center_profiles.png`, `center_profiles_raw_norm.png`, `edge_diagnostic_profiles.png`, `edge_spike_diagnostic.png`, `focal_intensity_log.png`, and `phase_with_beam_overlay.png`.

### Step 4: Only Then Adjust One Knob

Change one parameter at a time: target precomp size, `feedback_exponent`, `mraf_factor`, transition width, or `tail_to_free`. Do not run a large Cartesian sweep before you understand the edge diagnostic.

Example single-knob feedback test:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5 --feedback-exponent 1.6 --target-size-50-x-um 328 --target-size-50-y-um 118
```

Example single-knob MRAF test:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.6 --target-size-50-x-um 328 --target-size-50-y-um 118
```

### Step 5: Defer 4096 Final Review

Do not run 4096 until the 2048 sweep and edge spike diagnostic make sense.

Future 4096 pattern, only after selecting a 2048 candidate:

```powershell
python run_one.py --n 4096 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5 --target-size-50-x-um 328 --target-size-50-y-um 118
```

## 5. How to Judge a Result

Use metrics and plots together. Do not select only by one number.

### Size Match

Primary target:

```text
output_size_50_x_um close to 330
output_size_50_y_um close to 120
```

PowerShell sorting command:

```powershell
$s = Get-ChildItem artifacts\size_precomp -Recurse -Filter summary.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Import-Csv $s.FullName | Sort-Object @{Expression={[math]::Abs([double]$_.output_size_50_x_um-330)+[math]::Abs([double]$_.output_size_50_y_um-120)}} | Format-Table variant,output_size_50_x_um,output_size_50_y_um
```

### Edge Sharpness

Check `output_transition_width_13_90_x_um` and `output_transition_width_13_90_y_um`. Smaller is sharper, but only good if side lobes and center spikes remain acceptable.

```powershell
Import-Csv $s.FullName | Sort-Object @{Expression={[double]$_.output_transition_width_13_90_x_um+[double]$_.output_transition_width_13_90_y_um}} | Format-Table variant,output_transition_width_13_90_x_um,output_transition_width_13_90_y_um,rms_90
```

### Flatness

Check `rms_90`, `center_profile_std_x`, and `center_profile_std_y`. Use `rms_90` for 2D uniformity and center profile std for line-profile ripples.

```powershell
Import-Csv $s.FullName | Sort-Object @{Expression={[double]$_.rms_90}}, @{Expression={[double]$_.center_profile_std_x+[double]$_.center_profile_std_y}} | Format-Table variant,rms_90,center_profile_std_x,center_profile_std_y
```

### Side Lobes

Check `side_lobe_peak_x_rel_to_core`, `side_lobe_peak_y_rel_to_core`, `side_lobe_distance_x_um`, and `side_lobe_distance_y_um`. Peak values are normalized to the core mean.

```powershell
Import-Csv $s.FullName | Sort-Object @{Expression={[double]$_.side_lobe_peak_x_rel_to_core+[double]$_.side_lobe_peak_y_rel_to_core}} | Format-Table variant,side_lobe_peak_x_rel_to_core,side_lobe_peak_y_rel_to_core,side_lobe_distance_x_um,side_lobe_distance_y_um
```

## 6. How to Read Each Output Plot

- `target.png`: finite target intensity. For `industrial_logistic`, the 50% contour is the requested size, not a hard rectangle.
- `masks.png`: solver regions: zero, noise/free, transition, 50%, and core.
- `input_amplitude.png`: normalized DOE-plane amplitude; it must be Gaussian, with 5 mm 1/e^2 and 15 mm aperture circles marked.
- `input_intensity.png`: normalized input intensity; at the 5 mm 1/e^2 diameter circle, intensity is about 1/e^2 of peak.
- `phase.png`: DOE phase inside the 15 mm aperture; title states that illumination is the 5 mm Gaussian.
- `phase_with_beam_overlay.png`: same phase with 5 mm beam and 15 mm aperture overlays.
- `focal_intensity.png`: linear-scale focal intensity for overall spot shape and gross asymmetry.
- `focal_intensity_log.png`: log-scale focal intensity for weak side lobes, ghosts, and far-field leakage.
- `roi_intensity.png`: intensity normalized inside the nominal 50% target area; do not judge size from this crop alone.
- `center_profiles.png`: x and y center profiles compared with target.
- `center_profiles_flatness.png`: center profiles for plateau flatness inspection.
- `center_profiles_raw_norm.png`: center profiles with threshold crossings annotated.
- `edge_diagnostic_profiles.png`: full x/y edge diagnostic with crossings, transition width, and side-lobe info.
- `edge_spike_diagnostic.png`: zoomed left/right x edges and lower/upper y edges with target profile, output profile, 90/50/13.5% lines, output 13.5% crossings, and side-lobe peak positions.

## 7. If Center Profile Has Small Spikes

Check in this order:

1. Confirm it is not just plot scaling by opening `center_profiles_raw_norm.png` and `edge_spike_diagnostic.png`.
2. Check whether the spike sits exactly at the 13.5% crossing. If yes, the finite/free boundary may be too abrupt.
3. Check `side_lobe_peak_*_rel_to_core` and distance. A nearby high side lobe means edge ringing, not core flatness failure.
4. Compare x and y. If only y spikes, avoid changing x transition first.
5. Confirm `input_amplitude.png` still shows Gaussian illumination, not uniform aperture illumination.
6. Reduce `feedback_exponent` slightly before changing many other parameters.
7. Try `tail_to_free` only after the above confirms the spike is tied to the free boundary.

Lower-feedback diagnostic command:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5 --feedback-exponent 1.6 --target-size-50-x-um 328 --target-size-50-y-um 118
```

Tail-to-free diagnostic command:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5 --target-size-50-x-um 328 --target-size-50-y-um 118 --tail-to-free --tail-end-intensity 0.03 --tail-width-um 12
```

## 8. Current Standard Commands

Smoke test:

```powershell
python run_one.py --n 512 --iterations 2 --target industrial_logistic --method wgs
```

Size precomp sweep:

```powershell
python run_sweep_size_precomp.py --n 2048 --iterations 80
```

Read latest summary:

```powershell
$s = Get-ChildItem artifacts\size_precomp -Recurse -Filter summary.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Import-Csv $s.FullName | Format-Table
```

Recommended next small diagnostic set after size precomp:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5 --feedback-exponent 1.6 --target-size-50-x-um 328 --target-size-50-y-um 118
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.6 --feedback-exponent 2.0 --target-size-50-x-um 328 --target-size-50-y-um 118
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --phase-init quadratic --transition-width-13-90-x-um 14 --transition-width-13-90-y-um 18 --mraf-factor 0.5 --feedback-exponent 2.0 --target-size-50-x-um 328 --target-size-50-y-um 118
```
