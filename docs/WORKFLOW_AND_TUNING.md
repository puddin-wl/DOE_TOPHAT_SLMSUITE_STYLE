# DOE_TOPHAT_SLMSUITE_STYLE Workflow And Tuning Guide

这份文档记录当前 Python DOE 设计流程、物理参数、target 定义、solver 行为、输出图和推荐调参顺序。目标是让后续调参尽量围绕可诊断的物理量进行，而不是盲目改算法。

## 1. 项目目标

本项目是连续相位 DOE 设计程序，不是 SLM 控制程序。

它不包含：

- SLM hardware 控制
- camera feedback
- calibration
- LUT
- 实验闭环

当前设计目标是在焦平面形成一个工业定义下的矩形平顶光：

```text
size_50_x = 330 um
size_50_y = 120 um
```

这里的 `330 um x 120 um` 是最终光强 profile 的 50% 强度尺寸，不是硬 ROI，不是 90% 尺寸，也不是强制边界。

中心区域要尽量平，边界要像工业矩形平顶光那样足够陡，但不能陡到产生明显规则 ringing 或旁瓣侵入有效区域。

## 2. 物理参数解释

当前默认物理参数：

```text
wavelength              = 532 nm
focal_length            = 429 mm
DOE to lens distance    = 200 mm
DOE clear aperture      = 15 mm
input Gaussian diameter = 5 mm at intensity 1/e^2
N                       = 2048 by default
focus_sampling          = 2.5 um by default
```

传播链路：

```text
DOE plane
  -> angular spectrum propagation, 200 mm
  -> lens / pupil
  -> Fourier transform to focal plane
```

FFT 计算窗口由焦平面采样决定：

```text
compute_window_mm = wavelength_mm * focal_length_mm / focus_sampling_mm
```

当 `wavelength = 532 nm`, `focal_length = 429 mm`, `focus_sampling = 2.5 um` 时：

```text
compute_window_mm ~= 91.3 mm
```

这不表示真实 DOE 有 91.3 mm。真实通光孔径仍然是中心 15 mm。FFT 窗口更大只是为了得到需要的焦平面采样，相当于在真实 DOE aperture 外做零填充。

所以：

- 15 mm 是真实 DOE clear aperture。
- 91.3 mm 是数值计算窗口。
- aperture 外 near-field amplitude 强制为 0。
- aperture 内不是 uniform top-hat，而是 5 mm Gaussian 入射振幅。

## 3. 输入光斑和 DOE 孔径的区别

入射光斑定义为 Gaussian intensity beam。

配置参数：

```text
gaussian_1e2_diameter_mm = 5
```

这个 5 mm 是强度 `I` 下降到 `1/e^2` 的直径，不是 amplitude 的 `1/e^2` 直径。

因此：

```text
w = 5 mm / 2 = 2.5 mm
I(r) = exp(-2*r^2/w^2)
A(r) = sqrt(I) = exp(-r^2/w^2)
```

DOE clear aperture：

```text
aperture_diameter_mm = 15
```

solver 实际使用的 DOE 面振幅是：

```text
A_in(x,y) = exp(-(x^2+y^2)/w^2) * circular_aperture_15mm
```

也就是说：

- 5 mm 是入射高斯光斑尺寸。
- 15 mm 是 DOE 真实通光孔径。
- phase 可以定义在整个 15 mm aperture 内。
- 但有效照明主要集中在中心 5 mm 直径附近。
- aperture 外 amplitude = 0。
- aperture 内 amplitude 仍然是 Gaussian，不是 uniform。

新增诊断图：

- `input_amplitude.png`
- `input_intensity.png`
- `phase_with_beam_overlay.png`

看图方式：

