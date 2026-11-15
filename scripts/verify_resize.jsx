#target photoshop
(function () {
    var ROOT = "/d/ai/Work buddy/2026-10-31-14-22-22/job-poster";
    var log = [];
    function L(s) { log.push(s); }
    function hex(h) { var c = new SolidColor(); c.rgb.hexValue = h; return c; }

    app.displayDialogs = DialogModes.NO;
    try { while (app.documents.length > 0) app.documents[0].close(SaveOptions.DONOTSAVECHANGES); } catch (e) {}

    // ---------- resize 后 bounds 偏移：用普通图层，不用锁定的背景层 ----------
    var src = null;
    try {
        src = app.documents.add(new UnitValue(1279, "px"), new UnitValue(1704, "px"), 72,
            "verifyResize", NewDocumentMode.RGB, DocumentFill.WHITE);

        // 关键：新建普通图层再填充，背景层是锁定的，resize 会报「变换不可用」
        var lay = src.artLayers.add();
        src.activeLayer = lay;
        src.selection.select([[46, 129], [1237, 129], [1237, 1593], [46, 1593]]);
        src.selection.fill(hex("3366CC"));
        src.selection.deselect();

        var before = lay.bounds;
        L("填充后 bounds = " + before[0].as("px") + "," + before[1].as("px") +
          " - " + before[2].as("px") + "," + before[3].as("px"));

        lay.resize(64, 64, AnchorPosition.TOPLEFT);
        var after = lay.bounds;
        L("resize(64,64,TOPLEFT) 后 bounds = " +
          after[0].as("px") + "," + after[1].as("px") +
          " - " + after[2].as("px") + "," + after[3].as("px"));
        L("理论值(原坐标 x0.64) = " + (46 * 0.64).toFixed(1) + "," + (129 * 0.64).toFixed(1));
        L("结论: 实测左=" + after[0].as("px") + " 上=" + after[1].as("px") +
          "，理论 " + (46 * 0.64).toFixed(1) + "/" + (129 * 0.64).toFixed(1) +
          " -> " + (Math.abs(after[0].as("px") - 46 * 0.64) > 1 ? "存在偏移，必须用实测 bounds 反推" : "无偏移"));
    } catch (e) {
        L("resize 测试 FAIL -> " + e.message);
    }

    // ---------- 强制清理：无论前面是否抛异常 ----------
    try {
        for (var i = app.documents.length - 1; i >= 0; i--) {
            var nm = app.documents[i].name;
            if (nm.indexOf("verify") === 0) {
                app.documents[i].close(SaveOptions.DONOTSAVECHANGES);
            }
        }
    } catch (e2) { L("cleanup warn: " + e2.message); }

    L("");
    L("JSX app.documents.length (清理后) = " + app.documents.length);

    var f = new File(ROOT + "/verify_resize.txt");
    f.encoding = "UTF8"; f.open("w"); f.write(log.join("\n")); f.close();
})();
