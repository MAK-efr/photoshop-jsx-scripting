---
name: ps-jsx-poster-cutout
description: 用 Photoshop 25.x + ExtendScript(JSX) 做全自动出图：一份 JSON 清单 → 分层 PSD/PNG/JPG/TIFF，支持图层组与组套组（任意层嵌套）、图层蒙版（显示/隐藏全部或选区）、剪贴蒙版、矢量形状层（矩形/椭圆/填充/描边）、图层样式（描边/投影/外发光/颜色叠加/斜面和浮雕）、调整层（曲线/色阶/色相饱和度/渐变映射等 14 种）、滤镜（马赛克/高斯模糊/加噪等 11 种）、文字（点/段落/竖排/变形）、图片置入、选区运算、智能对象、多尺寸变体导出、WebP 导出；另有两个配套入口：数据表批量出图（模板 × CSV/JSON → N 张）与 PSD 模板按图层名回填（换文案/换图，版式不动）；也覆盖本地抠图（选择主体）与人像海报。当用户要求"用 PS 做海报/卡片/证件照"、"把人物抠出来换背景"、"不打开 GUI 批量出图"、"拿设计稿批量换文案"、"PS 能不能脚本化"时使用。已实测六份清单 + 批量 + 回填全部通过（共 79 步 fail=0），图层样式、变体尺寸、批量产物差异、模板哈希不变均有像素级或哈希级证据。
agent_created: true
---

# Photoshop 脚本化出图（JSX + 清单驱动）

> 验证环境：Photoshop **25.0.0**（Photoshop 2024）· Win11 26200 · 559 字体 · 2026-11-15
> 本文每条 ✅/❌ 都有对应的实测记录（`docs/VERIFY.md`），没有"看文档觉得应该行"的条目。

## 0. 四个入口，先选对

| 入口 | 用途 | 命令 |
|---|---|---|
| **`scripts/ps_build.py`** | **主力**：JSON 清单 → 分层 PSD/PNG/JPG/TIFF | `python ps_build.py manifest.json` |
| **`scripts/ps_batch.py`** | 一份模板 × CSV/JSON 数据表 → N 张（`{{字段}}` 替换） | `python ps_batch.py t.json --rows rows.csv` |
| **`scripts/ps_fill.py`** | 打开现成 .psd，按图层名换文案/换图，版式不动 | `python ps_fill.py fill.json` |
| `scripts/ps.py` | 底层：连接 / 跑任意 jsx / 导出图层树 / 旧版卡片模板 | `python ps.py info\|exec\|dump\|card` |

清单式不是"把内容写死在 jsx 里"——而是 **Python 决定内容、PS 负责执行**：改文案只改 JSON，不碰脚本。
`ps_build` 管"从零搭版式"，`ps_fill` 管"复用已有版式"，`ps_batch` 管"同版式多文案"。三者共用同一套导出与连接层。

```bash
SK=~/.workbuddy/skills/ps-jsx-poster-cutout/scripts
python "$SK/ps_build.py" manifest.json --check     # 只校验，不执行
python "$SK/ps_build.py" manifest.json --dry-run   # 只生成 jsx
python "$SK/ps_build.py" manifest.json             # 真跑 + 回读日志 + 核对产物
```

清单最小样例见 `examples/manifest_basic.json`，全特性样例见 `examples/manifest_full.json`（15 条顶层指令 → 13 图层，组、剪贴、模糊、擦除、图片置入全用上）；两组"复测翻案"专用样例：`manifest_recovered.json`（渐变映射 + 马赛克 + **三层嵌套组**，15 步全通过）、`manifest_recovered2.json`（**图层蒙版 + 矢量形状层 + WebP**，9 步全通过）。

## 1. 能力矩阵（实测，非推测）

### 1.1 图层体系