- `input_amplitude.png`：显示归一化 DOE 面输入振幅，可以看到中心亮、外侧按 Gaussian 衰减。
- `input_intensity.png`：显示归一化输入强度，在半径 2.5 mm 处应接近 `1/e^2`。
- `phase_with_beam_overlay.png`：白色圈是 5 mm 1/e^2 beam diameter，黑色虚线圈是 15 mm clear aperture。

如果 `phase.png` 看起来覆盖 15 mm，不表示入射光斑是 15 mm。它只是说明 phase mask 在 15 mm aperture 内有定义。

## 4. Target 构造

当前主 target 是：

```text
target = industrial_logistic
```

它不是 hard rectangle，也不是 rounded SDF，也不做人造 halo。

当前直角矩形距离定义：

```text
dx = abs(x) - target_width_um / 2
dy = abs(y) - target_height_um / 2
```

如果 x/y transition 相同，可以理解为：

```text
d = max(dx, dy)
I(d) = 1 / (1 + exp(d/s))
s = transition_width_13_90_um / 4.055
```

实际代码支持 x/y 分开：

```text
Ix = 1 / (1 + exp(dx/sx))
Iy = 1 / (1 + exp(dy/sy))
I_target = min(Ix, Iy)
```

这样保持直角矩形边界，不引入 rounded SDF。

`d = 0` 或 `dx = 0 / dy = 0` 对应 50% 强度边界，所以：

```text
target_width_um  = size_50_x target
target_height_um = size_50_y target
```

默认工业目标：

```text
target_width_um  = 330
target_height_um = 120
```

13.5% 是强度点：

```text
13.5% ~= exp(-2)
```

`transition_width_13_90` 定义为中心 profile 上从 90% 强度位置到 13.5% 强度位置的边缘距离。metrics 会分别给出 x/y：

```text
transition_width_13_90_x_um
transition_width_13_90_y_um
```

target intensity 和 target amplitude 的区别非常重要：

```text
I_target = desired intensity
A_target = sqrt(I_target)
```

MRAF/GS 约束的是复场振幅，不是强度，所以 solver 里使用：

```text
target_amplitude = sqrt(I_target)
```

### Finite Region 和 NaN/Free Region

target array 中：

- finite pixel：会参与焦平面振幅约束。
- NaN pixel：MRAF free/noise region，不强制为 0。

默认没有 tail 时：

```text
I_target >= 13.5% : finite constrained target
I_target < 13.5%  : NaN/free region
```

这意味着 13.5% 外侧不再强制 target amplitude，也不强制为 0。当前 focal field 在 free region 会按 `mraf_factor` 保留一部分，用来减少硬边界造成的问题。

### 可选 Finite Tail

为了诊断和缓解 13.5% 后立刻进入 NaN/free 造成的约束突变，新增：

```text
--tail-to-free
--tail-end-intensity
--tail-width-um
```

含义：

```text
I = 13.5% at 13.5% boundary
I smoothly falls to tail_end_intensity over tail_width_um
then target becomes NaN/free
```

这不是把外侧强制归零。它只是加一段很低强度的 finite target tail，tail 之后仍然是 NaN/free region。

## 5. Solver 解释

### GS

GS 是 Gerchberg-Saxton 相位恢复。

基本流程：

```text
DOE plane: use input amplitude and current phase
forward propagate to focal plane
replace focal amplitude by target amplitude
backward propagate to DOE plane
keep phase only
restore DOE input amplitude
repeat
```

GS 对 target 外侧通常会比较硬，容易产生 ringing 或能量分配问题。

### MRAF

MRAF 是 Mixed-Region Amplitude Freedom。

本项目里：

- finite target region：按 target amplitude 约束。
- NaN/free region：不按 target 约束，不强制为 0。

MRAF 关键点：

```text
NaN/free region != zero region
```

free region 是允许算法把边缘误差或噪声放到外侧，用来减少目标区域的规则 ringing。

### mraf_factor

代码中 free/noise region 的处理是：

```text
constrained[noise] = mraf_factor * focal_field[noise]
```

如果：

