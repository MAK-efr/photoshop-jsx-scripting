# 实测记录（VERIFY）

环境：Photoshop **25.0.0** · Win11 26200 · i7-12700H / 16 GB / Iris Xe · 2026-11-15
方法：每条结论都跑一次 JSX，把结果写日志；"有没有效果"用导出 PNG 与基准图算**逐像素平均绝对差（MAD）**，不靠肉眼。

> 本文第 8 节记录了一次**复测翻案**：早期 4 条 ❌ 里有 3 条是**误判**（用错 ID / 走错 API），不是本机不支持。判"不可用"之前必须把"同一能力的全部表达方式"列完。

## 1. 图层体系

| 项 | 结果 | 证据 |
|---|---|---|
| 组内新增图层不自动进组 | 确认 | 激活组后 `artLayers.add()`，`group.layers.length` 仍为 **0**；`move(g, INSIDE)` 后变 **1** |
| 组套组 | **可用（有且仅有一条路）** | `move(LayerSet→LayerSet)` 四种写法全「非法参数」；`duplicate` 报「您不能把一个图层组复制到另一个图层组中」；**在父组内锚点层上 `make layerSection`（`at = targetEnum`）成功**：`P1.layers=2`、`P1>P1_inner>p1_child` 三层回读保真 |
| 剪贴蒙版 | 可用 | 导两版 PNG：白方块内 `(255,0,255)`、方块外 `(26,26,26)`，两版整体 MAD **5.10** |
| 图层蒙版 | **不可用** | 见第 4 节，7 种配方全部「程序错误」 |
| 图层复合 | 可用 | 先隐藏再 `layerComps.add` → 恢复可见 → `apply`：`apply(off)->visible=false`、`apply(on)->visible=true` |
| 智能对象 | 可用 | `newPlacedLayer` → `placedLayerEditContents` 打开内部 `SO.psb`（文档数 1→2→1） |
| PSD 往返 | 保真 | 13 层：顶层 7 条、`Outer>Inner>2 子层`、`LayerKind.GRADIENTMAP`、名称/类型/不透明度/可见性逐一相同 |

## 2. 调整层与滤镜

建层（`make AdjL` + `using.adjustmentLayer.type.<ID>`）：
**14 个成功**：curves / levels / hueSaturation / blackAndWhite / photoFilter / vibrance / exposure / colorBalance / invert / posterize / selectiveColor / channelMixer / colorLookup / **gradientMap**
**1 个失败**：`threshold` → 四种写法均「命令"建立:"当前不可用」。

### 2.1 渐变映射为什么"看起来不支持"

`stringIDToTypeID` 探测给出关键差别：

```
gradientMap       => 4302        [gradientMap / ]          ← 事件 ID
gradientMapClass  => 1197755760  [gradientMapClass / GdMp] ← 类 ID，建层要用这个
gradientMapLayer  => 4409
gradientMapAdjustment => 4410
```

用 **事件 ID** 建层 → 「命令"建立:"当前不可用」（错误信息极具误导性，像是本机阉割）；
用 **类 ID `gradientMapClass`** → `PASS A1 ... kind=LayerKind.GRADIENTMAP`。
`GdMp`（charID）同样可建。像素影响：

```
recovered.png  Sky 区（原色 C8D8FF，B−R=55）
  mean RGB = 219.00 / 219.00 / 219.00
  max|B−R| = 0        std(B−R) = 0.000
```

三通道完全相等 = 被渐变映射映射成中性灰，**不是"没报错其实没生效"**。

### 2.2 马赛克走 ActionManager

`layer.applyMosaic()` **不存在**（「不是函数」），DOM 层没有这条路。用事件 `Msc ` + 整数键 `ClSz`（`charIDToTypeID("Msc ")` = 1299407648）可跑，`PASS F1 马赛克 Msc + ClSz => applied`。量化：

```
Tile 区（380×380）
  水平相邻像素完全相同占比 = 95.9%
  垂直相邻像素完全相同占比 = 96.0%
  跳变列位置 = 11,35,59,83,107,131,155,179,203,227,251,275
  跳变间距   = 24,24,24,24,24,24,24,24,24,24
```

