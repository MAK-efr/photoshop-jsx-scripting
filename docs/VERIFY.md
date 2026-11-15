# 实测记录（VERIFY）

环境：Photoshop **25.0.0** · Win11 26200 · i7-12700H / 16 GB / Iris Xe · 2026-11-15
方法：每条结论都跑一次 JSX，把结果写日志；"有没有效果"用导出 PNG 与基准图算**逐像素平均绝对差（MAD）**，不靠肉眼。

> 本文第 8、9 节记录了**两轮复测翻案**：先后判成 ❌ 的 7 项里有 **6 项是误判**（用错 ID / 走错 API / 少给一层描述符），只有阈值调整层确证不可用。判"不可用"之前必须把"同一能力的全部表达方式"列完，并且**要有一个能过的对照组**。

## 1. 图层体系

| 项 | 结果 | 证据 |
|---|---|---|
| 组内新增图层不自动进组 | 确认 | 激活组后 `artLayers.add()`，`group.layers.length` 仍为 **0**；`move(g, INSIDE)` 后变 **1** |
| 组套组 | **可用（有且仅有一条路）** | `move(LayerSet→LayerSet)` 四种写法全「非法参数」；`duplicate` 报「您不能把一个图层组复制到另一个图层组中」；**在父组内锚点层上 `make layerSection`（`at = targetEnum`）成功**：`P1.layers=2`、`P1>P1_inner>p1_child` 三层回读保真 |
| 剪贴蒙版 | 可用 | 导两版 PNG：白方块内 `(255,0,255)`、方块外 `(26,26,26)`，两版整体 MAD **5.10** |
| 图层蒙版 | **可用** | `Mk`+`Nw=Chnl`+`At=Chnl/Chnl/**Msk**`+`Usng=UsrM/RvlA|HdAl|RvlS|HdSl`；三种模式全过，像素证据见第 9 节 |
| 图层复合 | 可用 | 先隐藏再 `layerComps.add` → 恢复可见 → `apply`：`apply(off)->visible=false`、`apply(on)->visible=true` |
| 智能对象 | 可用 | `newPlacedLayer` → `placedLayerEditContents` 打开内部 `SO.psb`（文档数 1→2→1） |
| PSD 往返 | 保真 | 13 层：顶层 7 条、`Outer>Inner>2 子层`、`LayerKind.GRADIENTMAP`、名称/类型/不透明度/可见性逐一相同 |

## 2. 调整层与滤镜

建层（`make AdjL` + `using.adjustmentLayer.type.<ID>`）：
**14 个成功**：curves / levels / hueSaturation / blackAndWhite / photoFilter / vibrance / exposure / colorBalance / invert / posterize / selectiveColor / channelMixer / colorLookup / **gradientMap**
**1 个失败**：`threshold` → 10 种写法（4 类 ID × putObject/putClass × 空参/Lvl/presetKind/Adjs）均「命令"建立:"当前不可用」，且同构的 curves/posterize/invert 全过（对照组），见第 9 节。

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

## 4. 图层蒙版：当时为什么误判

第一轮把它判成"不可用"，失败原文是：

```
发生了常规 Photoshop 错误。该功能可能无法在这个版本的 Photoshop 中使用。
- 不能完成命令，因为程序错误。
```

复盘后是两个叠加错误，**都不是 Photoshop 的限制**：

1. `At` 引用的第三个枚举值写成了 `stringIDToTypeID("maskChannel")`（4414，那是**类 ID**），
   正确写法是 `charIDToTypeID("Msk ")`（= stringID `"mask"`）。
2. 同一段代码里 `"Nw "`/`"At "`/`"Mk "` 都只有 3 个字符，`charIDToTypeID` 直接抛「非法参数」——
   这层异常被外层 try/catch 一起吞掉，日志里只剩最后一层报错，看起来像"命令不支持"。

正确配方与像素证据见第 9.2 节。**教训：`At` 之后跟着的枚举三元组 `(key, enumType, enumValue)` 里，
第三个必须是枚举值 charID，不能塞类 stringID。**
## 5. 面板 / 导出