| 能力 | 状态 | 实测要点 |
|---|---|---|
| 普通图层 / 命名 / 不透明度 / 可见性 | ✅ | 不透明度有量化，写 30 读回 30.196 |
| 混合模式（normal/multiply/screen/overlay/…） | ✅ | `blendMode = BlendMode.MULTIPLY` |
| **图层组** | ✅ | `layerSets.add()`；**子层必须 `move(g, INSIDE)`** |
| **组套组（嵌套，任意深度）** | ✅ | `move(LayerSet→LayerSet)` 恒报「非法参数」，但**在父组内的锚点层上原位 `make layerSection`** 可成（实测 3 层结构 文档>Outer>Inner，回读嵌套保持）。坑位见 6、13 |
| **剪贴蒙版** | ✅ | `clip.grouped = true`，像素证据：白方块内洋红 (255,0,255)，方块外保持底色 (26,26,26)，两版 MAD 5.10 |
| **图层蒙版** | ✅ | `Mk` + `Nw=Chnl` + `At=Chnl/Chnl/**Msk**` + `Usng=UsrM/RvlA|HdAl|RvlS|HdSl`。像素证据：`RvlS` 后选区外 alpha=0、选区内 255；`HdAl` 后在蒙版通道涂白可只放出指定区域。**两个坑见 3、14** |
| 图层复合 layerComps | ✅ | 捕获的是**当前可见性**，不是任意指定 |
| 智能对象 | ✅ | `newPlacedLayer`；`placedLayerEditContents` 能打开内部 .psb（打开数 1→2→1） |
| 智能滤镜（非破坏模糊） | ✅ | 智能对象上 `applyGaussianBlur(8)` |
| 填充层：渐变 / 图案 | ✅ | `make AdjL` + `type: gradientLayer / patternLayer` |
| 填充层：纯色 | ⚠️ | 能建（`solidColorLayer`），但**改色 `setd` 失败**（参数 3），只能用默认色 |
| **矢量形状层** | ✅ | `make contentLayer` + `using = {type: solidColorLayer{Clr:RGBC}, shape: rectangle/ellipse, strokeStyle}`；矩形/椭圆、纯填充/描边都过，回读 `kind=SOLIDFILL` 且仍有 1 条矢量路径，见坑位 7 |
| **图层样式** | ✅ | 描边/投影/外发光/颜色叠加/斜面和浮雕 5 种，走 AM `Lefx`；**一次 `setd` 是整体替换**，多效果必须同一次写入，见 1.6 与坑位 15 |

### 1.2 调整层（14 ✅ / 1 ❌）

`make AdjL` + `using.adjustmentLayer.type.<ID>`，全部实测建层成功：

✅ `curves` `levels` `hueSaturation` `blackAndWhite` `photoFilter` `vibrance` `exposure`
  `colorBalance` `invert` `posterize` `selectiveColor` `channelMixer` `colorLookup` `gradientMap`

> **`gradientMap` 必须写 class ID `gradientMapClass`（`GdMp`, 1197755760），不是事件 ID `gradientMap`（4302）。**
> 写事件 ID 会报「命令"建立:"当前不可用」——这条曾被我误判成"本机不支持"，实际是 ID 用错。
> 量化证据：Sky 原色 `C8D8FF` 的 B−R=55，套渐变映射后 B−R=**0.00**、均值恰为 `219/219/219`（完全去色 neutralizing），见 `docs/VERIFY.md` §2。

❌ `threshold`（**这是唯一真正建不出来的调整层**：`thresholdClass`/`thresholdAdjustment`/`thresholdLayer`/`Thsh`(charID) 四类 ID × `putObject`/`putClass` × 空参/`Lvl`/`presetKind`/`Adjs` 共 10 种组合，全报「命令"建立:"当前不可用」；**同一段骨架换成 `curves`/`posterize`/`invert` 都成功**，已排除写法问题。替代：**像素层 `layer.threshold()`，MAD 93.88**）

**参数可写，且真的改像素**（与基准图逐像素平均绝对差）：

| 调整 | 配方 | MAD |
|---|---|---|
| 曲线 | `setd` → `T=Crvs` / `Adjs[0].Crv` 点列 | **29.51** |
| 色阶 | `setd` → `T=Lvls` / `Inpt`+`Gmm `+`Outt` | **18.32** |
| 色相饱和度 | `setd` → `T=HStr` / `H`+`Strt`+`Lght` | **4.69** |

> 只建层不设参 = 默认值 = 无变化。要"看起来调过色"，必须走上面的 `setd` 分支，`ps_build.py` 已封装成 `{"type":"adjust","adj":"curves","points":[[0,12],[128,140],[255,248]]}`。

### 1.3 滤镜（11 ✅，与 `FILTERS` 字典逐键对齐）

`layer.applyXxx()` 直接可用，MAD 全部非零：

| 滤镜 | 参数 | MAD |
|---|---|---|
| addNoise | amount | 68.72 |
| invert / desaturate | — | 53.81 / 12.56 |
| posterize | levels | 39.86 |
| highPass | radius | 26.41 |
| motionBlur | angle, distance | 14.80 |
| gaussianBlur | radius | 12.25 |
| unsharpMask | amount, radius, threshold | 7.87 |
| sharpenMore | — | 7.50 |
| threshold | level | 109.09 |
| **mosaic** | cellSize | 见下（DOM 无此方法，走 ActionManager） |

**马赛克要绕道**：DOM 里**没有** `applyMosaic`（「不是函数」）。正解是 ActionManager 事件 `Msc ` + 整数键 `ClSz`：

