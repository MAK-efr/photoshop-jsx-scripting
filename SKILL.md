---
name: ps-jsx-poster-cutout
description: 用 Photoshop 25.x + ExtendScript(JSX) 做全自动出图：一份 JSON 清单 → 分层 PSD/PNG/JPG/TIFF，支持图层组、剪贴蒙版、调整层（曲线/色阶/色相饱和度等 13 种）、滤镜（11 种）、文字（点/段落/竖排/变形）、图片置入、选区运算、智能对象；也覆盖本地抠图（选择主体）与人像海报。当用户要求"用 PS 做海报/卡片/证件照"、"把人物抠出来换背景"、"不打开 GUI 批量出图"、"PS 能不能脚本化"时使用。已实测清单式驱动 25 步全通过、产物 16 层可编辑、重开 PSD 图层名与不透明度保真。
agent_created: true
---

# Photoshop 脚本化出图（JSX + 清单驱动）

> 验证环境：Photoshop **25.0.0**（Photoshop 2024）· Win11 26200 · 559 字体 · 2026-11-15
> 本文每条 ✅/❌ 都有对应的实测记录（`docs/VERIFY.md`），没有"看文档觉得应该行"的条目。

## 0. 两条入口，先选对

| 入口 | 用途 | 命令 |
|---|---|---|
| **`scripts/ps_build.py`** | **主力**：JSON 清单 → 分层 PSD/PNG/JPG/TIFF | `python ps_build.py manifest.json` |
| `scripts/ps.py` | 底层：连接 / 跑任意 jsx / 导出图层树 / 旧版卡片模板 | `python ps.py info\|exec\|dump\|card` |

清单式不是"把内容写死在 jsx 里"——而是 **Python 决定内容、PS 负责执行**：改文案只改 JSON，不碰脚本。

```bash
SK=~/.workbuddy/skills/ps-jsx-poster-cutout/scripts
python "$SK/ps_build.py" manifest.json --check     # 只校验，不执行
python "$SK/ps_build.py" manifest.json --dry-run   # 只生成 jsx
python "$SK/ps_build.py" manifest.json             # 真跑 + 回读日志 + 核对产物
```

清单最小样例见 `examples/manifest_basic.json`，全特性样例见 `examples/manifest_full.json`（16 图层、组、剪贴、模糊、擦除、图片置入全用上）。

## 1. 能力矩阵（实测，非推测）

### 1.1 图层体系

| 能力 | 状态 | 实测要点 |
|---|---|---|
| 普通图层 / 命名 / 不透明度 / 可见性 | ✅ | 不透明度有量化，写 30 读回 30.196 |
| 混合模式（normal/multiply/screen/overlay/…） | ✅ | `blendMode = BlendMode.MULTIPLY` |
| **图层组** | ✅ | `layerSets.add()`；**子层必须 `move(g, INSIDE)`** |
| **组套组（嵌套）** | ❌ | 4 种写法全报「非法参数」，见坑位 6 |
| **剪贴蒙版** | ✅ | `clip.grouped = true`，像素证据：白方块内洋红 (255,0,255)，方块外保持底色 (26,26,26)，两版 MAD 5.10 |
| **图层蒙版** | ❌ | 4 种 ActionManager 配方全报「程序错误」，见坑位 3 |
| 图层复合 layerComps | ✅ | 捕获的是**当前可见性**，不是任意指定 |
| 智能对象 | ✅ | `newPlacedLayer`；`placedLayerEditContents` 能打开内部 .psb（打开数 1→2→1） |
| 智能滤镜（非破坏模糊） | ✅ | 智能对象上 `applyGaussianBlur(8)` |
| 填充层：渐变 / 图案 | ✅ | `make AdjL` + `type: gradientLayer / patternLayer` |
| 填充层：纯色 | ⚠️ | 能建（`solidColorLayer`），但**改色 `setd` 失败**（参数 3），只能用默认色 |

### 1.2 调整层（13 ✅ / 2 ❌）

`make AdjL` + `using.adjustmentLayer.type.<stringID>`，全部实测建层成功：

✅ `curves` `levels` `hueSaturation` `blackAndWhite` `photoFilter` `vibrance` `exposure`
  `colorBalance` `invert` `posterize` `selectiveColor` `channelMixer` `colorLookup`

❌ `gradientMap`（命令"建立:"当前不可用） · ❌ `threshold`（同上；像素层的 `layer.threshold()` 可用，MAD 109）

**参数可写，且真的改像素**（与基准图逐像素平均绝对差）：

| 调整 | 配方 | MAD |
|---|---|---|
| 曲线 | `setd` → `T=Crvs` / `Adjs[0].Crv` 点列 | **29.51** |
| 色阶 | `setd` → `T=Lvls` / `Inpt`+`Gmm `+`Outt` | **18.32** |
| 色相饱和度 | `setd` → `T=HStr` / `H`+`Strt`+`Lght` | **4.69** |