| 格式 | 结果 | 备注 |
|---|---|---|
| PNG | ✅ | **必须显式 `compression=9`**：默认值下 1080×1350 平涂卡片 **4,377,873 B**，设 9 后 **19,372 B**（同一画面，226 倍差） |
| JPG | ✅ | `quality=12`，1080×1350 → 281 KB |
| TIFF | ✅ | LZW + 保留图层 |
| PSD | ✅ | `layers=true`，13 层 2.1 MB |
| PDF | ✅ | |
| SaveForWeb PNG24 / JPG | ✅ | `exportDocument(f, ExportType.SAVEFORWEB, o)` 真写出文件 |
| **WebP** | ✅ | `SaveDocumentType.WEBP` 与 `WebPSaveOptions` 都不存在（这两条路确实堵死），但 **AM `save` + `as=WebPFormat{compression,quality,...}` 可用**（PS 2022+ 原生）。实测 900×600 → 14,406 B，RIFF/WEBP 头，PIL 解码正常 |

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

## 8. 复测翻案记录（三轮共 7 条 ❌ → **7 条全是误判**）

| 原判定 | 复测结论 | 原来的错在哪 |
|---|---|---|
| 渐变映射 ❌ | **✅ 可用** | 用了事件 ID `gradientMap`(4302)，应使用类 ID `gradientMapClass`(GdMp) |
| 马赛克 ❌ | **✅ 可用** | 只试了 DOM 的 `applyMosaic`，没试 AM 事件 `Msc ` + `ClSz` |
| 组套组 ❌ | **✅ 可用** | 只试了 `move`/`duplicate`，没试"父组内锚点上 `make layerSection`" |
| 图层蒙版 ❌ | **✅ 可用** | 第三个枚举值要写 `Msk `（=stringID "mask"），不是 `maskChannel`；再叠加 3 字符 charID 的坑，就成了「程序错误」 |
| 阈值调整层 ❌ | **✅ 可用（§11 翻案）** | 类 ID 是 `thresholdClassEvent`；我试的 `thresholdClass`/`thresholdAdjustment`/`thresholdLayer`/`Thsh` 全不在名单里，10 种组合自然全灭 |
| WebP ❌ | **✅ 可用** | 只试过 `As=WebP`（charID）；正解是 `as=WebPFormat` 对象 + `compression/quality` |
| 矢量形状层 ❌ | **✅ 可用** | 之前只给了 `null` 引用 + 极简 `type`，缺 `shape`/`strokeStyle` 两层；补齐即成功 |

**可复用的判断纪律**：报"不支持"之前，至少试到这几类表达——① DOM 方法 ② `make` + 类 ID ③ `make` + 事件 ID ④ AM 事件 + charID ⑤ 换父容器/锚点引用 ⑥ **从已存在的同类对象反查 ID**（§11 就是靠 ⑥ 破的）。
三条误判都是死在"只试了①"，第四条死在"名字靠猜"——**先反查，再试**。

## 9. 第二轮复测：蒙版 / 矢量形状层 / WebP 三项翻案（2026-11-15 下午）

按网上公开配方（Adobe 社区 Paul Riggott、r-bin，Stephen Marsh，Bioticronic gist）重测，三网三中、一网仍空。

### 9.1 定位到的真凶：`charIDToTypeID` 只吃 4 个字符

抄来的代码里 `"Nw "`、`"At "`、`"Mk "` 都是 **3 字符**，函数**在构造 ActionDescriptor 阶段就抛「非法参数」**，
根本走不到 `executeAction`——所以看到的是"参数不合法"，而不是"命令不可用"，极易误判成"本机不支持"。

```
charID [Nw ] len=3  => 抛「非法参数」
charID [Nw  ] len=4 => 1316429856
charID [At ] len=3  => 抛「非法参数」
charID [At  ] len=4 => 1098129440
charID [Mk ] len=3  => 抛「非法参数」
charID [Mk  ] len=4 => 1298866208
```

### 9.2 图层蒙版：三种模式全通