```text
mraf_factor = 0
```

free region 被强制为 0，这就不是我们想要的 MRAF。

如果：

```text
mraf_factor = 1
```

free region 完全保留。对当前问题，之前测试发现它会让太多能量跑进 free region，导致 `efficiency_13p5` 很差。

当前默认：

```text
mraf_factor = 0.5
```

这是一个折中：

- free region 不归零。
- free region 也不会完全主导反传相位。

### WGS-Leonardo

WGS-Leonardo 是 slmsuite 风格的 weighted GS 思路。

它不是相机反馈，而是使用当前仿真的 focal field 更新 target finite region 的权重。

直观理解：

- 某些 finite target 区域偏暗，就提高权重。
- 某些 finite target 区域偏亮，就降低权重。

当前默认：

```text
method = wgs
feedback_exponent = 2.0
```

## 6. 初始相位

支持：

```text
random
quadratic
astigmatic_quadratic
conical_like
```

### random

随机初相位。通常会引入 speckle 或 vortex 风险，不建议作为默认。

### quadratic

平滑二次相位。当前默认。

原因：

- 对当前 industrial logistic target，quadratic 在 2048 测试中给出最干净的 center profile。
- 边界外旁瓣比 astigmatic_quadratic 更可控。

### astigmatic_quadratic

x/y 强度不同的二次相位。适合当 x/y 方向能量分配明显不均衡时尝试。

### conical_like

类锥形相位。可在想改变能量铺展方式时尝试，但当前不是默认。

## 7. 主要可调参数

### `--n`

物理意义：FFT grid size。

默认值：

```text
2048
```

建议范围：

```text
512 smoke only
2048 tuning
4096 final review
```

增大后：

- 焦平面采样可以更细。
- 计算更慢，内存更多。

减小后：

- 快速验证流程。
- 结果不能作为最终判断。

### `--iterations`

物理意义：GS/MRAF/WGS 迭代次数。

默认值：

```text
50
```

建议范围：

```text
50 to 80 for tuning
```

增大后：

- 可能降低平台 ripple。
- 也可能过优化，让边界旁瓣更稳定地成形。

减小后：

- 更快。
- 可能尚未收敛。

### `--method`

默认：

```text
wgs
```

可选：

```text
gs
mraf
wgs
wgs-leonardo
```

建议：

- `gs` 只做 baseline。
- `mraf` 看 free region 基础效果。
- `wgs` 是当前主方法。

### `--phase-init`

默认：

```text
quadratic
```

建议：

- 先用 `quadratic`。
- 如果 x/y 明显不对称，再试 `astigmatic_quadratic`。
- 如果想探索更强铺展，再试 `conical_like`。

### `--mraf-factor`

默认：

```text
0.5
```

建议范围：

```text
0.4 to 0.6
```

增大后：

- free region 保留更多当前场。
- 可能减少硬约束感。
- 过大时能量容易跑进 free region，效率下降。

减小后：

- finite target 约束更强。
- 可能提高效率。
- 过小时 free region 近似被压制，边界 ringing 可能变重。

### `--transition-width-13-90-x-um`

物理意义：x 方向 target 从 90% 到 13.5% 的设计边缘宽度。

当前 sharp 推荐：

```text
12
```

建议范围：

```text
12 to 24
```

增大后：

- x 边缘更软。
- ringing 通常更容易压。
- 工业矩形边缘感觉会变弱。

减小后：

- x 边缘更陡。
- 可能更接近工业矩形边界。
- 过小时会产生旁瓣或直接收敛失败。

### `--transition-width-13-90-y-um`

物理意义：y 方向 target 从 90% 到 13.5% 的设计边缘宽度。

当前 sharp 推荐：

```text
16
```

当前 balanced 推荐：

```text
20
```

y 方向只有 120 um，通常比 x 方向更敏感。y transition 过窄时短边 ringing 会明显。