> 只建层不设参 = 默认值 = 无变化。要"看起来调过色"，必须走上面的 `setd` 分支，`ps_build.py` 已封装成 `{"type":"adjust","adj":"curves","points":[[0,12],[128,140],[255,248]]}`。

### 1.3 滤镜（11 ✅）

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

❌ `mosaic`：DOM 里**没有** `applyMosaic` 方法（不是权限问题，是方法不存在）。

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
| **扩展 expand** | ❌ | `selection.expand()` 报「没有这种元素」 |
| resizeCanvas / resizeImage / crop | ✅ | 600×400 → 300×200 → crop 200×150 |
| 导出 PNG / JPG / TIFF / PSD / PDF | ✅ | `saveAs` + 对应 Options；PSD `layers=true` 保层 |
| 存为 Web（PNG24 / JPG） | ✅ | `exportDocument(f, ExportType.SAVEFORWEB, o)` |
| **WebP** | ❌ | 无 `WebPSaveOptions` 构造器 |

**PSD 往返保真**（本例 16 层）：`saveAs(psd)` → `close` → `app.open` 回读，图层数、名称、类型（TEXT/NORMAL/LayerSet）、不透明度、文本内容全部一致。

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

## 3. 坑位（12 条，全部踩过）

**1. COM 的 `Documents.Count` 不可靠** → 判断"有没有文档"只信 JSX 的 `app.documents.length`。

**2. `app.displayDialogs = DialogModes.ALL` 会挂死整条链路。**
一旦某条命令内部报错，PS 会弹出无人可点的模态框，`DoJavaScriptFile` **永久阻塞**（实测卡 4 分钟，最后只能 `taskkill`）。**永远保持 `DialogModes.NO`**，Python 侧再加超时兜底。

**3. 图层蒙版建不出来（本机 25.0.0）。**
试过 `Mk Chnl`（charID）、`make channel`（stringID）、带/不带 `At` 引用、`revealAll`/`revealSelection`、显式目标图层、`quickMaskMode=false` —— 全部「发生了常规 Photoshop 错误 / 程序错误」。图层对象上也只有 `layerMaskFeather/layerMaskDensity` 这类**改**的属性，没有"加蒙版"的方法。
替代方案（都已验）：**剪贴蒙版**（`grouped=true`）、**选区 + `selection.clear()` 硬擦除**、**组不透明度**、**选区羽化半透明**。`ps_build.py` 的 `erase` 类型就是这条路。

**4. `doc.getPixel()` 不存在。**
想读某点像素只能 `doc.colorSamplers.add([x,y])`，或**导出 PNG 用 Pillow/numpy 量**（推荐，可复算）。本报告所有 MAD 都是这样算的。

**5. 覆盖用户文档 = 数据丢失级错误。**
早期模板写 `while (app.documents.length > 0) app.documents[0].close(...)`，用户开着未保存 PSD 时跑一次就丢光。正确做法：只 `app.documents.add()` 自己那一份，干完只 `doc.close()` 自己那份，并打日志核对 `app.documents.length` 回到 `preexisting`。

**6. 组套组做不到。**
`g2.move(g1, ElementPlacement.INSIDE / PLACEATBEGINNING)` 对 **LayerSet→LayerSet** 恒报「非法参数」（对 ArtLayer→LayerSet 却正常）。`layerSets.add()` 也不会因为激活组而进组。可用替代：**单层组 + 子层 move 进组**；需要视觉分组时用命名前缀（`Rows_R1`）。

**7. 矢量形状图层没有稳定配方。**
`make contentLayer` + `type: solidColorLayer` 报「命令当前不可用」；且失败后残留工作路径会让**后续 `selection.fill` 一起报「命令填充当前不可用」**（状态污染）。老实做：选区 + 填充。

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
    {"type":"adjust","adj":"curves","points":[[0,12],[128,140],[255,248]]},
    {"type":"adjust","adj":"levels","in":[40,200],"gamma":1.0,"out":[0,255]},
    {"type":"adjust","adj":"huesat","hue":0,"sat":60,"light":0},
    {"type":"filter","filter":"gaussianBlur","radius":24,"target":"PanelAccent"},
    {"type":"clip","target":"ClipTop"},
    {"type":"erase","x1":700,"y1":1170,"x2":996,"y2":1250,"target":"Bar"}
  ]
}
```

- `text.y` 是**基线**，不是顶边。
- `filter` 不写 `target` 时作用于"最近一个像素层"。
- `blend` 支持 normal/multiply/screen/overlay/softlight/hardlight/darken/lighten/difference/lineardodge/color/luminosity。

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

## 7. 文件清单

- `scripts/ps_build.py` — 清单驱动器（主力）
- `scripts/ps.py` — 连接/执行/图层树/卡片模板
- `scripts/*.jsx` — do_cutout（抠图）、curves_tone（分通道曲线）、make_poster（旧模板）、list_layers、probe_*
- `examples/manifest_basic.json` / `manifest_full.json`
- `docs/VERIFY.md` — 每条结论的实测记录与失败原文