```javascript
var d = new ActionDescriptor();
var r = new ActionReference(); r.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordr"), charIDToTypeID("Trgt"));
d.putReference(charIDToTypeID("null"), r);
d.putInteger(charIDToTypeID("ClSz"), 24);          // 单元格边长，是整数不是 UnitDouble
executeAction(charIDToTypeID("Msc "), d, DialogModes.NO);
```

`ps_build.py` 已封装成 `{"type":"filter","filter":"mosaic","cellSize":24}`。量化证据：导出图水平/垂直相邻像素完全相同率 **95.9% / 96.0%**，跳变列间距严格 **24,24,24,…**（10 个连续），见 `docs/VERIFY.md` §2。

### 1.4 文字

| 能力 | 状态 | 备注 |
|---|---|---|
| 点文字 / 段落文字 | ✅ | 段落用 `TextType.PARAGRAPHTEXT` + `ti.width/height` |
| 竖排 | ✅ | `ti.direction = Direction.VERTICAL` |
| 文字变形 | ✅ | `ti.warpStyle = WarpStyle.ARC` + `warpBend` |
| 字体回读一致 | ✅ | 请求 `NotoSansSC-Black` → 回读 `NotoSansSC-Black` |
| 字距 tracking | ✅ | `ti.tracking = 300` |
| **行距 leading** | ⚠️ | 直接写会抛「文本设置为自动行距，并且没有特殊的行距值」；**必须先 `ti.useAutoLeading = false`** |
| 换行 | ⚠️ | 必须 `\r`；用 `\n` 会渲染成方块 |

**本机可用中文字体（PostScript 名）**：`NotoSansSC-Thin/Light/DemiLight/Regular/Medium/Bold/Black`、`NotoSerifSC-SemiBold/Bold`、`MicrosoftYaHei`/`-Bold`、`MicrosoftYaHeiLight`、`SimHei`、`SimSun`、`DengXian-Bold`、`AdobeHeitiStd-Regular`。
写错字体名**不中断脚本**，只会静默回落默认字体——所以 `ps_build.py` 把 `ti.font` 回读打进日志，看到实际字体才算过。

### 1.5 选区 / 画布 / 导出

| 能力 | 状态 | 说明 |
|---|---|---|
| 矩形/椭圆选区 + 填充 | ✅ | 最稳的"形状"实现（矢量形状层 ❌，见坑位 7） |
| 羽化 feather | ✅ | 边缘渐变可量 |
| 收缩 contract | ✅ | 100px 选区 -10 → 80px |
| 反选 invert | ✅ | |
| **扩展 expand** | ⚠️ | `selection.expand()` 报「没有这种元素」；AM `Expn` 能跑但**不管传 8/32/80 都只扩 1px**（100→99/201）。**唯一可靠做法：读 `bounds` 自己算再 `select()`**（实测 92,92,208,208 一次到位） |
| resizeCanvas / resizeImage / crop | ✅ | 600×400 → 300×200 → crop 200×150 |
| 导出 PNG / JPG / TIFF / PSD / PDF / **WebP** | ✅ | `saveAs` + 对应 Options；PSD `layers=true` 保层；WebP 走 AM `save` |
| 存为 Web（PNG24 / JPG） | ✅ | `exportDocument(f, ExportType.SAVEFORWEB, o)` |
| **WebP** | ✅ | `SaveDocumentType.WEBP` 不存在、`WebPSaveOptions` 无构造器，唯一的路是 ActionManager `save` + `as=WebPFormat{compression,quality}`（PS 2022+ 原生）。实测 900×600 → 14,406 B，PIL 可解码 |

**PSD 往返保真**（本例 13 层）：`saveAs(psd)` → `close` → `app.open` 回读，顶层 7 条、`Outer>Inner>2 子层` 三层嵌套、`LayerKind.GRADIENTMAP`、图层名/类型/不透明度/可见性全部一致。

### 1.6 图层样式（5 ✅，走 ActionManager `layerEffects`）

DOM 没有图层样式 API，只能拼描述符。**铁律：一次 `setd` 对 `Lefx` 是整体替换**（Adobe 社区原话：any other styles applied they will be lost）→ 同一层的多个效果必须写在**同一个 `effect` 对象**里，写成两个对象只会留下后者。

| 效果 | 描述符键 | 关键参数 |
|---|---|---|
| 描边 | `FrFX` | `Styl/FStl`=OutF/InsF/CtrF · `Sz  ` · `Clr ` · `Opct` · `Md  `/`BlnM` |
| 投影 | `dropShadow` | distance · blur · opacity · angle · chokeMatte · color |
| 外发光 | `outerGlow` | blur · opacity · color · chokeMatte · glowTechnique |
| 颜色叠加 | `solidFill` | color · opacity · mode |
| 斜面和浮雕 | `bevelEmboss` | style · depth · size · soften · angle · altitude · 高光/暗部及各自 opacity |