```
PASS A1 revealAll(RvlA)
PASS A2 revealSelection(RvlS)
PASS A3 hideAll(HdAl) + 在蒙版上涂白
```

像素证据（导出 PNG 读 alpha 通道）：

| 用例 | 选区外 (50,50) | 选区内 (150,150) | 说明 |
|---|---|---|---|
| A2 `RvlS` | alpha **0** | alpha **255** | 选区外真透明 |
| A3 `HdAl` + 蒙版涂白 | alpha **0** | alpha **255** | 蒙版可继续编辑（`slct` 到 `Chnl/Msk ` 后 fill） |

### 9.3 矢量形状层：矩形填充 + 椭圆描边

```
PASS D1 形状层 矩形+纯色填充  => kind=LayerKind.SOLIDFILL
PASS D2 形状层 椭圆+描边      => kind=LayerKind.SOLIDFILL
```

像素证据：

| 检查点 | 实测 | 期望 |
|---|---|---|
| 矩形内 (150,125) | (200,130,47) | 探针里直接写 `Rd=200/Grn=130/Bl=47`，**完全一致**。（清单版 `C8892F` 另测：WebP 中心像素 (200,137,47)，精确） |
| 矩形边界 x=49 / 50 / 249 / 250 | 白 / 橙 / 橙 / 白 | 形状严格占 x∈[50,250) |
| 椭圆描边环 (60,150) | (0,0,0) | 6px 黑描边 |
| 椭圆内部 (150,150) | (255,255,255) | `fillEnabled=false`，内部不填 |
| 近黑像素占比 | 3.39% | 描边存在 |
| 回读 PSD 的 `pathItems.length` | 1 | 仍是矢量，未栅格化 |

### 9.4 WebP

```
PASS C1 WebP 有损 q80    => 3,366 B
PASS C2 WebP 无损        => 3,300 B
c1/c2: RIFF/WEBP 头=True  PIL 解码=WEBP size=(200,120)
```

清单驱动下（900×600 整图）：

```
PASS 9 export webp => ...
ecovered2.webp
recovered2.webp  14,406 B  header=b'RIFF'/b'WEBP'  size=(900,600)  中心像素 (200,137,47)
```

### 9.5 阈值调整层：当时判定"不可用"（**已于 §11 推翻，保留原文**）

> ⚠️ 本节结论是**错的**，保留是为了记录错误的推理过程。真正的解法见 §11：
> 类 ID 是 `thresholdClassEvent`，我试过的 4 个名字都不在其中。

同一段建层骨架，只换 class：

```
PASS CTRL_curves     => kind=LayerKind.CURVES
PASS CTRL_posterize  => kind=LayerKind.POSTERIZE
PASS CTRL_invert     => kind=LayerKind.INVERSION
FAIL V1_thresholdClass_empty      !! 命令"建立:"当前不可用
FAIL V2_ThshCharID_empty          !! 命令"建立:"当前不可用
FAIL V3_Thsh_Lvl                  !! 命令"建立:"当前不可用
FAIL V4_thClass_preset_Lvl        !! 命令"建立:"当前不可用
FAIL V5_thClass_Adjs              !! 命令"建立:"当前不可用
FAIL V6_putClass_thClass          !! 命令"建立:"当前不可用
FAIL V7_curves_then_setd          !! 命令"设置"当前不可用
FAIL V8_thresholdAdjustment       !! 命令"建立:"当前不可用
FAIL V9_thresholdLayer            !! 命令"建立:"当前不可用
FAIL V10_putClass_thresholdAdjustment !! 命令"建立:"当前不可用
```

**对照组能过、阈值 10 种全堵** → 这是该类调整层在本版本确实建不出来，不是写法问题。
实用替代：像素层 `layer.threshold(level)`，MAD 93.88。

### 9.6 清单式总验收（新增 `manifest_recovered2.json`）