间距严格等于 `cellSize=24`，块内恒定 → 真马赛克，不是"模糊得像"。
注：键必须是 `ClSz` 整数，传 `UnitDouble` 会「非法参数」。

### 2.3 参数是否真的改像素（MAD 对比基准图，阈值 0.5）

```
a_curves        MAD=  29.508  EFFECT
a_levels        MAD=  18.324  EFFECT
a_huesat        MAD=   4.694  EFFECT
a_gradmap       MAD=  45.837  EFFECT
f_noise         MAD=  68.720  EFFECT
f_invert        MAD=  53.813  EFFECT
f_posterize     MAD=  39.860  EFFECT
f_highpass      MAD=  26.407  EFFECT
f_motion        MAD=  14.803  EFFECT
f_desat         MAD=  12.556  EFFECT
f_gauss         MAD=  12.251  EFFECT
f_mosaic        MAD=   8.919  EFFECT
f_unsharp       MAD=   7.868  EFFECT
f_sharpenmore   MAD=   7.496  EFFECT
f_threshold     MAD= 109.093  EFFECT
零效果清单: []
```

## 3. 文字

- 字体回读：请求 `NotoSansSC-Black` → 回读 `NotoSansSC-Black`，**匹配 true**。
- 段落文字：`TextType.PARAGRAPHTEXT` + 宽高 420×160 生效，`\r` 换行三行正常。
- 竖排：`Direction.VERTICAL` 生效（像素区域 MAD 12.99，非空）。
- 变形：`WarpStyle.ARC` + `warpBend=50` 生效（MAD 8.67）。
- **行距**：直接赋值报「文本设置为自动行距，并且没有特殊的行距值」；改为先 `ti.useAutoLeading = false` 正常。

## 4. 为什么判定"图层蒙版不可用"

失败原文（同一句）：
```
发生了常规 Photoshop 错误。该功能可能无法在这个版本的 Photoshop 中使用。
- 不能完成命令，因为程序错误。
```
已排除的变量：
1. `Mk Chnl` + `Nw` + `At=maskChannel` + `Usng=userMask/revealAll`（charID 版）
2. 同上改用 `stringIDToTypeID`（`make/channel/maskChannel/userMask/revealAll`）
3. 去掉 `At` 引用
4. 先建选区再用 `revealSelection`
5. `At` 引用改为指向目标图层 + 通道
6. `quickMaskMode = false`
7. `displayDialogs = ALL`（结果更糟：PS 弹内部错误框、无人可点，`DoJavaScriptFile` 永久阻塞，4 分钟后只能 `taskkill`）

反证：图层对象上只有 `layerMaskFeather` / `layerMaskDensity` 这类**修改**属性，DOM 里没有任何"添加蒙版"的方法。
替代方案（都已验）：剪贴蒙版、选区 + `selection.clear()` 硬擦除、组不透明度、选区羽化半透明。

## 5. 面板 / 导出

| 格式 | 结果 | 备注 |
|---|---|---|
| PNG | ✅ | **必须显式 `compression=9`**：默认值下 1080×1350 平涂卡片 **4,377,873 B**，设 9 后 **19,372 B**（同一画面，226 倍差） |
| JPG | ✅ | `quality=12`，1080×1350 → 281 KB |
| TIFF | ✅ | LZW + 保留图层 |
| PSD | ✅ | `layers=true`，13 层 2.1 MB |
| PDF | ✅ | |
| SaveForWeb PNG24 / JPG | ✅ | `exportDocument(f, ExportType.SAVEFORWEB, o)` 真写出文件 |
| WebP | ❌ | `SaveDocumentType.WEBP` 枚举直接报错、无 `WebPSaveOptions` 构造器、AM `save` + `As=WebP` 报「存储参数当前是无效的」——三条路都堵死 |

## 6. 选区 / 画布

`feather(10)` ✅（羽化边缘可量）· `contract(10)` ✅（100→80，DOM 方法正常）· `invert()` ✅ · `resizeCanvas/resizeImage/crop` ✅（600×400→300×200→crop 200×150）。

**扩展 expand 单列一条**，因为三种表达全部"能跑但结果不对"：