像素证据（对"无样式基准"逐区域比，MAD > 0.5 才算真的动了像素）：

| 区域 | MAD | 改动像素占比 |
|---|---|---|
| Title 描边+投影 | **10.847** | 17.52% |
| Plate 斜面和浮雕 | **6.718** | 11.72% |
| Chip 颜色叠加 | **51.663** | 79.89% |
| GlowWord 外发光 | **6.845** | 35.26% |

颜色叠加还能**解析预测**：`C8892F` 上叠 `2F7D6E` @85% → 预测 `(70,127,101)`，实测 `(70,127,101)`，误差 ≤0.5。

```jsonc
{"type":"effect", "target":"Title",
 "stroke": {"size":5,"color":"C8892F","pos":"outside"},
 "shadow": {"distance":10,"blur":18,"opacity":65,"angle":120}}
```
可省略的参数取默认值；`pos` 三选一 outside/inside/center。**脚本会回读层上真正生效的效果个数，对不上就报 FAIL**——"命令没报错"不算证据。

### 1.7 变体导出（多倍率 / 多比例）

```jsonc
"out": {"variants": [
  {"suffix":"@1.5x", "scale":1.5, "formats":["png"]},                    // 纯缩放
  {"suffix":"1x1",   "w":1080, "h":1080, "mode":"cover"},                // 裁切填满
  {"suffix":"9x16",  "w":1080, "h":1920, "mode":"contain"}               // 缩放后补底
]}
```

机制：`doc.duplicate()` 出副本 → `resizeImage(BICUBIC)` → `resizeCanvas(MIDDLECENTER)` → 存 → 关副本。**主文档全程不受影响**，所以能和主格式导出同时跑。

实测（源 1080×1350）：`@1.5x` 得 **1620×2025**、`1x1` 得 **1080×1080**、`9x16` 得 **1080×1920**，三个文件都落地。
`contain` 放大画布后四周是透明的，脚本会自动用 `doc.bg` 在最底层补一层底，否则成品露空洞。

## 2. 执行通道
```python
import win32com.client
app = win32com.client.Dispatch('Photoshop.Application')
app.DisplayDialogs = 3                        # 3 = 不弹任何对话框（必须，见坑位 2）
app.DoJavaScriptFile(r'绝对路径\script.jsx')   # 首选，免疫字符串转义
```

- `CLSID {DD6CF2ED-4840-40A1-A393-B1F74F54D59A}`，`LocalServer32 = Photoshop.exe /Automation`，无需 SDK。
- `DoJavaScript(code)` 只有单参数签名可用，含引号/换行易报「未终止的字符串常数」→ **一律走 .jsx 文件**。
- 日志由 JSX 写文件、Python 读回；JSX 返回值不可靠。

## 3. 坑位（17 条，全部踩过）

**1. COM 的 `Documents.Count` 不可靠** → 判断"有没有文档"只信 JSX 的 `app.documents.length`。

**2. `app.displayDialogs = DialogModes.ALL` 会挂死整条链路。**
一旦某条命令内部报错，PS 会弹出无人可点的模态框，`DoJavaScriptFile` **永久阻塞**（实测卡 4 分钟，最后只能 `taskkill`）。**永远保持 `DialogModes.NO`**，Python 侧再加超时兜底。

**3. 图层蒙版：能加，但配方对两处细节极度敏感。**
能跑通的只有这一种写法（`ps_build.py` 的 `mask` 类型就是它）：

```javascript
var d = new ActionDescriptor();
d.putClass(charIDToTypeID("Nw  "), charIDToTypeID("Chnl"));     // ⚠ "Nw  " 是 4 字符
var r = new ActionReference();
// ⚠ 第三个枚举值是 "Msk "（= stringID "mask"），不是 stringIDToTypeID("maskChannel")
r.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Chnl"), charIDToTypeID("Msk "));
d.putReference(charIDToTypeID("At  "), r);                       // ⚠ "At  " 4 字符
d.putEnumerated(charIDToTypeID("Usng"), charIDToTypeID("UsrM"), charIDToTypeID("RvlA"));
executeAction(charIDToTypeID("Mk  "), d, DialogModes.NO);        // ⚠ "Mk  " 4 字符
```

四种模式：`RvlA` 显示全部 · `HdAl` 隐藏全部 · `RvlS` 显示选区（需先建选区）· `HdSl` 隐藏选区。
蒙版可继续编辑：`slct` 选中 `Chnl/Msk ` 后用 `selection.fill()` 涂黑白即可。
**之前判"不可用"错在哪**：把第三枚枚举值写成 `stringIDToTypeID("maskChannel")`（那是 4414 的**类 ID**，不是枚举值 `Msk `）→「程序错误」；再把三个 3 字符 charID 混进去 →「非法参数」。两条叠加，看起来就像本机不支持。