```
PASS 1 bg  => bg
PASS 2 shape rectangle ShapeRect  => kind=LayerKind.SOLIDFILL
PASS 3 shape ellipse ShapeRing    => kind=LayerKind.SOLIDFILL
PASS 4 rect Fade                  => Fade op=100
PASS 5 mask revealSelection FadeMask => mask=revealSelection on Fade
PASS 6 text Note
PASS 7~9 export psd / png / webp
SUMMARY pass=9 fail=0 layers=5 size=900x600
docs left open=0 (应=0)
```

**PSD 往返像素级证明**：重开 `recovered2.psd` → 再导一张 PNG → 与原 PNG 比对，

```
MAD(原PNG vs PSD回读PNG) = 0.0000
选区内(200,380)=(59,130,246) 蓝   选区外(60,380)=(16,16,20) 底色
```

如果蒙版丢了，Fade 会变回整块矩形、MAD 会大幅偏离 0；**0.0000 说明蒙版与形状层在 PSD 里完整保存**。

## 10. 第三轮：能力扩展（2026-11-15 晚）

这一轮补的不是"翻案"，是四个原本完全没有的能力：图层样式、多尺寸变体、数据表批量、PSD 模板回填。

### 10.1 图层样式：先被 charID 绊了一次，再全通

第一版 `fxStroke()` 直接照抄社区代码，结果只有描边挂不上：

```
FAIL 7 effect effect<-Title  !! 非法参数
PASS 8 effect effect<-Plate  => effects=1 on Plate      ← 浮雕（纯 stringID）
PASS 9 effect effect<-Chip   => effects=1 on Chip       ← 颜色叠加（纯 stringID）
PASS 10 effect effect<-GlowWord => effects=1 on GlowWord ← 外发光（纯 stringID）
```

四个效果里三个通过，唯独用 charID 写的描边失败 → 又一次是 **`"Md "` / `"Sz "` 只有 3 字符**（第 14 条坑的重演）。
逐字段探针 `p13_stroke.jsx` 的结论是：每个 `putXxx` 单看都 OK，`executeAction` 也 OK，`hasKey layerEffects = true`——说明配方本身没问题，问题只在拼写。

改成 `"Md  "` / `"Sz  "` 后：

```
PASS 7  effect effect<-Title     => effects=2 on Title
PASS 8  effect effect<-Plate     => effects=1 on Plate
PASS 9  effect effect<-Chip      => effects=1 on Chip
PASS 10 effect effect<-GlowWord  => effects=1 on GlowWord
SUMMARY pass=12 fail=0 layers=6
```

`effects=2` 这一条是关键：描边 + 投影写在同一个 `effect` 对象里，回读确认两个都生效。
如果分两次 `setd`，第二次会把第一次冲掉，而两次都不报错——这也是把 `countFX()` 回读写进流程的原因。

**逐区域像素证据**（基准 `manifest_effects_base.json`，同一版式但不加样式）：

```
基准 (600, 900, 3)  样式版 (600, 900, 3)  尺寸一致=True
OK  Title 描边+投影      MAD= 10.847   改动像素占比=17.52%
OK  Plate 斜面和浮雕     MAD=  6.718   改动像素占比=11.72%
OK  Chip 颜色叠加        MAD= 51.663   改动像素占比=79.89%
OK  GlowWord 外发光      MAD=  6.845   改动像素占比=35.26%

Chip 中心实测 RGB=[ 70 127 101]  预测 RGB=[ 70 127 101]  误差=[0.1 0.2 0.5]
```

颜色叠加是唯一能解析预测的：底色 `C8892F`(200,137,47) 上叠 `2F7D6E`(47,125,110) @85%
→ 理论 0.15×底色 + 0.85×叠加色 = (70,127,101)，实测完全吻合。这比"看起来绿了"强得多。

### 10.2 变体导出：尺寸是硬指标

源 1080×1350，三个变体：

```
PASS 8  variant @1.5x  => ...variants_@1.5x.png  1620x2025
PASS 9  variant 1x1    => ...variants_1x1.png    1080x1080
PASS 10 variant 9x16   => ...variants_9x16.png   1080x1920
```

