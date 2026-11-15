# -*- coding: utf-8 -*-
"""ps_build.py —— 用一份 JSON 清单驱动 Photoshop 出分层 PSD / PNG / JPG / TIFF

设计原则（每条都对应一次实测失败，见 SKILL.md「坑位」）
  1. 只创建、只操作、只关闭自己 app.documents.add() 的那一个文档；他人文档一律不碰。
  2. 一律写 .jsx 文件再 DoJavaScriptFile；DoJavaScript 单参数签名对引号/换行不友好。
  3. app.displayDialogs 永远保持 DialogModes.NO —— 切到 ALL 后一旦命令内部报错，
     PS 会弹出无人可点的模态框，整条 COM 链路永久阻塞（实测卡死 4 分钟，只能杀进程）。
  4. 日志由 JSX 写文件、Python 读文件；JSX 返回值不可靠。
  5. 组内图层必须 layer.move(group, INSIDE)；artLayers.add() 不会自动进组。
  6. 组套组不能 move（LayerSet→LayerSet 恒报「非法参数」），要在父组的锚点层上
     原位 make layerSection；且 getByName 不递归，第 3 层起必须写链式路径。
  7. adjust 的 type 一律用**类 ID**（如 gradientMapClass），事件 ID 会报"当前不可用"。

清单结构
{
  "out":  {"dir": "相对清单文件或绝对路径", "stem": "产物名", "formats": ["psd","png","jpg","tif"]},
  "doc":  {"w": 1080, "h": 1350, "dpi": 72, "bg": "14161A", "name": "PS-Build"},
  "layers": [ 自底向上排列的图层对象 ]
}

图层对象（type 字段）
  rect    {x1,y1,x2,y2,color,opacity?,blend?,name?}
  text    {text,font,size,color,x,y,tracking?,leading?,justify?,para:[w,h],
           vertical?,warp?,bend?,opacity?,blend?,name?}
  image   {path,x,y,w,h,fit?:cover|contain,opacity?,blend?,name?}
  group   {name,opacity?,blend?,layers:[子图层]}   子层里可再放 group（组套组）
  adjust  {adj:curves|levels|huesat|gradientMap|..., ...参数}
  filter  {filter:gaussianBlur|mosaic|threshold|..., target?:图层名(缺省=最近一个像素层), ...参数}
  clip    {target?}      把最近一个图层设为下方图层的剪贴蒙版
  erase   {x1,y1,x2,y2,target?}   在目标层上硬擦除一个矩形（图层蒙版不可用时的替代）

用法
  python ps_build.py manifest.json
  python ps_build.py manifest.json --dry-run          # 只生成 jsx，不执行
  python ps_build.py manifest.json --check            # 只校验清单
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ps  # noqa: E402  复用连接/重试/JSX 执行

BLEND = {
    "normal": "NORMAL", "multiply": "MULTIPLY", "screen": "SCREEN",
    "overlay": "OVERLAY", "softlight": "SOFTLIGHT", "hardlight": "HARDLIGHT",
    "darken": "DARKEN", "lighten": "LIGHTEN", "difference": "DIFFERENCE",
    "lineardodge": "LINEARDODGE", "color": "COLOR", "luminosity": "LUMINOSITY",
}
JUSTIFY = {"left": "LEFT", "center": "CENTER", "right": "RIGHT",
           "justify": "JUSTIFIED", "justifyall": "JUSTIFYALL"}
WARP = {"arc": "ARC", "arch": "ARCH", "bulge": "BULGE", "wave": "WAVE",
        "rise": "RISE", "fish": "FISH", "shell": "SHELL", "none": "NONE"}
FILTERS = {
    "gaussianBlur": ("applyGaussianBlur", ["radius"]),
    "unsharpMask": ("applyUnSharpMask", ["amount", "radius", "threshold"]),
    "addNoise": ("applyAddNoise", ["amount"]),
    "motionBlur": ("applyMotionBlur", ["angle", "distance"]),
    "highPass": ("applyHighPass", ["radius"]),
    "sharpenMore": ("applySharpenMore", []),
    "invert": ("invert", []),
    "desaturate": ("desaturate", []),
    "posterize": ("posterize", ["levels"]),
    "threshold": ("threshold", ["level"]),
    "mosaic": ("__am_mosaic__", ["cellSize"]),   # DOM 无 applyMosaic，需走 Msc 事件
}
ADJUSTS = {"curves", "levels", "huesat", "bw", "photoFilter", "vibrance",
           "exposure", "colorBalance", "invert", "posterize", "selectiveColor",
           "channelMixer", "colorLookup", "gradientMap"}
# 注意：这里必须是 **class ID**，不是事件 ID。
# 反例：写 "gradientMap"（事件ID 4302）会报「命令"建立:"当前不可用」；
#       写 "gradientMapClass"（class ID）才建得出来。阈值同理，只是它的 class 也不可用。
ADJ_KIND_STR = {
    "gradientMap": "gradientMapClass",
    "curves": "curves", "levels": "levels", "huesat": "hueSaturation",
    "bw": "blackAndWhite", "photoFilter": "photoFilter", "vibrance": "vibrance",
    "exposure": "exposure", "colorBalance": "colorBalance", "invert": "invert",
    "posterize": "posterize", "selectiveColor": "selectiveColor",
    "channelMixer": "channelMixer", "colorLookup": "colorLookup",
}


# ---------------------------------------------------------------- 校验
def validate(m):
    errs = []
    if not isinstance(m, dict):
        return ["清单根必须是对象"]
    doc = m.get("doc") or {}
    for k in ("w", "h"):
        if not isinstance(doc.get(k), int) or doc.get(k) <= 0:
            errs.append("doc.%s 必须是正整数" % k)
    out = m.get("out") or {}
    if not out.get("dir"):
        errs.append("缺少 out.dir")
    if not out.get("stem"):
        errs.append("缺少 out.stem")
    fmts = out.get("formats") or ["png", "psd"]
    for f in fmts:
        if f.lower() not in ("psd", "png", "jpg", "tif", "pdf"):
            errs.append("不支持的导出格式: %s" % f)
    if not isinstance(m.get("layers"), list) or not m["layers"]:
        errs.append("layers 必须是非空数组")
    seen_names = set()

    def walk(layers, where):
        for i, L in enumerate(layers):
            p = "%s[%d]" % (where, i)
            if not isinstance(L, dict):
                errs.append("%s 不是对象" % p)
                continue
            t = L.get("type")
            nm = L.get("name") or ("%s_%d" % (t, i))
            if nm in seen_names:
                errs.append("%s 图层名重复: %s" % (p, nm))
            seen_names.add(nm)
            if t == "rect":
                for k in ("x1", "y1", "x2", "y2", "color"):
                    if k not in L:
                        errs.append("%s 缺少 %s" % (p, k))
                if L.get("blend") and L["blend"].lower() not in BLEND:
                    errs.append("%s 未知混合模式 %s" % (p, L["blend"]))
            elif t == "text":
                for k in ("text", "font", "size", "color", "x", "y"):
                    if k not in L:
                        errs.append("%s 缺少 %s" % (p, k))
                if L.get("justify") and L["justify"].lower() not in JUSTIFY:
                    errs.append("%s 未知对齐 %s" % (p, L["justify"]))
                if L.get("warp") and L["warp"].lower() not in WARP:
                    errs.append("%s 未知变形 %s" % (p, L["warp"]))
                if L.get("para") and len(L["para"]) != 2:
                    errs.append("%s para 必须是 [宽,高]" % p)
            elif t == "image":
                for k in ("path", "x", "y"):
                    if k not in L:
                        errs.append("%s 缺少 %s" % (p, k))
                if not Path(str(L.get("path", ""))).is_file():
                    errs.append("%s 图片不存在: %s" % (p, L.get("path")))
            elif t == "group":
                if not isinstance(L.get("layers"), list):
                    errs.append("%s group 缺少 layers" % p)
                else:
                    walk(L["layers"], p + ".layers")
            elif t == "adjust":
                if L.get("adj") not in ADJUSTS:
                    errs.append("%s 未知调整类型 %s" % (p, L.get("adj")))
            elif t == "filter":
                if L.get("filter") not in FILTERS:
                    errs.append("%s 未知滤镜 %s" % (p, L.get("filter")))
            elif t in ("clip", "erase"):
                pass
            else:
                errs.append("%s 未知 type: %s" % (p, t))

    walk(m["layers"], "layers")
    return errs


# ---------------------------------------------------------------- JSX 生成
def _s(v):
    """JS 字符串字面量。"""
    return '"' + str(v).replace('\\', '\\\\').replace('"', '\\"').replace('\r', '\\r').replace('\n', '\\n') + '"'


def _num(v):
    return repr(float(v)) if isinstance(v, float) else str(int(v))


def _common(L, var="l"):
    """opacity / blend / name 三类公共属性。"""
    out = []
    if L.get("opacity") is not None:
        out.append("%s.opacity = %s;" % (var, _num(L["opacity"])))
    if L.get("blend"):
        out.append("%s.blendMode = BlendMode.%s;" % (var, BLEND[L["blend"].lower()]))
    return out


PRELUDE = r'''#target photoshop
// 由 ps_build.py 生成，勿手改
(function () {
    var OUT = "%(out)s";
    var STEM = "%(stem)s";
    var FORMATS = %(formats)s;
    var log = [];
    function L(s) { log.push(s); }
    function flush() {
        var f = new File(OUT + "/" + STEM + ".log");
        f.encoding = "UTF8"; f.open("w"); f.write(log.join("\n")); f.close();
    }
    function hex(h) { var c = new SolidColor(); c.rgb.hexValue = h; return c; }
    var step = 0, ok = 0, bad = 0;
    function T(name, fn) {
        var myStep = ++step;   // 必须捕获，嵌套 T 执行期全局 step 已变，直接读会串号
        try { var r = fn(); ok++; L("PASS " + myStep + " " + name + (r != null ? "  => " + r : "")); }
        catch (e) { bad++; L("FAIL " + myStep + " " + name + "  !! " + e.message); }
    }
    function need(n) { var l = D.artLayers.getByName(n); return l; }
    function rect(x1, y1, x2, y2, color) {
        D.selection.select([[x1, y1], [x2, y1], [x2, y2], [x1, y2]]);
        D.selection.fill(hex(color));
        D.selection.deselect();
    }
    function setCurves(pts) {
        var d = new ActionDescriptor();
        var r = new ActionReference();
        r.putEnumerated(charIDToTypeID("AdjL"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        d.putReference(charIDToTypeID("null"), r);
        var d2 = new ActionDescriptor();
        var adjs = new ActionList();
        var a1 = new ActionDescriptor();
        var rc = new ActionReference();
        rc.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Chnl"), charIDToTypeID("Cmps"));
        a1.putReference(charIDToTypeID("Chnl"), rc);
        var list = new ActionList();
        for (var i = 0; i < pts.length; i++) {
            var p = new ActionDescriptor();
            p.putDouble(charIDToTypeID("Hrzn"), pts[i][0]);
            p.putDouble(charIDToTypeID("Vrtc"), pts[i][1]);
            list.putObject(charIDToTypeID("Pnt "), p);
        }
        a1.putList(charIDToTypeID("Crv "), list);
        adjs.putObject(charIDToTypeID("CrvA"), a1);
        d2.putList(charIDToTypeID("Adjs"), adjs);
        d.putObject(charIDToTypeID("T   "), charIDToTypeID("Crvs"), d2);
        executeAction(charIDToTypeID("setd"), d, DialogModes.NO);
    }
    function setLevels(inb, inw, gamma, outb, outw) {
        var d = new ActionDescriptor();
        var r = new ActionReference();
        r.putEnumerated(charIDToTypeID("AdjL"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        d.putReference(charIDToTypeID("null"), r);
        var d2 = new ActionDescriptor();
        var adjs = new ActionList();
        var a1 = new ActionDescriptor();
        var rc = new ActionReference();
        rc.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Chnl"), charIDToTypeID("Cmps"));
        a1.putReference(charIDToTypeID("Chnl"), rc);
        var li = new ActionList(); li.putInteger(inb); li.putInteger(inw);
        a1.putList(charIDToTypeID("Inpt"), li);
        a1.putDouble(charIDToTypeID("Gmm "), gamma);
        var lo = new ActionList(); lo.putInteger(outb); lo.putInteger(outw);
        a1.putList(charIDToTypeID("Outt"), lo);
        adjs.putObject(charIDToTypeID("LvlA"), a1);
        d2.putList(charIDToTypeID("Adjs"), adjs);
        d.putObject(charIDToTypeID("T   "), charIDToTypeID("Lvls"), d2);
        executeAction(charIDToTypeID("setd"), d, DialogModes.NO);
    }
    function setHueSat(hue, sat, light) {
        var d = new ActionDescriptor();
        var r = new ActionReference();
        r.putEnumerated(charIDToTypeID("AdjL"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        d.putReference(charIDToTypeID("null"), r);
        var d2 = new ActionDescriptor();
        var adjs = new ActionList();
        var a1 = new ActionDescriptor();
        var rc = new ActionReference();
        rc.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Chnl"), charIDToTypeID("Cmps"));
        a1.putReference(charIDToTypeID("Chnl"), rc);
        a1.putInteger(charIDToTypeID("H   "), hue);
        a1.putInteger(charIDToTypeID("Strt"), sat);
        a1.putInteger(charIDToTypeID("Lght"), light);
        adjs.putObject(charIDToTypeID("HStr"), a1);
        d2.putList(charIDToTypeID("Adjs"), adjs);
        d2.putBoolean(charIDToTypeID("Clrz"), false);
        d.putObject(charIDToTypeID("T   "), charIDToTypeID("HStr"), d2);
        executeAction(charIDToTypeID("setd"), d, DialogModes.NO);
    }
    function mkAdjust(kindStr) {
        var d = new ActionDescriptor();
        var r = new ActionReference();
        r.putClass(stringIDToTypeID("adjustmentLayer"));
        d.putReference(stringIDToTypeID("null"), r);
        var d2 = new ActionDescriptor();
        d2.putObject(stringIDToTypeID("type"), stringIDToTypeID(kindStr), new ActionDescriptor());
        d.putObject(stringIDToTypeID("using"), stringIDToTypeID("adjustmentLayer"), d2);
        executeAction(stringIDToTypeID("make"), d, DialogModes.NO);
        return D.activeLayer;
    }

    var pre = app.documents.length;
    L("preexisting docs = " + pre + " (一律不碰)");
    app.displayDialogs = DialogModes.NO;
    var D = app.documents.add(new UnitValue(%(W)s, "px"), new UnitValue(%(H)s, "px"),
                              %(DPI)s, %(NAME)s, NewDocumentMode.RGB, DocumentFill.TRANSPARENT);
    var lastPixel = null;   // 最近一个像素层，供 filter/erase/clip 定位
    // 新建文档必带一个空白占位层（WHITE→"背景"，TRANSPARENT→"图层 1"）。
    // 不删它（删唯一图层会报错），而是把它当底色层复用 —— 见下面 bg 的生成代码。
'''

EPILOGUE = r'''
    // ---------- 导出 ----------
    for (var i = 0; i < FORMATS.length; i++) {
        var f = FORMATS[i];
        (function (fmt) {
            T("export " + fmt, function () {
                var file = new File(OUT + "/" + STEM + "." + fmt);
                if (fmt === "png") {
                    // 实测：不显式指定 compression 时 PS 存的是"几乎不压缩"的 PNG，
                    // 1080x1350 平涂卡片会到 4.3 MB（≈ 原始字节数）。必须给 9。
                    var po = new PNGSaveOptions(); po.compression = 9; po.interlaced = false;
                    D.saveAs(file, po, true, Extension.LOWERCASE);
                }
                else if (fmt === "psd") {
                    var o = new PhotoshopSaveOptions(); o.layers = true; o.embedColorProfile = true;
                    D.saveAs(file, o, false, Extension.LOWERCASE);
                } else if (fmt === "jpg") {
                    var j = new JPEGSaveOptions(); j.quality = 12; j.embedColorProfile = true;
                    D.saveAs(file, j, true, Extension.LOWERCASE);
                } else if (fmt === "tif") {
                    var t = new TiffSaveOptions(); t.imageCompression = TIFFEncoding.TIFFLZW; t.layers = true;
                    D.saveAs(file, t, true, Extension.LOWERCASE);
                } else if (fmt === "pdf") {
                    D.saveAs(file, new PDFSaveOptions(), true, Extension.LOWERCASE);
                }
                return file.fsName;
            });
        })(f);
    }

    L("");
    L("SUMMARY pass=" + ok + " fail=" + bad + " layers=" + D.layers.length
      + " size=" + D.width.as("px") + "x" + D.height.as("px"));
    // 先关自己这一份，再核对文档数——否则日志会把"自己那份"算成残留
    D.close(SaveOptions.DONOTSAVECHANGES);
    L("closed own doc only");
    L("docs left open=" + app.documents.length + " (应=" + pre + ")");
    flush();
})();
'''


def emit_layer(L, depth=0, stack=None):
    """把一个图层对象翻译成 JSX 语句。

    stack = 祖先组名列表（[] / None 表示文档根）。
    组套组不能靠 move（对 LayerSet 恒报「非法参数」），正确做法是
    **在父组内的锚点图层上原位 make layerSection**，新组会插在锚点前、即父组内部。

    关键坑：DOM 的 getByName 只在**当前集合的直接成员**里找，不做递归。
    所以第 3 层及更深必须用链式路径 A.layerSets.getByName("B")... 去定位，
    否则 `D.artLayers.getByName("Outer__anchor")` 会报「没有这种元素」（实测已踩）。
    """
    stack = list(stack or [])
    t = L["type"]
    nm = L.get("name") or "%s_%d" % (t, depth)
    out = []
    in_group = bool(stack)

    def gref():
        """最内层组的 JS 表达式。"""
        e = "D"
        for g in stack:
            e += '.layerSets.getByName(%s)' % _s(g)
        return e

    def into_group(var):
        if in_group:
            return ['  %s.move(%s, ElementPlacement.INSIDE);' % (var, gref())]
        return []

    if t == "rect":
        out.append('T(%s, function () {' % _s("rect " + nm))
        out.append('  var l = D.artLayers.add(); l.name = %s; D.activeLayer = l;' % _s(nm))
        out.append('  rect(%s, %s, %s, %s, %s);' % (_num(L["x1"]), _num(L["y1"]), _num(L["x2"]), _num(L["y2"]), _s(L["color"])))
        out += ["  " + x for x in _common(L)]
        out += into_group("l")
        out.append('  lastPixel = l;')
        out.append('  return l.name + " op=" + l.opacity;')
        out.append('});')
    elif t == "text":
        txt = "\\r".join(str(L["text"]).split("\n"))
        out.append('T(%s, function () {' % _s("text " + nm))
        out.append('  var l = D.artLayers.add(); l.name = %s; l.kind = LayerKind.TEXT; D.activeLayer = l;' % _s(nm))
        out.append('  var ti = l.textItem;')
        if L.get("para"):
            out.append('  ti.kind = TextType.PARAGRAPHTEXT;')
            out.append('  ti.width = new UnitValue(%s, "px"); ti.height = new UnitValue(%s, "px");' % (_num(L["para"][0]), _num(L["para"][1])))
        else:
            out.append('  ti.kind = TextType.POINTTEXT;')
        out.append('  ti.contents = %s;' % _s(txt))
        out.append('  ti.font = %s;' % _s(L["font"]))
        out.append('  ti.size = new UnitValue(%s, "pt");' % _num(L["size"]))
        out.append('  ti.color = hex(%s);' % _s(L["color"]))
        out.append('  ti.justification = Justification.%s;' % JUSTIFY[(L.get("justify") or "left").lower()])
        if L.get("tracking") is not None:
            out.append('  ti.tracking = %s;' % _num(L["tracking"]))
        if L.get("leading") is not None:
            # 实测：不先关自动行距，写 leading 会抛「文本设置为自动行距，并且没有特殊的行距值」
            out.append('  ti.useAutoLeading = false;')
            out.append('  ti.leading = new UnitValue(%s, "pt");' % _num(L["leading"]))
        if L.get("vertical"):
            out.append('  ti.direction = Direction.VERTICAL;')
        if L.get("warp"):
            out.append('  ti.warpStyle = WarpStyle.%s;' % WARP[L["warp"].lower()])
            out.append('  ti.warpBend = %s;' % _num(L.get("bend", 50)))
        out.append('  ti.position = [new UnitValue(%s, "px"), new UnitValue(%s, "px")];' % (_num(L["x"]), _num(L["y"])))
        out += ["  " + x for x in _common(L)]
        out += into_group("l")
        out.append('  return "font=" + ti.font + " size=" + ti.size;')
        out.append('});')
    elif t == "image":
        fit = (L.get("fit") or "cover").lower()
        out.append('T(%s, function () {' % _s("image " + nm))
        out.append('  var src = app.open(new File(%s));' % _s(L["path"]))
        out.append('  var l = src.activeLayer.duplicate(D, ElementPlacement.PLACEATBEGINNING);')
        out.append('  src.close(SaveOptions.DONOTSAVECHANGES);')
        out.append('  l.name = %s; D.activeLayer = l;' % _s(nm))
        out.append('  var b = l.bounds;')
        out.append('  var bw = b[2].as("px") - b[0].as("px"), bh = b[3].as("px") - b[1].as("px");')
        tw = L.get("w"); th = L.get("h")
        if tw and th:
            if fit == "contain":
                out.append('  var s = Math.min(%s / bw, %s / bh) * 100;' % (_num(tw), _num(th)))
            else:
                out.append('  var s = Math.max(%s / bw, %s / bh) * 100;' % (_num(tw), _num(th)))
            out.append('  l.resize(s, s, AnchorPosition.TOPLEFT);')
        out.append('  var b2 = l.bounds;')
        out.append('  l.translate(%s - b2[0].as("px"), %s - b2[1].as("px"));' % (_num(L["x"]), _num(L["y"])))
        out += ["  " + x for x in _common(L)]
        out += into_group("l")
        out.append('  lastPixel = l;')
        out.append('  return "bounds=" + l.bounds[0].as("px") + "," + l.bounds[1].as("px");')
        out.append('});')
    elif t == "group":
        out.append('T(%s, function () {' % _s("group " + nm))
        if not in_group:
            out.append('  var g = D.layerSets.add(); g.name = %s;' % _s(nm))
        else:
            out.append('  D.activeLayer = %s.artLayers.getByName(%s);' % (gref(), _s(stack[-1] + "__anchor")))
            out.append('  var d = new ActionDescriptor();')
            out.append('  var rc = new ActionReference(); rc.putClass(stringIDToTypeID("layerSection"));')
            out.append('  d.putReference(stringIDToTypeID("null"), rc);')
            out.append('  var rt = new ActionReference(); rt.putEnumerated(stringIDToTypeID("layer"), stringIDToTypeID("ordinal"), stringIDToTypeID("targetEnum"));')
            out.append('  d.putReference(stringIDToTypeID("at"), rt);')
            out.append('  executeAction(stringIDToTypeID("make"), d, DialogModes.NO);')
            out.append('  var g = D.activeLayer; g.name = %s;' % _s(nm))
        out.append('  var anchor = D.artLayers.add(); anchor.name = %s + "__anchor";' % _s(nm))
        out.append('  anchor.move(g, ElementPlacement.INSIDE);')
        for child in L["layers"]:
            out.append("\n".join(emit_layer(child, depth + 1, stack + [nm])))
        out.append('  anchor.remove();')
        out += ["  " + x for x in _common(L, var="g")]
        out.append('  return "children=" + g.layers.length;')
        out.append('});')
    elif t == "adjust":
        adj = L["adj"]
        out.append('T(%s, function () {' % _s("adjust " + adj + " " + nm))
        out.append('  var l = mkAdjust(%s); l.name = %s;' % (_s(ADJ_KIND_STR[adj]), _s(nm)))
        if adj == "curves":
            pts = L.get("points") or [[0, 0], [255, 255]]
            out.append('  setCurves(%s);' % json.dumps(pts))
        elif adj == "levels":
            i0, i1 = (L.get("in") or [0, 255])[:2]
            o0, o1 = (L.get("out") or [0, 255])[:2]
            out.append('  setLevels(%s, %s, %s, %s, %s);' % (_num(i0), _num(i1), _num(L.get("gamma", 1.0)), _num(o0), _num(o1)))
        elif adj == "huesat":
            out.append('  setHueSat(%s, %s, %s);' % (_num(L.get("hue", 0)), _num(L.get("sat", 0)), _num(L.get("light", 0))))
        out += ["  " + x for x in _common(L)]
        out.append('  return "kind=" + l.kind;')
        out.append('});')
    elif t == "filter":
        fn, args = FILTERS[L["filter"]]
        vals = ", ".join(_num(L[a]) for a in args)
        tgt = L.get("target")
        out.append('T(%s, function () {' % _s("filter " + L["filter"]))
        if tgt:
            out.append('  var t = D.layers.getByName(%s); D.activeLayer = t;' % _s(tgt))
        else:
            out.append('  if (!lastPixel) throw new Error("没有可作用的像素层"); D.activeLayer = lastPixel;')
        if fn == "__am_mosaic__":
            out.append('  var d = new ActionDescriptor();')
            out.append('  var r = new ActionReference(); r.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));')
            out.append('  d.putReference(charIDToTypeID("null"), r);')
            out.append('  d.putInteger(charIDToTypeID("ClSz"), %s);' % vals)
            out.append('  executeAction(charIDToTypeID("Msc "), d, DialogModes.NO);')
        else:
            out.append('  D.activeLayer.%s(%s);' % (fn, vals))
        out.append('  return "applied";')
        out.append('});')
    elif t == "clip":
        tgt = L.get("target")
        out.append('T(%s, function () {' % _s("clip"))
        if tgt:
            out.append('  var c = D.layers.getByName(%s); D.activeLayer = c;' % _s(tgt))
        else:
            out.append('  var c = D.activeLayer;')
        out.append('  c.grouped = true;')
        out.append('  return "grouped=" + c.grouped;')
        out.append('});')
    elif t == "erase":
        tgt = L.get("target")
        out.append('T(%s, function () {' % _s("erase " + nm))
        if tgt:
            out.append('  var e = D.layers.getByName(%s); D.activeLayer = e;' % _s(tgt))
        else:
            out.append('  if (!lastPixel) throw new Error("没有可擦除的像素层"); D.activeLayer = lastPixel;')
        out.append('  D.selection.select([[%s, %s], [%s, %s], [%s, %s], [%s, %s]]);'
                   % (_num(L["x1"]), _num(L["y1"]), _num(L["x2"]), _num(L["y1"]),
                      _num(L["x2"]), _num(L["y2"]), _num(L["x1"]), _num(L["y2"])))
        out.append('  D.selection.clear(); D.selection.deselect();')
        out.append('  return "erased";')
        out.append('});')
    else:
        raise ValueError("未知 type: %s" % t)
    return out


def build_jsx(m, out_dir, stem):
    doc = m["doc"]
    fmts = [f.lower() for f in (m["out"].get("formats") or ["png", "psd"])]
    head = PRELUDE % {
        "out": str(out_dir).replace("\\", "/"),
        "stem": stem,
        "formats": json.dumps(fmts),
        "W": doc["w"], "H": doc["h"], "DPI": doc.get("dpi", 72),
        "NAME": _s(doc.get("name", "PS-Build")),
    }
    body = []
    if doc.get("bg"):
        # 复用新建文档自带的占位层当 BG，避免产物多一层空白
        body.append('T("bg", function () { var l = (D.layers.length === 1) ? D.layers[0] : D.artLayers.add();'
                    ' l.name = "BG"; D.activeLayer = l;')
        body.append('  rect(0, 0, %s, %s, %s); lastPixel = l; return "bg"; });'
                    % (_num(doc["w"]), _num(doc["h"]), _s(doc["bg"])))
    for L in m["layers"]:
        body += emit_layer(L)
    return head + "\n".join(body) + EPILOGUE


def main():
    ap = argparse.ArgumentParser(description="用 JSON 清单驱动 Photoshop 出图")
    ap.add_argument("manifest")
    ap.add_argument("--out", help="覆盖清单里的 out.dir")
    ap.add_argument("--stem", help="覆盖清单里的 out.stem")
    ap.add_argument("--dry-run", action="store_true", help="只生成 jsx，不执行")
    ap.add_argument("--check", action="store_true", help="只校验清单")
    a = ap.parse_args()

    mpath = Path(a.manifest).resolve()
    m = json.loads(mpath.read_text(encoding="utf-8"))
    # 图片路径按"清单文件所在目录"解析，清单可以整体搬走
    def _abs(layers):
        for L in layers:
            if L.get("type") == "image" and L.get("path"):
                pp = Path(L["path"])
                if not pp.is_absolute():
                    L["path"] = str((mpath.parent / pp).resolve())
            elif L.get("type") == "group":
                _abs(L.get("layers") or [])
    _abs(m.get("layers") or [])
    errs = validate(m)
    if errs:
        print("清单有问题，未执行：")
        for e in errs:
            print("  -", e)
        return 2
    if a.check:
        print("清单校验通过：layers=%d" % len(m["layers"]))
        return 0

    # out.dir 同样按"清单文件所在目录"解析，整包搬走不变
    od = Path(a.out or m["out"]["dir"])
    if not od.is_absolute():
        od = mpath.parent / od
    out_dir = od.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = a.stem or m["out"]["stem"]
    jsx = build_jsx(m, out_dir, stem)
    jf = out_dir / (stem + "_gen.jsx")
    jf.write_text(jsx, encoding="utf-8")
    print("jsx:", jf)
    if a.dry_run:
        return 0

    ps.run_jsx(jf)
    log = out_dir / (stem + ".log")
    if log.is_file():
        txt = log.read_text(encoding="utf-8", errors="replace")
        print(txt)
        if "FAIL " in txt:
            print("!! 日志里有 FAIL，见上")
    else:
        print("!! 没有日志，JSX 可能未跑完")

    for f in (m["out"].get("formats") or ["png", "psd"]):
        p = out_dir / ("%s.%s" % (stem, f))
        print(("OK   " if p.is_file() else "MISS ") + str(p)
              + ("  %d B" % p.stat().st_size if p.is_file() else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
