# -*- coding: utf-8 -*-
"""ps_batch.py —— 一份模板清单 × 一份数据表 → N 张图

模板里**任何字符串**都可以写 {{字段}}，按数据表逐行替换；out.stem 同样支持，
所以每张成品能用数据里的名字命名（例如 "{{name}}_poster"）。

为什么要单独一层：ps_build 只认"已算好内容的清单"。
批量不是把清单复制 N 份手改，而是**清单只写一次、内容来自数据表**。

用法
  python ps_batch.py template.json --rows rows.csv
  python ps_batch.py template.json --rows rows.json --limit 2
  python ps_batch.py template.json --rows rows.csv --check      # 只校验所有行，不跑 PS
  python ps_batch.py template.json --rows rows.csv --dry-run    # 只生成每行的 jsx

数据表格式
  CSV  : 首行是表头，逗号分隔，UTF-8（带 BOM 也认）
  JSON : [{"name":"张三", ...}, ...]  或  {"rows":[...]}

注意
  - 每行都会新建并关闭一个文档，跑完核对 app.documents.length 回零（ps_build 内部已做）。
  - 某行失败不会中断整体，最后统一汇总；有任一行 FAIL 则退出码为 1。
"""
import argparse
import copy
import csv
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ps_build  # noqa: E402

TOKEN = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


def load_rows(path):
    p = Path(path)
    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            data = data.get("rows") or data.get("data")
        if not isinstance(data, list):
            raise ValueError("JSON 数据表必须是数组，或含 rows/data 数组的对象")
        return [dict(r) for r in data]
    txt = p.read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(txt)))
    return [dict(r) for r in rows]


def sub(obj, row, miss):
    """递归替换所有字符串里的 {{字段}}；未匹配的记到 miss 里。"""
    if isinstance(obj, str):
        def rep(m):
            k = m.group(1)
            if k in row and row[k] is not None:
                return str(row[k])
            miss.add(k)
            return m.group(0)
        return TOKEN.sub(rep, obj)
    if isinstance(obj, list):
        return [sub(x, row, miss) for x in obj]
    if isinstance(obj, dict):
        # 以 _ 开头的键（_note 等）是注释，不参与替换
        return {k: (v if str(k).startswith("_") else sub(v, row, miss))
                for k, v in obj.items()}
    return obj


def main():
    ap = argparse.ArgumentParser(description="模板清单 × 数据表 批量出图")
    ap.add_argument("template")
    ap.add_argument("--rows", required=True, help="CSV 或 JSON 数据表")
    ap.add_argument("--out", help="覆盖模板里的 out.dir")
    ap.add_argument("--stem", help="覆盖模板里的 out.stem（可用 {{字段}}）")
    ap.add_argument("--limit", type=int, help="只跑前 N 行")
    ap.add_argument("--check", action="store_true", help="只校验，不执行")
    ap.add_argument("--dry-run", action="store_true", help="只生成 jsx，不执行")
    a = ap.parse_args()

    tpl, tpath = ps_build.load_manifest(a.template)
    rows = load_rows(a.rows)
    if a.limit:
        rows = rows[:a.limit]
    if not rows:
        print("数据表没有数据行")
        return 2

    print("模板 %s  数据 %d 行  列：%s"
          % (tpath.name, len(rows), ", ".join(list(rows[0].keys()))))

    results = []
    for i, row in enumerate(rows, 1):
        miss = set()
        m = sub(copy.deepcopy(tpl), row, miss)
        if a.stem:
            m.setdefault("out", {})["stem"] = a.stem
        if miss:
            print("\n[%d/%d] 跳过：模板里有数据表没有的字段 %s"
                  % (i, len(rows), ", ".join(sorted(miss))))
            results.append((i, None, "缺字段 " + ",".join(sorted(miss)), 0, 0))
            continue

        stem = m["out"]["stem"]
        try:
            out_dir, jf, txt = ps_build.run_manifest(
                m, tpath.parent, a.out, None, a.dry_run)
        except ValueError as e:
            print("\n[%d/%d] 清单不合法：%s" % (i, len(rows), e))
            results.append((i, stem, "清单不合法", 0, 0))
            continue

        ok = p = 0
        mm = re.search(r"SUMMARY pass=(\d+) fail=(\d+)", txt or "")
        if mm:
            p, ok = int(mm.group(1)), int(mm.group(2))
        status = "dry-run" if a.dry_run else (
            "PASS" if (mm and ok == 0) else ("FAIL" if mm else "无日志"))
        sizes = 0
        if not a.dry_run:
            for f in (m["out"].get("formats") or ["png", "psd"]):
                fp = out_dir / ("%s.%s" % (stem, f))
                if fp.is_file():
                    sizes += fp.stat().st_size
        results.append((i, stem, status, p, sizes))
        print("[%d/%d] %-24s %-8s pass=%-3d %s"
              % (i, len(rows), stem, status, p,
                 ("%.1f KB" % (sizes / 1024.0)) if sizes else ""))

    bad = [r for r in results if r[2] not in ("PASS", "dry-run")]
    print("\n批量结束：成功 %d / %d，失败 %d"
          % (len(results) - len(bad), len(results), len(bad)))
    for r in bad:
        print("  - 第 %d 行 %s : %s" % (r[0], r[1], r[2]))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
