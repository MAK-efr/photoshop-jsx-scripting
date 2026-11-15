# -*- coding: utf-8 -*-
"""
ps.py — Photoshop COM/ExtendScript 驱动层（AI 接入用）

设计要点
  1. 一律写 .jsx 文件再用 DoJavaScriptFile 执行 —— 免疫字符串转义问题。
  2. 内容参数由 Python 侧生成并注入 JSX —— 让"AI 决定内容、PS 执行"成立。
  3. 日志由 JSX 写文件、Python 读文件 —— JSX 的返回值不可靠。

用法
  python ps.py info
  python ps.py exec <script.jsx>
  python ps.py card "<主标题>" "<副标题>" [--out 目录] [--size 1080x1350]
  python ps.py dump <输出目录>            # 列出当前文档图层结构
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PS_PROGID = 'Photoshop.Application'


def _retry(fn, tries=20, delay=1.5):
    """三类"不是错误，是稍后再问"的情况都要重试：

    1. RPC_E_SERVERCALL_RETRYLATER (-2147417846)
       PS 正被用户操作 → 报"消息筛选器显示应用程序正在使用中"。
    2. RPC_E_DISCONNECTED (-2147220995)
       Dispatch 已返回代理，但 PS 进程还在启动 → 报"对象没有连接到服务器"。
       这一条是实测踩到的：COM 拉起 PS 后立刻读 Version 必报此错。
    3. CO_E_SERVER_EXEC_FAILURE (-2146959355)
       PS 未运行时的首次拉起，偶发"服务器运行失败"，重试即可。
    """
    import time
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:          # pywintypes.com_error
            last = e
            msg = str(e)
            code = e.args[0] if getattr(e, 'args', None) and e.args else None
            if (code in (-2147417846, -2147220995, -2146959355)
                    or '消息筛选器' in msg
                    or 'call was rejected' in msg.lower()
                    or '没有连接到服务器' in msg
                    or '服务器运行失败' in msg):
                time.sleep(delay)
                continue
            raise
    raise last


def app():
    import win32com.client as w

    def connect():
        a = w.Dispatch(PS_PROGID)
        a.DisplayDialogs = 3          # 3 = 不弹任何对话框, 防卡死
        return a

    return _retry(connect)


def run_jsx(path):
    a = app()

    def call():
        a.DoJavaScriptFile(str(Path(path).resolve()))
        return a

    return _retry(call)


def ps_escape(s):
    """JSX 字符串字面量转义。"""
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\r', '').replace('\n', '\\n')


CARD_TMPL = r'''#target photoshop
(function () {{
    var OUT = "{out}";
    var log = [];
    function L(s) {{ log.push(s); }}
    function flush() {{
        var f = new File(OUT + "/_ps_log.txt");
        f.encoding = "UTF8"; f.open("w"); f.write(log.join("\n")); f.close();
    }}
    function hex(h) {{ var c = new SolidColor(); c.rgb.hexValue = h; return c; }}

    var W = {W}, H = {H};
    var BG = "14161A", FG = "F2EEE7", ACC = "C8892F", DIM = "8A8577";

    app.displayDialogs = DialogModes.NO;
    // ⚠️ 绝不关闭他人文档：只操作本脚本自己新建的那一个。
    var preexisting = app.documents.length;
    L("preexisting docs=" + preexisting + " (will NOT be touched)");

    var doc = app.documents.add(new UnitValue(W, "px"), new UnitValue(H, "px"), 72,
                                "AI-Card", NewDocumentMode.RGB, DocumentFill.WHITE);
    function block(x1, y1, x2, y2, color, name, opacity) {{
        var l = doc.artLayers.add();
        l.name = name;
        doc.activeLayer = l;
        doc.selection.select([[x1, y1], [x2, y1], [x2, y2], [x1, y2]]);
        doc.selection.fill(hex(color));
        doc.selection.deselect();
        if (opacity !== undefined) {{ l.opacity = opacity; }}
        return l;
    }}
    function text(contents, font, size, color, x, y, tracking, opacity) {{
        var t = doc.artLayers.add();
        t.kind = LayerKind.TEXT;
        var ti = t.textItem;
        ti.kind = TextType.POINTTEXT;
        ti.contents = contents;
        try {{ ti.font = font; }} catch (e) {{ L("font fail " + font + ": " + e.message); }}
        ti.size = new UnitValue(size, "pt");
        ti.color = hex(color);
        ti.justification = Justification.LEFT;
        if (tracking !== undefined) {{ try {{ ti.tracking = tracking; }} catch (e) {{}} }}
        ti.position = [new UnitValue(x, "px"), new UnitValue(y, "px")];
        if (opacity !== undefined) {{ t.opacity = opacity; }}
        t.name = "T_" + Math.round(y);
        return t;
    }}

    // 底色
    block(0, 0, W, H, BG, "BG");
    // 顶部细线与竖条
    block(84, 96, 84 + 96, 100, ACC, "RuleTop");
    // 右侧装饰色块（低透明度做纵深）
    block(W - 300, 150, W - 84, H - 150, ACC, "PanelAccent", 12);

    text("{eyebrow}", "NotoSansSC-Medium", 20, DIM, 84, 150, 300);
    text("{title}", "NotoSansSC-Black", {tsize}, FG, 84, 330, 20);
    text("{subtitle}", "NotoSansSC-Light", 30, DIM, 84, 470, 40);
    block(84, 560, 84 + 300, 566, ACC, "RuleMid");

    {rows}

    text("{footer}", "NotoSansSC-Light", 20, DIM, 84, H - 110, 120, 60);

    var psd = new PhotoshopSaveOptions();
    psd.layers = true; psd.embedColorProfile = true;
    doc.saveAs(new File(OUT + "/{stem}.psd"), psd, false, Extension.LOWERCASE);
    var png = new PNGSaveOptions();
    png.compression = 6;
    doc.saveAs(new File(OUT + "/{stem}.png"), png, true, Extension.LOWERCASE);

    L("saved " + OUT + "/{stem}.png");
    L("layers=" + doc.layers.length + " size=" + W + "x" + H);

    // 只关自己新建的这一份，且已保存，不影响用户正开着的文档
    try {{ doc.close(SaveOptions.DONOTSAVECHANGES); L("closed own doc only"); }}
    catch (e) {{ L("close own doc FAIL: " + e.message); }}
    L("docs left open=" + app.documents.length + " (should equal preexisting)");
    flush();
}})();
'''


def cmd_info(a):
    p = app()
    print('Name    :', _retry(lambda: p.Name))
    print('Version :', _retry(lambda: p.Version))
    print('Path    :', _retry(lambda: p.Path))
    # ⚠️ COM 的 Documents.Count 在 PS 上不可靠, 以 JSX 侧为准
    print('Docs    :', _retry(lambda: p.DoJavaScript('app.documents.length')))
    print('JSX     :', _retry(lambda: p.DoJavaScript('app.version + " | " + app.fonts.length + " fonts"')))
    try:
        names = _retry(lambda: p.DoJavaScript(
            '(function(){var r=[];for(var i=0;i<app.documents.length;i++)r.push(app.documents[i].name);'
            'return r.join(" | ")||"(none)";})()'))
        print('Open    :', names)
    except Exception as e:
        print('Open    : (读取失败)', e)


def cmd_exec(a):
    run_jsx(a.jsx)
    print('ok:', a.jsx)


def cmd_card(a):
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    w, h = (int(v) for v in a.size.lower().split('x'))
    rows = getattr(a, 'rows', None)
    if rows:
        # 行用 ; 分隔，每行内 标签|值|备注
        rows = [r for r in rows.split(';') if r.strip()]
    else:
        rows = ['通道|COM + ExtendScript|无界面点击',
                '引擎|Photoshop 25.0.0|本地离线',
                '产物|PSD 分层 + PNG|可继续精修']
    parts = []
    y = 640
    for i, r in enumerate(rows, 1):
        k, v, note = ([c.strip() for c in r.split('|')] + ['', ''])[:3]
        parts.append(f'text("{ps_escape(v)}", "NotoSansSC-Medium", 40, FG, 84, {y}, 20);')
        parts.append(f'block(84, {y + 62}, {84 + 660}, {y + 64}, "3A3D42", "rule{i}");')
        if k:
            parts.append(f'text("{ps_escape(k)}", "NotoSansSC-Regular", 22, ACC, 84, {y - 34}, 200);')
        if note:
            parts.append(f'text("{ps_escape(note)}", "NotoSansSC-Light", 22, DIM, 760, {y + 6}, 40, 80);')
        y += 130

    jsx = CARD_TMPL.format(
        out=str(out).replace('\\', '/'),
        W=w, H=h,
        eyebrow=ps_escape(a.eyebrow),
        title=ps_escape(a.title),
        subtitle=ps_escape(a.subtitle),
        footer=ps_escape(a.footer),
        tsize=92 if len(a.title) <= 8 else 68,
        rows='\n    '.join(parts),
        stem=ps_escape(a.stem),
    )
    p = out / '_gen.jsx'
    p.write_text(jsx, encoding='utf-8')
    run_jsx(p)
    log = out / '_ps_log.txt'
    print(log.read_text(encoding='utf-8') if log.is_file() else '(no log)')
    for f in ('%s.png' % a.stem, '%s.psd' % a.stem):
        fp = out / f
        print(('OK   ' if fp.is_file() else 'MISS ') + str(fp), fp.stat().st_size if fp.is_file() else '')


def cmd_dump(a):
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    jsx = out / '_dump.jsx'
    jsx.write_text(r'''#target photoshop
(function () {
    var res = [];
    function walk(container, depth) {
        for (var i = 0; i < container.layers.length; i++) {
            var l = container.layers[i];
            var pad = "";
            for (var k = 0; k < depth; k++) pad += "  ";
            var kind = "?";
            try { kind = l.typename; } catch (e) {}
            var b = "";
            try { b = l.bounds[0].as("px") + "," + l.bounds[1].as("px") + " - " +
                      l.bounds[2].as("px") + "," + l.bounds[3].as("px"); } catch (e) {}
            res.push(pad + kind + " | " + l.name + " | vis=" + l.visible +
                     " op=" + l.opacity + " | " + b);
            if (kind === "LayerSet") walk(l, depth + 1);
        }
    }
    var f = new File("''' + str(out).replace('\\', '/') + r'''/layers.txt");
    f.encoding = "UTF8"; f.open("w");
    if (app.documents.length === 0) {
        f.write("(no document)");
    } else {
        var d = app.documents[0];
        f.write("doc " + d.name + " " + d.width.as("px") + "x" + d.height.as("px") + "\n");
        walk(d, 0);
        f.write("\n--- listed ---\n" + res.join("\n"));
    }
    f.close();
})();
''', encoding='utf-8')
    run_jsx(jsx)
    print((out / 'layers.txt').read_text(encoding='utf-8'))


def main():
    ap = argparse.ArgumentParser(description='Photoshop COM 驱动')
    sub = ap.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('info'); s.set_defaults(func=cmd_info)
    s = sub.add_parser('exec'); s.add_argument('jsx'); s.set_defaults(func=cmd_exec)
    s = sub.add_parser('dump'); s.add_argument('out'); s.set_defaults(func=cmd_dump)
    s = sub.add_parser('card')
    s.add_argument('title'); s.add_argument('subtitle')
    s.add_argument('--eyebrow', default='AI ACCESS  /  VERIFIED')
    s.add_argument('--footer', default='generated by AI - no manual click')
    s.add_argument('--out', default='_ps_out')
    s.add_argument('--size', default='1080x1350')
    s.add_argument('--stem', default='ai-card')
    s.add_argument('--rows', help='行用 ; 分隔，每行内 标签|值|备注')
    s.set_defaults(func=cmd_card)

    a = ap.parse_args()
    return a.func(a)


if __name__ == '__main__':
    sys.exit(main())