**4. `doc.getPixel()` 不存在。**
想读某点像素只能 `doc.colorSamplers.add([x,y])`，或**导出 PNG 用 Pillow/numpy 量**（推荐，可复算）。本报告所有 MAD 都是这样算的。

**5. 覆盖用户文档 = 数据丢失级错误。**
早期模板写 `while (app.documents.length > 0) app.documents[0].close(...)`，用户开着未保存 PSD 时跑一次就丢光。正确做法：只 `app.documents.add()` 自己那一份，干完只 `doc.close()` 自己那份，并打日志核对 `app.documents.length` 回到 `preexisting`。

**6. 组套组：`move` 不行，但在锚点上 `make layerSection` 可以。**
`g2.move(g1, ElementPlacement.INSIDE / PLACEATBEGINNING)` 对 **LayerSet→LayerSet** 恒报「非法参数」（对 ArtLayer→LayerSet 却正常）；`g2.duplicate(g1)` 报「您不能把一个图层组复制到另一个图层组中」。**可行的路只有一条**：

```javascript
// 前提：父组 G 里已经有一个普通图层当"锚点"（名字自己起，如 G__anchor）
D.activeLayer = <父组>.artLayers.getByName("G__anchor");
var d = new ActionDescriptor();
var rc = new ActionReference(); rc.putClass(stringIDToTypeID("layerSection"));
d.putReference(stringIDToTypeID("null"), rc);
var rt = new ActionReference(); rt.putEnumerated(stringIDToTypeID("layer"), stringIDToTypeID("ordinal"), stringIDToTypeID("targetEnum"));
d.putReference(stringIDToTypeID("at"), rt);          // at = 锚点 → 新组插在锚点位置，即父组内部
executeAction(stringIDToTypeID("make"), d, DialogModes.NO);
var g = D.activeLayer; g.name = "子组";
```

`ps_build.py` 的 `group` 类型就是这么做的：**进组前先塞 `名字+__anchor` 普通层，建完子层后 `anchor.remove()`**，所以产物里看不到锚点。实测 `Outer>Inner` 三层结构，回读 `Outer.children=2`、`Inner.children=2`。

**7. 矢量形状层：能建，但 `make contentLayer` 要一次给全三层描述符。**
少任何一层就报「命令<未知的>当前不可用 / 非法参数」。完整结构（矩形填充，`ps_build.py` 的 `shape` 类型）：

```javascript
var d = new ActionDescriptor();
var r = new ActionReference(); r.putClass(stringIDToTypeID("contentLayer"));
d.putReference(charIDToTypeID("null"), r);

var d1 = new ActionDescriptor();
// ① 颜色：type = solidColorLayer，里面包 Clr=RGBC{Rd,Grn,Bl}
var cd = new ActionDescriptor();
cd.putDouble(charIDToTypeID("Rd  "), 200); cd.putDouble(charIDToTypeID("Grn "), 130); cd.putDouble(charIDToTypeID("Bl  "), 47);
var td = new ActionDescriptor(); td.putObject(charIDToTypeID("Clr "), charIDToTypeID("RGBC"), cd);
d1.putObject(stringIDToTypeID("type"), stringIDToTypeID("solidColorLayer"), td);
// ② 形状：shape = rectangle/ellipse，四边用 pixelsUnit
var sh = new ActionDescriptor();
sh.putUnitDouble(stringIDToTypeID("top"),    stringIDToTypeID("pixelsUnit"), 50);
sh.putUnitDouble(stringIDToTypeID("left"),   stringIDToTypeID("pixelsUnit"), 50);
sh.putUnitDouble(stringIDToTypeID("bottom"), stringIDToTypeID("pixelsUnit"), 200);
sh.putUnitDouble(stringIDToTypeID("right"),  stringIDToTypeID("pixelsUnit"), 250);
d1.putObject(stringIDToTypeID("shape"), stringIDToTypeID("rectangle"), sh);
// ③ 描边/填充开关：fillEnabled 或 strokeEnabled 必须显式给一个
var st = new ActionDescriptor();
st.putBoolean(stringIDToTypeID("strokeEnabled"), false);
st.putBoolean(stringIDToTypeID("fillEnabled"), true);
d1.putObject(stringIDToTypeID("strokeStyle"), stringIDToTypeID("strokeStyle"), st);

d.putObject(stringIDToTypeID("using"), stringIDToTypeID("contentLayer"), d1);
executeAction(charIDToTypeID("Mk  "), d, DialogModes.NO);
```

