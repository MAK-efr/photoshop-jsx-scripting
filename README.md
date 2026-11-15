# Photoshop 脚本化出图（photoshop-jsx-scripting）

用一份 JSON 清单驱动 Photoshop 出**分层可编辑**的 PSD / PNG / JPG / TIFF，不开界面、不点鼠标。

Photoshop 是有官方自动化接口的（`Photoshop.Application` + ExtendScript），所以这个项目**不是逆向**，而是把 Adobe 已经给的东西接成一条能干活的生产线：Python 决定内容，PS 负责执行。

```bash
python scripts/ps_build.py examples/manifest_basic.json       # 最小例子
python scripts/ps_build.py examples/manifest_full.json        # 全特性：15 条指令 → 13 层
python scripts/ps_build.py examples/manifest_recovered.json   # 渐变映射 + 马赛克 + 三层嵌套组
python scripts/ps_build.py examples/manifest_recovered2.json  # 图层蒙版 + 矢量形状层 + WebP
```

产物（`examples/_out/`）：`caps.psd` 13 层可编辑 · `caps.png` 125 KB · `caps.jpg` 282 KB

---

## 能做什么（全部有实测证据，见 [docs/VERIFY.md](docs/VERIFY.md)）

| 能力 | 状态 | 关键实测数据 |
|---|---|---|
| 图层 / 命名 / 不透明度 / 混合模式 | ✅ | 不透明度写 30 读回 30.196（有量化） |
| 图层组 | ✅ | 子层必须 `move(g, INSIDE)`；`add()` 不会自动进组（实测 `group.layers.length` 仍为 0） |
| **组套组（任意深度）** | ✅ | `move`/`duplicate` 全「非法参数」；**在父组锚点层上 `make layerSection`** 才行（实测 `Outer>Inner>子层` 三层回读保真） |
| 剪贴蒙版 | ✅ | 白块内 (255,0,255)、块外 (26,26,26)，两版 MAD 5.10 |
| **图层蒙版** | ✅ | `Mk` + `Nw=Chnl` + `At=Chnl/Chnl/**Msk**` + `Usng=UsrM/RvlA、HdAl、RvlS、HdSl`；`RvlS` 后选区外 alpha=0、选区内 255；蒙版可继续涂黑白 |
| **矢量形状层** | ✅ | `contentLayer` + `type=solidColorLayer` + `shape=rectangle/ellipse` + `strokeStyle`；回读 `SOLIDFILL` 且仍有 1 条矢量路径 |
| 调整层 | ✅ 14 种 | 曲线 / 色阶 / 色相饱和度 / 黑白 / 照片滤镜 / 自然饱和度 / 曝光度 / 色彩平衡 / 反相 / 色调分离 / 选取颜色 / 通道混合器 / 颜色查找 / **渐变映射** |
| 调整参数真的生效 | ✅ | 曲线 MAD **29.51**、色阶 **18.32**、渐变映射 **45.84**（vs 基准图逐像素） |
| 滤镜 | ✅ 12 种 | 高斯 12.25 / USM 7.87 / 加噪 68.72 / 反相 53.81 / 色调分离 39.86 / 高反差 26.41 / **马赛克 8.92** |
| 文字：点 / 段落 / 竖排 / 变形 | ✅ | 字体回读 `NotoSansSC-Black` 完全一致；`\r` 换行；行距需先 `useAutoLeading=false` |
| 图片置入（cover/contain） | ✅ | `app.open` → `duplicate` → 按 bounds 缩放定位 |
| 选区：羽化 / 收缩 / 反选 | ✅ | 100 px 选区 −10 → 80 px |
| **选区：扩展** | ⚠️ | DOM 版报「没有这种元素」；AM `Expn` 不管传多少只扩 1px → 自己读 bounds 算再 `select()` |
| 导出 PNG/JPG/TIFF/PSD/PDF | ✅ | **PNG 必须显式 `compression=9`**：默认 4,377,873 B → 19,372 B |
| 存为 Web（PNG24/JPG） | ✅ | `exportDocument(..., SAVEFORWEB, o)` |
| **WebP** | ✅ | `SaveDocumentType.WEBP` 不存在，但 AM `save` + `as=WebPFormat{compression,quality}` 可用；900×600 → 14 KB |
| 智能对象 / 智能滤镜 | ✅ | `placedLayerEditContents` 能打开内部 `.psb` |
| 本地抠图（选择主体） | ✅ | `autoCutout` 走本机 Sensei，非云端 |
| 生成式填充 / 扩图 / 消除物体 | ❌ | 走 Firefly 云端，中国大陆恒返回 `-25920`（地区锁，非本机问题） |

## 清单长什么样

```jsonc
{
  "out": {"dir":"./_out","stem":"caps","formats":["psd","png","jpg"]},
  "doc": {"w":1080,"h":1350,"dpi":72,"bg":"14161A"},
  "layers": [
    {"type":"text","text":"AI 直连 PS","font":"NotoSansSC-Black","size":118,
     "color":"F2EEE7","x":84,"y":350,"tracking":10},
    {"type":"group","name":"Rows","layers":[
      {"type":"text","text":"图层 / 组 / 剪贴蒙版","font":"NotoSansSC-Medium","size":30,
       "color":"F2EEE7","x":84,"y":830}
    ]},
    {"type":"image","path":"examples/assets/demo_tile.png","x":84,"y":470,"w":420,"h":300,"fit":"cover"},
    {"type":"adjust","adj":"curves","points":[[0,12],[128,140],[255,248]]},
    {"type":"filter","filter":"gaussianBlur","radius":24,"target":"PanelAccent"},
    {"type":"clip","target":"ClipTop"},
    {"type":"erase","x1":700,"y1":1170,"x2":996,"y2":1250,"target":"Bar"}
  ]
}
```

