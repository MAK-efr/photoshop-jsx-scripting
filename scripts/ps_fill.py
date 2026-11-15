# -*- coding: utf-8 -*-
"""ps_fill.py —— 打开设计师给的 .psd，按图层名换文案/换图，原版式分毫不动

和 ps_build.py 的分工：
  ps_build  从零搭版式（内容与版式都由清单决定）
  ps_fill   复用已有版式（版式在 PSD 里，清单只提供"换什么"）

为什么需要它：设计师交付的 PSD 里有字体、间距、图层样式、智能对象变形，
把它翻译成清单等于重做一遍。直接改图层名指向的内容，才是真实工作流。

清单结构
{
  "template": "tpl_cert.psd",
  "out": {"dir": "_out/fill", "stem": "cert_A", "formats": ["png","psd"]},
  "text":    {"Title": "新标题", "Price": "¥199"},   // 图层名 → 新文案
  "images":  {"Photo": "new.jpg"},                   // 图层名 → 新图（必须是智能对象）
  "visible": {"Badge": false}                        // 图层名 → 显示/隐藏
}

用法
  python ps_fill.py fill.json
  python ps_fill.py fill.json --check
  python ps_fill.py fill.json --dry-run
  python ps_fill.py fill.json --out 别处 --stem 别的名字

硬约束（全部是实测踩出来的）
  1. 原模板文件绝不覆盖：只 saveAs 到新文件名，关文档时 DONOTSAVECHANGES。
  2. images 的目标层必须是**智能对象**，否则 replacedLayerReplaceContents 报 -25920；
     普通像素层只能重新置入（尺寸会丢），所以这里直接判失败并给出改法。
  3. 目标层被隐藏或被图层筛选器挡住时选不中，同样 -25920 → 替换前先置 visible=true。
  4. getByName 不递归，所以用自己写的 findL() 深度优先找。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ps  # noqa: E402
import ps_build  # noqa: E402


def _s(v):
    return ps_build._s(v)


def validate(m, base_dir):
    errs = []
    tpl = m.get("template")
    if not tpl:
        errs.append("缺少 template")
    else:
        tp = Path(tpl)
        if not tp.is_absolute():
            tp = Path(base_dir) / tp
        if not tp.is_file():
            errs.append("模板不存在: %s" % tp)
    out = m.get("out") or {}
    if not out.get("dir"):
        errs.append("缺少 out.dir")
    if not out.get("stem"):
        errs.append("缺少 out.stem")
    for f in (out.get("formats") or ["png"]):
        if str(f).lower() not in ("psd", "png", "jpg", "tif", "pdf", "webp"):
            errs.append("不支持的导出格式: %s" % f)
    for k in ("text", "images", "visible"):
        if m.get(k) is not None and not isinstance(m[k], dict):
            errs.append("%s 必须是 {图层名: 值} 对象" % k)
    for name, p in (m.get("images") or {}).items():
        pp = Path(str(p))
        if not pp.is_absolute():
            pp = Path(base_dir) / pp
        if not pp.is_file():
            errs.append("images.%s 图片不存在: %s" % (name, pp))
    if not (m.get("text") or m.get("images") or m.get("visible")):
        errs.append("text / images / visible 至少要给一个，否则等于什么都没改")
    return errs


def build_jsx(m, base_dir, out_dir, stem):
    tp = Path(m["template"])
    if not tp.is_absolute():
        tp = Path(base_dir) / tp
    imgs = {}
    for k, v in (m.get("images") or {}).items():
        pp = Path(str(v))
        if not pp.is_absolute():
            pp = Path(base_dir) / pp
        imgs[k] = str(pp.resolve()).replace("\\", "/")

    head = r'''#target photoshop
// 由 ps_fill.py 生成，勿手改
(function () {
    var OUT = "%(out)s";
    var STEM = "%(stem)s";
    var TPL = "%(tpl)s";
    var FORMATS = %(formats)s;
    var TEXT = %(text)s;
    var IMAGES = %(images)s;
    var VISIBLE = %(visible)s;
    var log = [];
    function L(s) { log.push(s); }
    function flush() {
        var f = new File(OUT + "/" + STEM + ".log");
        f.encoding = "UTF8"; f.open("w"); f.write(log.join("\n")); f.close();
    }
    function hex(h) { var c = new SolidColor(); c.rgb.hexValue = h; return c; }
    var step = 0, ok = 0, bad = 0;
    function T(name, fn) {
        var myStep = ++step;
        try { var r = fn(); ok++; L("PASS " + myStep + " " + name + (r != null ? "  => " + r : "")); }
        catch (e) { bad++; L("FAIL " + myStep + " " + name + "  !! " + e.message); }
    }
''' % {
        "out": str(out_dir).replace("\\", "/"),
        "stem": stem,
        "tpl": tp.resolve().as_posix(),
        "formats": json.dumps([f.lower() for f in (m["out"].get("formats") or ["png"])]),
        "text": json.dumps({k: str(v) for k, v in (m.get("text") or {}).items()}, ensure_ascii=False),
        "images": json.dumps(imgs, ensure_ascii=False),
        "visible": json.dumps({k: bool(v) for k, v in (m.get("visible") or {}).items()}),
    }

    body = r'''
    // getByName 只在直接成员里找，所以自己写深度优先
    function findL(cont, name) {
        for (var i = 0; i < cont.layers.length; i++) {
            var l = cont.layers[i];
            if (l.name === name) return l;
            if (l.typename === "LayerSet") {
                var r = findL(l, name);
                if (r) return r;
            }
        }
        return null;
    }

    var pre = app.documents.length;
    L("preexisting docs = " + pre + " (一律不碰)");
    app.displayDialogs = DialogModes.NO;
    var D = app.open(new File(TPL));
    T("open template", function () {
        return D.name + " " + D.width.as("px") + "x" + D.height.as("px") + " layers=" + D.layers.length;
    });

    for (var k in TEXT) {
        (function (name) {
            T("text " + name, function () {
                var l = findL(D, name);
                if (!l) throw new Error("找不到图层 " + name);
                if (l.kind !== LayerKind.TEXT) throw new Error(name + " 不是文字层（kind=" + l.kind + "）");
                l.textItem.contents = TEXT[name];
                return "contents=" + l.textItem.contents.replace(/\r/g, "|");
            });
        })(k);
    }

    for (var k2 in IMAGES) {
        (function (name) {
            T("image " + name, function () {
                var l = findL(D, name);
                if (!l) throw new Error("找不到图层 " + name);
                if (l.kind !== LayerKind.SMARTOBJECT) {
                    throw new Error(name + " 不是智能对象（kind=" + l.kind + "）；"
                                    + "请在模板里右键该层 → 转换为智能对象");
                }
                if (!l.visible) l.visible = true;   // 隐藏层选不中，会报 -25920
                D.activeLayer = l;
                var d = new ActionDescriptor();
                d.putPath(charIDToTypeID("null"), new File(IMAGES[name]));
                d.putInteger(charIDToTypeID("PgNm"), 1);
                executeAction(stringIDToTypeID("placedLayerReplaceContents"), d, DialogModes.NO);
                return "replaced " + D.activeLayer.name + " kind=" + D.activeLayer.kind;
            });
        })(k2);
    }

    for (var k3 in VISIBLE) {
        (function (name) {
            T("visible " + name, function () {
                var l = findL(D, name);
                if (!l) throw new Error("找不到图层 " + name);
                l.visible = VISIBLE[name];
                return "visible=" + l.visible;
            });
        })(k3);
    }

'''

    tail = r'''    for (var i = 0; i < FORMATS.length; i++) {
        (function (fmt) {
            T("export " + fmt, function () { return saveFmt(D, fmt, OUT + "/" + STEM); });
        })(FORMATS[i]);
    }

    L("");
    L("SUMMARY pass=" + ok + " fail=" + bad + " layers=" + D.layers.length
      + " size=" + D.width.as("px") + "x" + D.height.as("px"));
    // 只关自己打开的这份；DONOTSAVECHANGES 保证模板文件一个字节都没被改写
    D.close(SaveOptions.DONOTSAVECHANGES);
    L("closed template copy only");
    L("docs left open=" + app.documents.length + " (应=" + pre + ")");
    flush();
})();
'''
    return head + ps_build.SAVE_FMT_JS + body + tail


def main():
    ap = argparse.ArgumentParser(description="按图层名回填已存在的 PSD 模板")
    ap.add_argument("fill")
    ap.add_argument("--out", help="覆盖 out.dir")
    ap.add_argument("--stem", help="覆盖 out.stem")
    ap.add_argument("--dry-run", action="store_true", help="只生成 jsx")
    ap.add_argument("--check", action="store_true", help="只校验清单")
    a = ap.parse_args()

    fpath = Path(a.fill).resolve()
    m = json.loads(fpath.read_text(encoding="utf-8"))
    errs = validate(m, fpath.parent)
    if errs:
        print("清单有问题，未执行：")
        for e in errs:
            print("  -", e)
        return 2
    if a.check:
        print("清单校验通过：text=%d images=%d visible=%d"
              % (len(m.get("text") or {}), len(m.get("images") or {}), len(m.get("visible") or {})))
        return 0

    od = Path(a.out or m["out"]["dir"])
    if not od.is_absolute():
        od = fpath.parent / od
    out_dir = od.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = a.stem or m["out"]["stem"]

    jsx = build_jsx(m, fpath.parent, out_dir, stem)
    jf = out_dir / (stem + "_gen.jsx")
    jf.write_text(jsx, encoding="utf-8")
    print("jsx:", jf)
    if a.dry_run:
        return 0

    ps.run_jsx(jf)
    log = out_dir / (stem + ".log")
    txt = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    print(txt if txt else "!! 没有日志，JSX 可能未跑完")

    miss = 0
    for f in (m["out"].get("formats") or ["png"]):
        p = out_dir / ("%s.%s" % (stem, f))
        got = p.is_file()
        if not got:
            miss += 1
        print(("OK   " if got else "MISS ") + str(p)
              + ("  %d B" % p.stat().st_size if got else ""))
    if "FAIL " in txt or miss:
        print("!! 有失败项，见上")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
