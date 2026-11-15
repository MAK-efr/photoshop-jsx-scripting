# -*- coding: utf-8 -*-
"""一条命令自检：把 PS 上所有已宣称的能力真跑一遍，再逐条量像素。

    python scripts/selftest.py            # 全部跑
    python scripts/selftest.py --quick    # 只跑清单，不跑批量/回填

不读文档里的旧数字，所有结论都从本次产出的文件现算。
退出码：0 全通过 / 1 有检查项失败 / 3 环境问题（没有 pywin32 或连不上 PS）
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import traceback
from pathlib import Path

SK = Path(__file__).resolve().parents[1]
EX = SK / "examples"
OUT = EX / "_out"
PY = sys.executable

try:
    import numpy as np
    from PIL import Image
except ImportError:
    print("缺依赖：pip install pillow numpy")
    sys.exit(3)
try:
    import win32com.client  # noqa: F401
except ImportError:
    print("缺依赖：pip install pywin32（且必须用装了它的那个 Python 跑）")
    sys.exit(3)

sys.path.insert(0, str(SK / "scripts"))
import ps_build  # noqa: E402

results = []


def rec(name, ok, note):
    results.append((name, ok, note))
    print(("  PASS  " if ok else "  FAIL  ") + name.ljust(24) + note)


def parse(txt):
    p = re.search(r"pass=(\d+)", txt or "")
    f = re.search(r"fail=(\d+)", txt or "") or re.search(r"失败\s*(\d+)", txt or "")
    return (int(p.group(1)) if p else -1, int(f.group(1)) if f else -1)


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def arr(p):
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.float64)


def mad(a, b, region=None):
    A, B = arr(a), arr(b)
    if region:
        A, B = A[region], B[region]
    return float(np.abs(A - B).mean())


# ---------- 1. 清单 ----------
def check_manifests():
    print("\n[1] 清单式出图")
    total_ok = total_bad = 0
    for mf in sorted(EX.glob("manifest_*.json")):
        name = mf.stem
        try:
            m, mp = ps_build.load_manifest(mf)
            od, jf, txt = ps_build.run_manifest(m, mp.parent)
            ok, bad = parse(txt)
            total_ok += max(ok, 0)
            total_bad += max(bad, 0)
            rec(name, ok > 0 and bad == 0, "pass=%d fail=%d" % (ok, bad))
        except Exception:
            rec(name, False, "异常：" + traceback.format_exc(limit=1).replace("\n", " "))
    return total_ok, total_bad


# ---------- 2. 批量 ----------
def check_batch():
    print("\n[2] 数据表批量出图")
    r = subprocess.run([PY, str(SK / "scripts" / "ps_batch.py"),
                        str(EX / "batch_template.json"), "--rows", str(EX / "batch_rows.csv")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=1800)
    txt = (r.stdout or "") + (r.stderr or "")
    ok, bad = parse(txt)
    rec("ps_batch", r.returncode == 0 and bad == 0, "exit=%d 失败=%d" % (r.returncode, bad))


# ---------- 3. 回填 ----------
def check_fill():
    print("\n[3] PSD 模板按图层名回填")
    tpl = EX / "assets" / "tpl_cert.psd"
    before = md5(tpl)

    # 先把模板原样渲一张 PNG 当基准（否则"图区变了"没法量化）
    base_png = OUT / "_selftest_tpl.png"
    base_png.parent.mkdir(parents=True, exist_ok=True)
    jsx = OUT / "_selftest_render.jsx"
    jsx.write_text(
        '#target photoshop\n'
        'app.displayDialogs = DialogModes.NO;\n'
        'var d = app.open(new File("%s"));\n'
        'var o = new PNGSaveOptions(); o.compression = 9;\n'
        'd.saveAs(new File("%s"), o, true, Extension.LOWERCASE);\n'
        'd.close(SaveOptions.DONOTSAVECHANGES);\n' % (tpl.as_posix(), base_png.as_posix()),
        encoding="utf-8")

    import ps  # noqa: E402
    ps.run_jsx(jsx)

    r = subprocess.run([PY, str(SK / "scripts" / "ps_fill.py"), str(EX / "fill_cert.json")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=1800)
    txt = (r.stdout or "") + (r.stderr or "")
    ok, bad = parse(txt)
    rec("ps_fill", r.returncode == 0 and bad == 0, "exit=%d pass=%d fail=%d" % (r.returncode, ok, bad))
    rec("模板文件零改动", md5(tpl) == before, "MD5 " + before[:8] + " 跑前跑后一致")

    try:
        made = OUT / "fill" / "cert_2026.png"
        reg = (slice(180, 470), slice(470, 850))
        m = mad(made, base_png, reg)
        rec("回填图区已换图", m > 20, "图区 MAD %.2f（模板原样 vs 回填后）" % m)
    except Exception:
        rec("回填图区已换图", False, repr(traceback.format_exc(limit=1)))


# ---------- 4. 像素 ----------
def check_pixels():
    print("\n[4] 像素级验证")

    try:
        th, tb = OUT / "threshold.png", OUT / "threshold_base.png"
        ys = [25, 75, 125, 175]
        got_t = [int(arr(th)[y, 150, 0]) for y in ys]
        got_b = [int(arr(tb)[y, 150, 0]) for y in ys]
        rec("阈值灰带翻面", got_t == [0, 255, 255, 255],
            "基准 %s → 阈值64 %s" % (got_b, got_t))
        rec("阈值偏离基准", mad(th, tb) > 50, "MAD %.2f" % mad(th, tb))
    except Exception:
        rec("阈值像素", False, repr(traceback.format_exc(limit=1)))

    try:
        m = mad(OUT / "effects.png", OUT / "effects_base.png")
        rec("图层样式生效", m > 5, "effects vs base MAD %.2f" % m)
    except Exception:
        rec("图层样式像素", False, repr(traceback.format_exc(limit=1)))

    try:
        v = json.loads((EX / "manifest_variants.json").read_text(encoding="utf-8"))
        w0, h0 = v["doc"]["w"], v["doc"]["h"]
        for it in v["out"]["variants"]:
            sfx = it.get("suffix")
            if "scale" in it:
                want = (round(w0 * it["scale"]), round(h0 * it["scale"]))
            else:
                want = (it["w"], it["h"])
            got = Image.open(OUT / ("variants_%s.png" % sfx)).size
            rec("变体 " + str(sfx), got == want, "期望 %dx%d 实际 %dx%d" % (want + got))
    except Exception:
        rec("变体尺寸", False, repr(traceback.format_exc(limit=1)))

    try:
        pngs = sorted((OUT / "batch").glob("*.png"))
        if len(pngs) >= 3:
            rec("批量成品互异", mad(pngs[0], pngs[1]) > 0.5 and mad(pngs[0], pngs[2]) > 0.5,
                "%d 张，MAD %.2f / %.2f" % (len(pngs), mad(pngs[0], pngs[1]), mad(pngs[0], pngs[2])))
        else:
            rec("批量成品互异", False, "只找到 %d 张 png" % len(pngs))
    except Exception:
        rec("批量像素", False, repr(traceback.format_exc(limit=1)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="只跑清单，跳过批量/回填")
    a = ap.parse_args()

    import ps  # noqa: E402
    try:
        info = str(ps.app().Version)
    except Exception:
        print("连不上 Photoshop：先完全退出所有 PS 进程，再重跑本脚本")
        return 3
    print("Photoshop " + info)

    ok, bad = check_manifests()
    if not a.quick:
        check_batch()
        check_fill()
        check_pixels()

    names = [n for n, good, _ in results if not good]
    print("\n" + "=" * 64)
    print("清单步骤 pass=%d fail=%d ；检查项 %d 通过 %d 失败 %d"
          % (ok, bad, len(results), len(results) - len(names), len(names)))
    if names:
        print("失败：" + "、".join(names))
    print("=" * 64)
    return 1 if names else 0


if __name__ == "__main__":
    sys.exit(main())