图层类型：`rect` `text` `image` `group` `adjust` `filter` `clip` `erase`。字段速查见 [SKILL.md](SKILL.md#4-清单字段速查)。

## 两轮复测，翻了六案

先后有 7 项被标成 ❌。按「把同一能力的全部表达方式列完 + 留一个能过的对照组」重测，**6 项都是我的用法错**，不是 Photoshop 不支持：

| 原判 | 真相 |
|---|---|
| 渐变映射不支持 | 用了事件 ID `gradientMap`(4302)，建层要类 ID **`gradientMapClass`**(GdMp) |
| 马赛克不支持 | 只试了 DOM 的 `applyMosaic`（不存在），该走 AM 事件 **`Msc `** + 整数键 `ClSz` |
| 组套组不支持 | 只试了 `move`/`duplicate`（都报错），该在父组**锚点层上 `make layerSection`** |
| 图层蒙版不支持 | `At` 的枚举值要写 `Msk `（= stringID `mask`），不是 `maskChannel`；且 charID 必须满 4 字符 |
| 矢量形状层不支持 | 只给了 `null` 引用，缺 `shape` / `strokeStyle` 两层描述符 |
| WebP 不支持 | 只试了 `As=WebP`（charID），正解是 `as=WebPFormat` 对象 |

只剩**阈值调整层**一项：10 种写法全堵，而同一段骨架换 curves / posterize / invert 全过（对照组），确证本版本建不出来 —— 用像素层 `layer.threshold()` 代替。复测明细见 [docs/VERIFY.md §8、§9](docs/VERIFY.md)。

## 安装

```bash
pip install pywin32 pillow        # 只需这两个
```

Photoshop 需支持 COM 自动化（CS6 以后都支持，本项目在 **25.0.0** 上验证）。**不需要** SDK、不需要装扩展、不需要开「允许脚本」。

**顺序很重要**：先完全退出所有 Photoshop 进程，然后让 COM 自己拉起；手动启动的实例不一定注册到 ROT，此时 `Dispatch` 会永久阻塞（见坑位 11）。

## 14 个坑（全部用失败换来的）

摘要，完整版见 [SKILL.md](SKILL.md#3-坑位13-条全部踩过)：

1. `Documents.Count` 不可靠 → 只信 JSX 的 `app.documents.length`
2. **`displayDialogs = ALL` 会挂死整条链路**（模态框无人可点，`DoJavaScriptFile` 永久阻塞）
3. 图层蒙版：`At` 的枚举值必须是 `Msk `，且 `Nw  ` / `At  ` / `Mk  ` 都是 4 字符
4. `doc.getPixel()` 不存在 → 导出 PNG 用 numpy 量
5. 覆盖用户文档 = 数据丢失 → 只碰自己 `add()` 的那一份
6. 组套组不能 `move`，要在父组锚点上 `make layerSection`
7. 矢量形状层要一次给全 `type` / `shape` / `strokeStyle` 三层；失败残留工作路径会污染 `selection.fill`
8. 填充层不能用 `kind` 建，必须 `make AdjL`
9. 新建文档自带占位层 → 删它会报错，直接改名当底色用
10. 组内新增图层要显式 `move`
11. 手动启动的 PS 可能不注册 ROT，`Dispatch` 卡死
12. 子线程调 COM 必须先 `pythoncom.CoInitialize()`
13. `getByName` 不递归，第 3 层起要写链式路径（这是组套组唯一的翻车点）
14. **`charIDToTypeID` 只吃 4 个字符**：`Nw ` / `At ` / `Mk ` 只有 3 字符，会在构造描述符时就抛「非法参数」，看起来像「功能不支持」

## 仓库结构

```
SKILL.md              # 给 AI 用的技能说明（能力矩阵 + 坑位 + 字段速查）
scripts/ps_build.py   # 清单驱动器（主力）
scripts/ps.py         # 连接 / 执行 jsx / 图层树 / 卡片模板
scripts/*.jsx         # 抠图、分通道曲线、海报模板、探针
examples/             # 四份可直接跑的清单 + 素材
docs/VERIFY.md        # 每条结论的实测记录与失败原文
```

## 边界

- 只覆盖 **Windows + 已安装的桌面版 Photoshop**；不含 UXP 插件形态。
- 生成式功能（Firefly）在中国大陆不可用，这是 Adobe 的地区策略，不是本项目的问题。
- 模板里的字体名是**本机**可用的 PostScript 名（`NotoSansSC-*` 等）；换机器前先 `ps.py info` 看字体数，用错字体不会报错，只会静默回落。

## 许可证

自有代码 MIT。Photoshop 是 Adobe 的商标与商业软件，本项目不含、也不分发其任何二进制。详见 [NOTICE.md](NOTICE.md)。