描边模式：`strokeEnabled=true` + `strokeStyleLineWidth`(pixelsUnit) + `strokeStyleContent = solidColorLayer{Clr:RGBC}`，同时 `fillEnabled=false`。
回读验证：`kind=LayerKind.SOLIDFILL`，且 `pathItems.length=1`（仍是矢量，不是栅格化的矩形）。
**旧判定错在哪**：只传了 `null` 引用和极简 `type`，缺 `shape`/`strokeStyle`，于是被当成畸形内容层。失败后残留的工作路径确实会污染后续 `selection.fill`（这条仍然成立），所以失败后要先 `pathItems[0].remove()` 或重开文档。

**8. 填充层不能用 `kind` 建。**
`l.kind = LayerKind.SOLIDFILL` 报「您只能将图层的类型更改为文本或正常」。必须 `make` + `AdjL`。

**9. 新建文档必带一个占位层。**
`DocumentFill.WHITE` → "背景"；`TRANSPARENT` → "图层 1"。删唯一层会报错，所以 `ps_build.py` **把它改名为 BG 直接当底色用**，否则产物会多一层空白、重开核对时多一层干扰。

**10. 组内新增图层要显式 move。**
`doc.activeLayer = group; doc.artLayers.add()` —— 新层**不进组**（实测 `group.layers.length` 仍为 0），必须 `l.move(g, ElementPlacement.INSIDE)`。

**11. PS 已手动启动时，`Dispatch` 可能永久阻塞。**
手动启动的实例不一定注册到 ROT（`GetActiveObject` 报「操作无法使用」），此时 `Dispatch` 会去拉新实例、撞上单实例锁，卡住不返回。
处理：**先完全退出所有 Photoshop 进程**，再让 COM 自己拉起；`ps.py` 已对三种错误码做重试：
`-2147417846` 忙 · `-2147220995` Dispatch 已返回但进程还在启动 · `-2146959355` 拉起失败。

**12. 别在子线程里直接调 COM。**
线程内必须先 `pythoncom.CoInitialize()`，否则报「尚未调用 CoInitialize」——这个错误看起来像"PS 没装好"，其实是漏初始化。

**13. `getByName` 只找直接成员，不做递归。**`D.artLayers.getByName("Outer__anchor")` 对**组内**的图层报「没有这种元素」；`D.layerSets.getByName("Inner")` 同样找不到嵌套组。三层以上必须写链式路径：

```javascript
D.layerSets.getByName("Outer").layerSets.getByName("Inner").artLayers.getByName("Inner__anchor")
```

`ps_build.py` 的 `emit_layer` 用 `stack` 列表逐层拼出这条链（`gref()`），这是嵌套组第一版唯一的翻车点。顺带一个纪律：**清单里图层名必须全局唯一**，否则链式定位会命中错的同名层。

**14. `charIDToTypeID` 只接受恰好 4 个字符——3 个字符会直接抛「非法参数」。**
这条坑过一次大的：蒙版/形状层两次判"不可用"，一半原因就是抄来的代码里写了 `"Nw "`、`"At "`、`"Mk "`（都只有 3 字符），**在 `ActionDescriptor` 构造阶段就抛异常**，根本走不到 `executeAction`，错误信息看起来像"参数不合法"，实际是 **charID 拼错**。

```javascript
charIDToTypeID("Nw ")   // ✗ 抛「非法参数」（3 字符）
charIDToTypeID("Nw  ")  // ✓ 1316429856
charIDToTypeID("At  ")  // ✓ 1098129440   ← 注意是 At + 两个空格
charIDToTypeID("Mk  ")  // ✓ 1298866208
```

诊断办法：把所有要用的 charID 先过一遍，打印 `typeID`，看到异常/0 就是拼错：

```javascript
try { L("  [" + s + "] len=" + s.length + " => " + charIDToTypeID(s)); }
catch (e) { L("  [" + s + "] len=" + s.length + " ERR " + e.message); }
```

顺带记几个容易数错的：`"Rd  "`（红）/ `"Grn "` / `"Bl  "`（蓝）/ `"T   "`（type 键，T+3 空格）/ `"Lvl "`（level）/ `"Nm  "`（name）。