### `--target-size-50-x-um`

物理意义：目标 output 的 x 方向 50% 强度尺寸。

默认：

```text
330
```

如果 output size_50_x 偏大，可以略微减小这个 target 值做预补偿。

如果 output size_50_x 偏小，可以略微增大这个 target 值。

建议一次只改几微米。

### `--target-size-50-y-um`

物理意义：目标 output 的 y 方向 50% 强度尺寸。

默认：

```text
120
```

y 尺寸更敏感，建议每次改 1 到 3 um。

### `--corner-radius-um`

默认：

```text
0
```

当前 `industrial_logistic` target 不使用 rounded SDF，所以这个参数保留为 0。它写在配置里只是为了明确：当前流程不启用圆角 target。如果未来重新启用 rounded target，再单独实现和验证。

### `--tail-to-free`

默认：

```text
false
```

物理意义：是否在 13.5% 后增加一段低强度 finite tail，然后再进入 NaN/free region。

打开后：

- finite-to-NaN 的突变被推到更低强度处。
- 可能降低下降沿最后的小尖峰。
- 也可能改变效率或边缘宽度。

### `--tail-width-um`

默认：

```text
12
```

建议测试：

```text
8, 12, 16
```

增大后：

- finite tail 更长。
- 约束更平滑。
- 可能让边缘变宽。

减小后：

- 更接近原始直接 NaN/free。
- 小尖峰可能不变。

### `--tail-end-intensity`

默认：

```text
0.03
```

建议测试：

```text
0.03
0.01
```

数值越低：

- finite tail 约束延伸到更低强度。
- finite-to-free 的突变发生在更暗处。
- 可能降低小尖峰，也可能引入低强度外侧结构。

## 8. 推荐调参顺序

建议按这个顺序：

1. 固定 `N=2048`。
2. 固定 `iterations=50` 或 `80`。
3. 固定 `mraf_factor=0.5`。
4. 先调 `transition_width_13_90_x/y`。
5. 再做 `size_50` 预补偿。
6. 再看 `tail_to_free` 是否能压低下降沿小尖峰。
7. 最后才增加 iterations 或上 `N=4096`。

不要一开始就做大 sweep。每次只改一类参数，并同时看：

- `size_50_x/y`
- `transition_width_13_90_x/y`
- `efficiency_13p5`
- `rms_90`
- `center_profile_std_x/y`
- `side_lobe_peak_x/y_rel_to_core`
- `edge_diagnostic_profiles.png`

## 9. 当前推荐起点

### sharp candidate

```text
transition x/y = 12 / 16 um
mraf_factor    = 0.5
iterations     = 80
```

参考结果：

```text
artifact:
artifacts\transition_sweep_20260425-2052\twx12_twy16_mraf05_i80

output transition x/y = 16.8 / 20.5 um
output size_50 x/y    = 333.9 / 123.2 um
efficiency_13p5       = 0.864
rms_90                = 0.0208
```

这个候选边缘最硬，但 size_50 稍偏大，后续可以做 target size 预补偿。

### balanced candidate

```text
transition x/y = 16 / 20 um
mraf_factor    = 0.5
iterations     = 50 or 80
```

参考结果：

```text
output transition x/y = 20.1 / 22.4 um
output size_50 x/y    = 332.4 / 121.4 um
efficiency_13p5       = 0.900
rms_90                = 0.0183
```

这个候选比 sharp 稍软，但效率更高，整体更稳。

## 10. 每张输出图怎么看

### `target.png`

显示 finite constrained target intensity。NaN/free region 不显示为有效 target。

用来看：

- target 是否是直角矩形 logistic。
- tail_to_free 打开后，13.5% 外是否有低强度 finite tail。

### `masks.png`

显示 target mask 区域：

- noise/free region
- transition region
- 50% region
- core region

用来看 NaN/free region 是否合理。

### `input_amplitude.png`