1620×2025 = 1080×1.5 / 1350×1.5；1:1 与 9:16 是 `resizeCanvas` 到目标画布后的绝对值，不是"差不多"。
`contain` 模式会把画布撑大，脚本自动在最底层补一层 `doc.bg` 底色，否则四周是透明的。

### 10.3 批量：三张成品必须互不相同

第一次跑直接全跳过：

```
[1/3] 跳过：模板里有数据表没有的字段 字段
批量结束：成功 0 / 3，失败 3
```

原因不是数据表，是模板里 `"_note": "...{{字段}}..."` 这句说明被当成真变量。给 `_` 前缀键豁免后：

```
[1/3] cert_001   PASS  pass=9  241.5 KB
[2/3] cert_002   PASS  pass=9  249.1 KB
[3/3] cert_003   PASS  pass=9  252.4 KB
批量结束：成功 3 / 3，失败 0
```

像素互比（证明替换落到画面而不是只改了 JSON）：

```
001 vs 002 MAD = 4.104
001 vs 003 MAD = 4.469
002 vs 003 MAD = 4.465
```

### 10.4 模板回填：模板哈希不变是底线

模板 `tpl_cert.psd` 由 `p14_mktpl.jsx` 造出（BG + Title/Price 两个文字层 + Photo 智能对象，4 层）。

> 第一版版式有遮挡：Title 72pt 从 x=60 起排到约 500px，智能对象却在 x=460 起，且替换图本身偏暗，
> 出图看像"标题被截断 + 图片没换"。这不是脚本错，是样例设计没留够位置。
> 改成 Title 60pt / 智能对象放在 (480,180) 360×300 后重做，下面所有数据都来自新版。

```
PASS 1 open template  => tpl_cert.psd 900x600 layers=4
PASS 2 text Title  => contents=年度优秀员工
PASS 3 text Price  => contents=奖金 ¥12,000
PASS 4 image Photo => replaced Photo kind=LayerKind.SMARTOBJECT
PASS 5 visible Price => visible=true
PASS 6 export png / PASS 7 export psd
SUMMARY pass=7 fail=0 layers=4 size=900x600
```

**模板没被改写**：

```
跑前 8d0c894b14c86fc0cc28cb2402cdc2c3 *tpl_cert.psd
跑后 8d0c894b14c86fc0cc28cb2402cdc2c3 *tpl_cert.psd
```

换图生效（A/B 两份回填只差文案和图片）：

```
A vs B MAD = 22.816
图区 MAD   = 92.994      ← 只取智能对象所在区域 (480,180)-(840,480)
```

负向用例（把图替换到普通像素层上）必须明确报错而不是静默成功：

```
FAIL 2 image BG  !! BG 不是智能对象（kind=LayerKind.NORMAL）；请在模板里右键该层 → 转换为智能对象
SUMMARY pass=2 fail=1
```

### 10.5 全量回归（重构后旧能力零回退）

`main()` 被拆成 `load_manifest()` / `run_manifest()` 供 `ps_batch` 复用，导出分支被抽成 `SAVE_FMT_JS` 供 `ps_fill` 共用，所以必须整体重跑：

```
manifest_basic         SUMMARY pass=8  fail=0 layers=6
manifest_full          SUMMARY pass=25 fail=0 layers=13
manifest_recovered     SUMMARY pass=15 fail=0 layers=7
manifest_recovered2    SUMMARY pass=9  fail=0 layers=5
manifest_effects       SUMMARY pass=12 fail=0 layers=6
manifest_variants      SUMMARY pass=10 fail=0 layers=6 variants=3
```

合计 **79 步，fail=0**。另有批量 3 行 ×9 步、回填 7 步 / 5 步 / 负向 1 失败。

## 11. 第四轮：阈值调整层翻案（2026-11-15 晚，结论：**之前判错**）

§9.5 里我写的是"对照组确证不可用"。这次重新搜公开资料，在 ps-scripts 一个讲
「按图层反查 LayerKind」的帖子里看到这段 switch：

```javascript
case 'posterization'      : return LayerKind.POSTERIZE;
case 'thresholdClassEvent': return LayerKind.THRESHOLD;    // ← 就是它
```