**15. 图层样式一次 `setd` 是整体替换，不是叠加。**
`setd` 目标 `Prpr/Lefx` 会**用新描述符覆盖该层全部效果**。想要"描边 + 投影"必须把 `FrFX` 和 `dropShadow` 放进同一个 `Lefx` 里；写成两次 `setd`，第二次会把第一次的效果冲掉，而两次都返回成功、都不报错——静默坑。
同时 `enabled` / `present` / `showInDialog` 三个布尔少写 `present` 或 `showInDialog`，效果"建了但看不见"。
另外效果内部的混合模式键是 charID `"Md  "`（mode）+ `"BlnM"`，枚举值也是 charID（`Nrml`/`Mltp`/`Scrn`…），**和图层混合模式的 `BlendMode.NORMAL` 不是一套写法**，直接混用会报「非法参数」。这一轮我自己就又把 `"Md "`（3 字符）写了一遍，报错位置和真因差了十个字段——所以脚本里加了 charID 长度自检。

**16. 换智能对象内容：目标层必须"唯一选中且可见"。**
`placedLayerReplaceContents` 不认 `_target` 参数，只认"当前活动图层"。实测两个必踩条件：
① 层被**隐藏**时选不中 → 报 `-25920`（错误文案是"命令当前不可用"，看起来像功能缺失）；
② 被**图层筛选器**挡住时同样选不中，且没有干净的办法检测筛选器状态。
所以替换前先 `l.visible = true; D.activeLayer = l;`，用完再决定要不要还原可见性。
普通像素层不是智能对象，直接替换同样 `-25920`——脚本先判 `kind === LayerKind.SMARTOBJECT` 并给出"右键→转换为智能对象"的改法。

**17. 批量的变量替换要跳过注释键。**
模板里以 `_` 开头的字段（`_note` / `_comment`）是给人看的说明，里面常写 `{{字段}}` 当示例。如果替换器无差别遍历所有字符串，就会把这些示例当成"数据表缺字段"从而整行跳过——现象是"明明写了数据却一行都没跑"。`ps_batch.py` 已对 `_` 前缀键做豁免。

## 4. 清单字段速查

```jsonc
{
  "out": {"dir": "...", "stem": "caps", "formats": ["psd","png","jpg"]},
  "doc": {"w":1080, "h":1350, "dpi":72, "bg":"14161A", "name":"PS-Caps"},
  "layers": [ /* 自底向上 */
    {"type":"rect","x1":84,"y1":96,"x2":180,"y2":101,"color":"C8892F","name":"RuleTop"},
    {"type":"text","text":"AI 直连 PS","font":"NotoSansSC-Black","size":118,
     "color":"F2EEE7","x":84,"y":350,"tracking":10,
     /* 可选 */ "leading":140,"justify":"center","para":[420,160],"vertical":true,
                "warp":"arc","bend":50,"opacity":80,"blend":"screen"},
    {"type":"image","path":"a.png","x":84,"y":470,"w":420,"h":300,"fit":"cover"},
    {"type":"group","name":"Rows","opacity":100,"layers":[ /* 子层 */ ]},
    {"type":"group","name":"Outer","layers":[            /* 组套组：直接嵌 group */
        {"type":"group","name":"Inner","layers":[ /* 再嵌 */ ]}
    ]},
    {"type":"adjust","adj":"curves","points":[[0,12],[128,140],[255,248]]},
    {"type":"adjust","adj":"levels","in":[40,200],"gamma":1.0,"out":[0,255]},
    {"type":"adjust","adj":"huesat","hue":0,"sat":60,"light":0},
    {"type":"adjust","adj":"gradientMap"},
    {"type":"filter","filter":"gaussianBlur","radius":24,"target":"PanelAccent"},
    {"type":"filter","filter":"mosaic","cellSize":24,"target":"Tile"},
    {"type":"shape","shape":"rectangle","x1":40,"y1":40,"x2":400,"y2":260,
     "color":"C8892F","name":"ShapeRect"},                    /* 矢量形状层*/
    {"type":"shape","shape":"ellipse","x1":460,"y1":40,"x2":860,"y2":260,
     "stroke":{"w":10,"color":"2F7D6E"},"name":"ShapeRing"},  /* 描边模式：不给 color */
    {"type":"mask","mode":"revealSelection","target":"Fade",
     "sel":[120,340,320,420],"name":"FadeMask"},              /* 真·图层蒙版 */
    {"type":"clip","target":"ClipTop"},
    {"type":"erase","x1":700,"y1":1170,"x2":996,"y2":1250,"target":"Bar"}
  ]
}
```

- `text.y` 是**基线**，不是顶边。
- `filter` 不写 `target` 时作用于"最近一个像素层"。
- `mask.mode` 四选一：`revealAll` / `hideAll` / `revealSelection` / `hideSelection`；后两者必须配 `sel`。
- `shape.stroke` 存在时走描边模式（`fillEnabled=false`），此时 `color` 只用于内部颜色描述符。
- `formats` 支持 `psd/png/jpg/tif/pdf/webp`。
- `blend` 支持 normal/multiply/screen/overlay/softlight/hardlight/darken/lighten/difference/lineardodge/color/luminosity。
- `effect` 的五类键都可省略，缺省值见 1.6；`stroke.pos` 三选一；效果混合模式用的是**另一套**写法（normal→`Nrml` 等），脚本已做映射，清单里照常写 normal/multiply/screen。
- `out.variants` 每项必须有 `suffix`，且 `scale` 与 `w`+`h` 二选一；`mode` 缺省 `contain`。
- `out.dir` 与 `image.path` 都**按清单文件所在目录**解析，整包目录搬走不用改。