显示 DOE 面输入振幅，按最大值归一化。

用来看 5 mm Gaussian 是否在中心，而不是 15 mm uniform。

### `input_intensity.png`

显示 DOE 面输入强度，按最大值归一化。

在半径 2.5 mm 附近，强度应接近 `1/e^2`。

### `phase.png`

显示 15 mm clear aperture 内的 DOE phase。

注意：phase 定义在 15 mm aperture 内，不代表入射光斑是 15 mm。真实有效照明主要来自中心 5 mm Gaussian。

### `phase_with_beam_overlay.png`

显示 phase，并叠加：

- 5 mm 1/e^2 beam diameter 圈
- 15 mm DOE clear aperture 圈

这是判断 phase 区域和实际入射光斑关系的主图。

### `focal_intensity.png`

焦平面线性强度图。

用来看主光斑形状、边缘和明显外侧 ghost。

### `focal_intensity_log.png`

焦平面 log 强度图。

用来看低强度旁瓣、ghost 和外侧能量泄露。

### `center_profiles_raw_norm.png`

显示 x/y 中心线 profile，归一化到高强度 core mean。

它标出：

- 90% 水平线
- 50% 水平线
- 13.5% 水平线
- 各阈值交点
- size_90
- size_50
- size_13.5
- transition width

不要用平滑曲线掩盖真实振荡。这个图显示原始采样 profile。

### `center_profiles_flatness.png`

用于看中心平台 flatness 和规则 ripple。

重点看：

- 平台内是否有周期性波动。
- x/y 哪个方向更差。
- 边界附近是否有 overshoot。

### `edge_diagnostic_profiles.png`

专门诊断下降沿和小尖峰。

它显示：

- actual intensity profile
- target intensity profile
- 90%, 50%, 13.5% 水平线
- finite-to-NaN/free region 位置
- side-lobe peak 标记

如果下降沿最后有对称小尖峰，优先看这张图。

### `roi_intensity.png`

显示 50% 尺寸参考区域内的归一化强度。

用来看平台面内二维均匀性，不只看中心线。

## 11. Metrics 怎么看

### `size_50_x_um`, `size_50_y_um`

实际 output 中心 profile 的 50% 强度尺寸。

目标：

```text
330 x 120 um
```

### `size_13p5_x_um`, `size_13p5_y_um`

实际 output 中心 profile 的 13.5% 强度尺寸。

配合 `size_90` 可以判断边缘宽度。

### `transition_width_13_90_x_um`, `transition_width_13_90_y_um`

实际 output 的 13.5% 到 90% 边缘距离。

无前缀字段默认表示 output。

### `target_transition_width_13_90_x/y_um`

target 本身的设计边缘宽度。

用来判断边缘宽是 target 设得宽，还是传播/优化后变宽。

### `output_transition_width_13_90_x/y_um`

实际焦平面输出的边缘宽度。

### `efficiency_13p5`

落在 target finite 13.5% 区域内的能量比例。

不要只追求效率。边缘太宽时效率可能很高，但不符合工业矩形边界感觉。

### `rms_core`

高强度 core 区域的均匀性。适合看平台中心是否平。

### `rms_90`

target intensity >= 90% 区域的均匀性。当前最常用。

### `center_profile_std_x/y`

x/y 中心线在 50% 尺寸范围内的归一化标准差。

越低通常表示平台越平，但要结合图看是否存在局部尖峰。

### `side_lobe_peak_x/y`

side lobe 的原始强度峰值。

### `side_lobe_peak_x/y_rel_to_core`

side lobe 峰值相对 core mean 的强度。

这个更直观。比如：

```text
0.10
```

表示旁瓣峰约为 core mean 的 10%。

### `side_lobe_distance_x/y_um`

side lobe 峰值距离 13.5% 边界的距离。

用来判断小尖峰是贴着下降沿，还是远离主光斑的 ghost。