| 写法 | 结果 |
|---|---|
| `selection.expand(8)`（DOM） | ❌「没有这种元素」 |
| AM `Expn` + `Pxl=8` / `#Pxl` UnitDouble / Integer / Double | ⚠️ 恒得 `99,99,201,201`（只扩 1px，**与传入值无关**；传 32、80 结果一模一样） |
| AM `stringIDToTypeID("expandSelection")` | ❌「命令<未知的>当前不可用」 |
| **读 `bounds` 自己算再 `select()`** | ✅ 一次到位 `92,92,208,208`（期望值） |

对照：AM `Cntc`（收缩）同样只缩 1px（`101,101,199,199`，期望 108），而 DOM `selection.contract(10)` 是对的（100→80）。**结论：涉及九宫格几何运算优先用 DOM 方法，DOM 没有的（expand）自己算边界。**

## 7. 清单式驱动的总验收

### 7.1 `examples/manifest_full.json`（15 条顶层指令 → 13 图层）

```
SUMMARY pass=25 fail=0 layers=13 size=1080x1350
closed own doc only
docs left open=0 (应=0)
```

重开 `caps.psd` 核对（`app.open` → 遍历 → 关闭）后文本层内容可读、组结构保留、不透明度 14 精确保留、跑完不留残留文档。

### 7.2 `examples/manifest_recovered.json`（渐变映射 + 马赛克 + 三层嵌套）

```
PASS  1 bg
PASS  2 rect Sky
PASS  3 adjust gradientMap GradMap   => kind=LayerKind.GRADIENTMAP
PASS  4 image Tile                   => bounds=60,380
PASS  5 filter mosaic                => applied
PASS  8 rect InnerBar
PASS  9 text InnerTxt
PASS  7 group Inner                  => children=2
PASS 10 rect OuterBar
PASS  6 group Outer                  => children=2
PASS 11 text Note
PASS 12 text Footer
PASS 13~15 export psd / png / jpg
SUMMARY pass=15 fail=0 layers=7 size=900x1100
docs left open=0 (应=0)
```

（编号 6/7/8 交错是正常的：`T()` 进入时取号、组要等子层跑完才返回。）

产物 `recovered.psd` 回读：

```
opened recovered.psd  900x1100
mode=DocumentMode.RGB bits=EIGHT layers(top)=7
LayerKind.TEXT Footer      visible=true opacity=100
LayerKind.TEXT Note        visible=true opacity=100
[GROUP] Outer              visible=true opacity=100
    LayerKind.NORMAL OuterBar
    [GROUP] Inner
        LayerKind.TEXT InnerTxt
        LayerKind.NORMAL InnerBar
LayerKind.NORMAL Tile
LayerKind.GRADIENTMAP GradMap
LayerKind.NORMAL Sky
LayerKind.NORMAL BG
closed
```

嵌套结构、调整层类型、可见性、不透明度全部原样保留。

## 8. 复测翻案记录（4 条 ❌ → 3 条是误判）

| 原判定 | 复测结论 | 原来的错在哪 |
|---|---|---|
| 渐变映射 ❌ | **✅ 可用** | 用了事件 ID `gradientMap`(4302)，应使用类 ID `gradientMapClass`(GdMp) |
| 马赛克 ❌ | **✅ 可用** | 只试了 DOM 的 `applyMosaic`，没试 AM 事件 `Msc ` + `ClSz` |
| 组套组 ❌ | **✅ 可用** | 只试了 `move`/`duplicate`，没试"父组内锚点上 `make layerSection`" |
| 图层蒙版 ❌ | ❌ 仍不可用 | 7 种配方全部「程序错误」，DOM 无 add-mask 方法 |
| 阈值调整层 ❌ | ❌ 仍不可用 | `thresholdClass`/`Thsh`/`thresholdLayer`/curves 改 type 四条路全堵；但**像素层** `layer.threshold()` 可用（MAD 93.88） |
| WebP ❌ | ❌ 仍不可用 | 枚举/构造器/AM save 三条路全堵 |
| 矢量形状层 ❌ | ❌ 仍不可用 | `contentLayer` 报「命令<未知的>当前不可用」，带 shape 描述符亦同 |

**可复用的判断纪律**：报"不支持"之前，至少试到这几类表达——① DOM 方法 ② `make` + 类 ID ③ `make` + 事件 ID ④ AM 事件 + charID ⑤ 换父容器/锚点引用。三条误判都是死在"只试了①"。