## 5. 抠图（本地，不依赖云端）

```javascript
executeAction(stringIDToTypeID("autoCutout"), undefined, DialogModes.NO);  // 本地 Sensei
doc.selection.contract(2);   // 必须：剔除边缘混合像素，否则深底上浮青边
doc.selection.feather(0.5);
executeAction(stringIDToTypeID("defringe"), {Wth: 1}, DialogModes.NO);
```

**云端能力地区锁**：生成式填充 / 扩图 / 消除物体走 Adobe Firefly，中国大陆恒返回 `-25920`，与本机环境无关。
**"PS 云端锁 ≠ 本地锁"**：选择主体是本机 Sensei，可用。

定位要用 Pillow 在 alpha 通道上量（bbox / 头顶 y / 头中心 x / 肩宽），别用"原坐标 × 缩放比"——`resize()` 后有非零原点偏移。

## 6. 素材合格性（先说，别做完再说）

求职/证件类人像海报要求：**正面、正装、光线均匀、无他人入镜**。
自拍、便装、侧低头、阴天冷光 → 技术能救（曲线校色温、抠图换底），气质救不回来。这种情况先讲清楚再动手。

## 7. 批量出图与模板回填

### 7.1 `ps_batch.py`：模板 × 数据表

```bash
python ps_batch.py examples/batch_template.json --rows examples/batch_rows.csv
```

清单里**任何字符串**都能写 `{{字段}}`，`out.stem` 也支持（`"cert_{{id}}"` → `cert_001`）。
数据表 CSV（表头逗号分隔，UTF-8 带 BOM 也认）或 JSON 数组。
以 `_` 开头的键（`_note`）是注释，**不参与替换**——否则注释里写个示例 `{{字段}}` 就会被当成缺字段。

实测：3 行 → `cert_001/002/003` 各 9 步全 PASS；三张成品互比 MAD **4.10 / 4.47 / 4.47**，证明替换真的落到像素而不是只改了 JSON。
缺字段的行会跳过并报出来，不会静默出一张空图。

### 7.2 `ps_fill.py`：拿设计稿改内容

```jsonc
{
  "template": "tpl_cert.psd",
  "out": {"dir": "_out/fill", "stem": "cert_A", "formats": ["png","psd"]},
  "text":    {"Title": "2026 年度优秀员工", "Price": "奖金 ¥12,000"},
  "images":  {"Photo": "new.png"},
  "visible": {"Price": true}
}
```

- 按**图层名**定位，`getByName` 不递归 → 脚本自带 `findL()` 深度优先。
- 换图只能作用于**智能对象**（`placedLayerReplaceContents`）；普通像素层会直接报错并告诉你"右键→转换为智能对象"，不会静默失败。实测负向用例原文：`BG 不是智能对象（kind=LayerKind.NORMAL）`。
- 目标层被隐藏或被图层筛选器挡住时选不中（报 `-25920`），所以替换前先 `visible = true`。
- **模板文件一个字节都不改**：只 `saveAs` 到新名字，关文档用 `DONOTSAVECHANGES`。实测模板 MD5 跑前跑后都是 `8d0c894b…`。

实测：回填 7 步 / 5 步全 PASS；两份回填成品整图 MAD **22.82**、图区 MAD **92.99**，证明换图生效。

## 8. 文件清单

- `scripts/ps_build.py` — 清单驱动器（主力）
- `scripts/ps_batch.py` — 模板 × 数据表 批量出图
- `scripts/ps_fill.py` — PSD 模板按图层名回填
- `scripts/ps.py` — 连接/执行/图层树/卡片模板
- `scripts/*.jsx` — do_cutout（抠图）、curves_tone（分通道曲线）、make_poster（旧模板）、list_layers、probe_*
- `examples/manifest_basic.json` / `manifest_full.json` / `manifest_recovered.json` / `manifest_recovered2.json`
- `examples/manifest_effects.json`（+ `manifest_effects_base.json` 无样式基准）、`manifest_variants.json`
- `examples/batch_template.json` + `batch_rows.csv`、`examples/fill_cert.json`（配套 `assets/tpl_cert.psd`）
- `docs/VERIFY.md` — 每条结论的实测记录与失败原文