## 12. 常见问题

### 为什么 phase 图看起来覆盖 15 mm？

因为 DOE phase 在整个 15 mm clear aperture 内定义。15 mm 是真实 DOE 通光孔径。

### 为什么入射光斑不是 15 mm？

因为输入振幅是 5 mm 1/e^2 intensity diameter 的 Gaussian，再乘以 15 mm aperture mask。15 mm aperture 只是裁剪边界，不是 uniform illumination。

### 为什么 mraf_factor=1.0 反而很差？

因为 free region 完全保留时，太多能量可以留在 free/noise region，反传相位会被外侧场主导，导致目标区域效率很低。

### 为什么 transition 太窄会有 ringing？

边缘越陡，高频越多。当前系统衍射尺度约：

```text
lambda * f / D ~= 532 nm * 429 mm / 15 mm ~= 15.2 um
```

所以 4 到 6 um 的边缘宽度对这个系统大概率不现实。

### 为什么 transition 太宽会不像工业矩形边缘？

边缘太软时，50% 尺寸仍然可以对，但 90% 到 13.5% 的下降距离很长，看起来像柔和光斑，不像矩形平顶 DOE。

### 为什么 size_50 会比 target 稍大？

传播、有限 aperture、WGS 权重、MRAF free region 都会改变最终 profile。target 的 50% 尺寸不一定等于 output 的 50% 尺寸。

### 为什么要做 target size 预补偿？

如果某组参数稳定地产生：

```text
output_size_50_x > 330
output_size_50_y > 120
```

可以把 target size 稍微设小，让 output 回到目标值。这个叫 size_50 预补偿。

## 13. 常用命令

### 创建环境

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 512 smoke test

```powershell
python run_one.py --n 512 --iterations 2 --target industrial_logistic --method wgs
```

### 2048 单次运行

sharp candidate:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5
```

balanced candidate:

```powershell
python run_one.py --n 2048 --iterations 50 --method wgs --target industrial_logistic --transition-width-13-90-x-um 16 --transition-width-13-90-y-um 20 --mraf-factor 0.5
```

### Transition sweep

```powershell
python run_one.py --n 2048 --iterations 50 --method wgs --target industrial_logistic --transition-width-13-90-um 16 --variant-name tw16
python run_one.py --n 2048 --iterations 50 --method wgs --target industrial_logistic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --variant-name twx12_twy16
python run_one.py --n 2048 --iterations 50 --method wgs --target industrial_logistic --transition-width-13-90-x-um 16 --transition-width-13-90-y-um 20 --variant-name twx16_twy20
python run_one.py --n 2048 --iterations 50 --method wgs --target industrial_logistic --transition-width-13-90-x-um 20 --transition-width-13-90-y-um 24 --variant-name twx20_twy24
```

### Size compensation test

如果 sharp candidate 输出偏大，可以试：

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --target-size-50-x-um 326 --target-size-50-y-um 117 --variant-name sharp_size_comp_326x117
```

### Tail-to-free test

baseline:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5 --variant-name tail_baseline_false
```

tail 3%:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5 --tail-to-free --tail-end-intensity 0.03 --tail-width-um 12 --variant-name tail_003_w12
```

tail 1%:

```powershell
python run_one.py --n 2048 --iterations 80 --method wgs --target industrial_logistic --transition-width-13-90-x-um 12 --transition-width-13-90-y-um 16 --mraf-factor 0.5 --tail-to-free --tail-end-intensity 0.01 --tail-width-um 12 --variant-name tail_001_w12
```

### 打开 artifact 位置

运行后终端会打印：

```text
saved: artifacts\YYYYMMDD-HHMMSS\variant_name
```

在文件资源管理器中打开：

```powershell
explorer artifacts
```

重点先看：

```text
center_profiles_raw_norm.png
edge_diagnostic_profiles.png
phase_with_beam_overlay.png
metrics.json
```