也就是说阈值层的**类 ID 叫 `thresholdClassEvent`**，我此前试过的
`thresholdClass` / `thresholdAdjustment` / `thresholdLayer` / `Thsh`(charID) 一个都不对。
10 种组合全灭不是"功能不存在"，是**名字全部猜错**。

### 11.1 建层：5 个变体，4 个通过

```
OK   A_empty    cls=thresholdClassEvent  kind=LayerKind.THRESHOLD  name=阈值 1  layers=2
OK   B_preset   cls=thresholdClassEvent  kind=LayerKind.THRESHOLD  name=阈值 1  layers=2
OK   C_lvl      cls=thresholdClassEvent  kind=LayerKind.THRESHOLD  name=阈值 1  layers=2
OK   D_lvlPre   cls=thresholdClassEvent  kind=LayerKind.THRESHOLD  name=阈值 1  layers=2
ERR  E_thsh     cls=Thsh  !! 发生了常规 Photoshop 错误。该功能可能无法在这个版本的 Photoshop 中使用。
- 命令"建立:"当前不可用。
```

E 就是原来那 10 种组合里的写法，同一个文档、同一段骨架，只换类 ID 就从 FAIL 变 PASS。

### 11.2 参数：`Lvl` 写在 make 里会被静默丢弃

第一次测 C（`Lvl=128`）与 F（`Lvl=64`）时，两张图**逐个像素完全相同**（MAD 0.000）——
说明 `make` 阶段塞进 type 描述符的 `Lvl` 根本没被采纳，层还是默认值。
这类"层建成了但参数没进去"的坑比报错更危险，所以参数一律走 `setd`：

```
ERR  G setd T=charID("Thsh")                 !! 命令"设置:当前不可用。
OK   H setd T=stringID("thresholdClassEvent")  kind=LayerKind.THRESHOLD
```

**建层和 `setd` 的 `T` 键都必须用 stringID 形式**；任何一处换成 charID `Thsh` 就报"不可用"。

### 11.3 像素证据：四条灰带证明阈值真的变了

素材：`60 / 100 / 140 / 200` 四条灰带，读同一列（x=150）四个高度。

```
base   60->60   100->100  140->140  200->200     ← 不建层
I      60->0    100->0    140->255  200->255     ← 默认阈值 128
H      60->0    100->255  140->255  200->255     ← Lvl=64
```

`100` 这条带在阈值 128 时转黑、阈值 64 时转白——**只改一个整数就让整条灰带翻面**，
这是参数生效最硬的判据。整图 `MAD(base vs Lvl=64) = 96.25`。

### 11.4 PSD 往返 + 类 ID 反查

重开 `threshold.psd`：

```
layer[0] Thresh64 kind=LayerKind.THRESHOLD
adjustment class = thresholdClassEvent
```

回读出的类 ID 正是 `thresholdClassEvent`，与建层时用的完全一致。
这个方法（`executeActionGet` → `getList("adjustment").getClass(0)` → `typeIDToStringID`）
应该作为**所有调整层的标准反查手段**：不要猜名字，先看 Photoshop 自己怎么叫。

### 11.5 收口

- `ps_build.py`：`ADJUSTS` 增加 `threshold`，`ADJ_KIND_STR["threshold"] = "thresholdClassEvent"`，新增 `setThreshold(lvl)`；`level` 校验 0–255 整数。
- 新增 `examples/manifest_threshold.json`（+ `manifest_threshold_base.json` 基准），`pass=7 fail=0`。
- 调整层能力从 **14 ✅ / 1 ❌** 变成 **15 ✅ / 0 ❌**；§8 的"7 条 ❌"现在**全部**是误判。
- 全量回归：7 份清单 **86 步 fail=0**。

**这一轮的教训比结论更值钱**：连续四次误判里有三次是同一类——**ID 名字靠记忆猜**。
以后判定"不支持"必须有一步是"从已存在的对象反查真实 ID"，没有这一步就不许下结论。
