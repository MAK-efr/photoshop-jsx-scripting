#target photoshop
(function () {
    var ROOT = "/d/ai/Work buddy/2026-10-31-14-22-22/job-poster";
    var log = [];
    function L(s) { log.push(s); }
    function hex(h) { var c = new SolidColor(); c.rgb.hexValue = h; return c; }

    app.displayDialogs = DialogModes.NO;
    try { while (app.documents.length > 0) app.documents[0].close(SaveOptions.DONOTSAVECHANGES); } catch (e) {}

    var doc = app.documents.add(new UnitValue(900, "px"), new UnitValue(900, "px"), 72,
        "verifyClaims", NewDocumentMode.RGB, DocumentFill.WHITE);

    // ---------- 1) Brightness/Contrast (BrgC) ----------
    try {
        var d = new ActionDescriptor();
        d.putEnumerated(stringIDToTypeID("presetKind"),
            stringIDToTypeID("presetKindType"), stringIDToTypeID("presetKindCustom"));
        var list = new ActionList();
        var cd = new ActionDescriptor();
        cd.putInteger(charIDToTypeID("Brgh"), 18);
        cd.putInteger(charIDToTypeID("Cntr"), 14);
        list.putObject(charIDToTypeID("BrgC"), cd);
        d.putList(charIDToTypeID("Adjs"), list);
        executeAction(charIDToTypeID("BrgC"), d, DialogModes.NO);
        L("CLAIM BrgC usable = TRUE (adjs Brgh=18 Cntr=14 applied)");
    } catch (e) {
        L("CLAIM BrgC usable = FALSE -> " + e.message);
    }

    // ---------- 2) 文字层换行：\r vs \n ----------
    function makeText(contents) {
        var t = doc.artLayers.add();
        t.kind = LayerKind.TEXT;
        var ti = t.textItem;
        ti.kind = TextType.POINTTEXT;
        ti.contents = contents;
        try { ti.font = "NotoSansSC-Regular"; } catch (e) {}
        ti.size = new UnitValue(48, "pt");
        ti.color = hex("000000");
        ti.justification = Justification.LEFT;
        ti.position = [new UnitValue(60, "px"), new UnitValue(400, "px")];
        return t;
    }

    function measure(label, contents) {
        var t = makeText(contents);
        var b = t.bounds;
        var w = b[2].as("px") - b[0].as("px");
        var h = b[3].as("px") - b[1].as("px");
        L("  " + label + " -> bounds " + w.toFixed(1) + " x " + h.toFixed(1) +
          "  (单行高约 48~70px，两行约 96~140px)");
        t.remove();
        return h;
    }

    L("");
    L("CLAIM \\r 换行 test:");
    var hCR = measure("contents='甲乙\\r丙丁'", "甲乙\r丙丁");
    L("CLAIM \\n 换行 test:");
    var hLF = measure("contents='甲乙\\n丙丁'", "甲乙\n丙丁");
    L("  VERDICT: \\r 高=" + hCR.toFixed(1) + "  \\n 高=" + hLF.toFixed(1) +
      "  -> " + (hCR > hLF * 1.5 ? "\\r 确实换行、\\n 不换行" : "两者表现相同，原结论存疑"));

    // ---------- 3) 竖排 Direction.VERTICAL ----------
    L("");
    try {
        var t2 = makeText("甲乙丙丁");
        var dirOk = false;
        try {
            t2.textItem.direction = Direction.VERTICAL;
            dirOk = true;
        } catch (e2) {
            L("CLAIM Direction.VERTICAL 赋值 = FAIL -> " + e2.message);
        }
        if (dirOk) {
            var b2 = t2.bounds;
            var w2 = b2[2].as("px") - b2[0].as("px");
            var h2 = b2[3].as("px") - b2[1].as("px");
            L("CLAIM Direction.VERTICAL = ASSIGNABLE, bounds " + w2.toFixed(1) + " x " + h2.toFixed(1) +
              "  (竖排应 宽窄高长)");
        }
        t2.remove();
    } catch (e3) {
        L("CLAIM Direction.VERTICAL = FAIL -> " + e3.message);
    }

    // ---------- 4) resize 后的 bounds 偏移 ----------
    L("");
    try {
        var src = app.documents.add(new UnitValue(1279, "px"), new UnitValue(1704, "px"), 72,
            "verifyResize", NewDocumentMode.RGB, DocumentFill.WHITE);
        src.selection.select([[46, 129], [1237, 129], [1237, 1593], [46, 1593]]);
        src.selection.fill(hex("3366CC"));
        src.selection.deselect();
        var before = src.activeLayer.bounds;
        L("CLAIM resize offset: 填充后 bounds = " +
          before[0].as("px") + "," + before[1].as("px") + " - " +
          before[2].as("px") + "," + before[3].as("px"));
        src.activeLayer.resize(64, 64, AnchorPosition.TOPLEFT);
        var after = src.activeLayer.bounds;
        L("   resize(64,64,TOPLEFT) 后 bounds = " +
          after[0].as("px") + "," + after[1].as("px") + " - " +
          after[2].as("px") + "," + after[3].as("px"));
        L("   理论值(原坐标x0.64) = " + (46 * 0.64).toFixed(1) + "," + (129 * 0.64).toFixed(1));
        src.close(SaveOptions.DONOTSAVECHANGES);
    } catch (e4) {
        L("CLAIM resize offset FAIL -> " + e4.message);
    }

    // JSX 侧文档数（给 Python 侧对比 COM Count）
    L("");
    L("JSX app.documents.length = " + app.documents.length);

    try { doc.close(SaveOptions.DONOTSAVECHANGES); } catch (e) {}

    var f = new File(ROOT + "/verify_claims.txt");
    f.encoding = "UTF8"; f.open("w"); f.write(log.join("\n")); f.close();
})();
