#target photoshop
(function () {
    var log = [];
    function L(s) { log.push(s); }
    function flush() {
        var f = new File("/d/ai/Work buddy/2026-10-31-14-22-22/job-poster/probe_cutout.txt");
        f.encoding = "UTF8"; f.open("w"); f.write(log.join("\n")); f.close();
    }

    try {
        app.displayDialogs = DialogModes.NO;
    } catch (e) { L("displayDialogs set fail: " + e.message); }

    var doc = null;
    try {
        doc = app.open(new File("/d/ai/Work buddy/2026-10-31-14-22-22/job-poster/portrait.jpg"));
        L("OPENED name=" + doc.name + " w=" + doc.width + " h=" + doc.height + " mode=" + doc.mode);
    } catch (e) {
        L("OPEN FAIL: " + e.message); flush(); return;
    }

    function tryCmd(label, fn) {
        try {
            try { doc.selection.deselect(); } catch (e) {}
            fn();
            var b;
            try { b = doc.selection.bounds; } catch (e) { b = null; }
            if (b) {
                L(label + " => OK  bounds=[" + b[0] + "," + b[1] + "," + b[2] + "," + b[3] + "]");
                // 统计选区羽化后面积比
                return true;
            } else {
                L(label + " => NO_SELECTION");
                return false;
            }
        } catch (e) {
            L(label + " => THROW: " + e.message);
            return false;
        }
    }

    var ok = false;

    // 候选 A: autoCutout （PS "选择主体" 的底层命令）
    ok = tryCmd("A: stringID autoCutout", function () {
        executeAction(stringIDToTypeID("autoCutout"), undefined, DialogModes.NO);
    });

    // 候选 B: setSelectionToSubject
    if (!ok) {
        ok = tryCmd("B: charID setSelectionToSubject", function () {
            executeAction(charIDToTypeID("setSelectionToSubject"), undefined, DialogModes.NO);
        });
    }

    // 候选 C: 完整 ActionDescriptor 版 autoCutout（带 sampleAllLayers）
    if (!ok) {
        ok = tryCmd("C: autoCutout desc", function () {
            var d = new ActionDescriptor();
            d.putBoolean(stringIDToTypeID("sampleAllLayers"), false);
            executeAction(stringIDToTypeID("autoCutout"), d, DialogModes.NO);
        });
    }

    // 候选 D: Sbjc 布尔参数
    if (!ok) {
        ok = tryCmd("D: setd+Sbjc", function () {
            var idsetd = charIDToTypeID("setd");
            var d = new ActionDescriptor();
            var idnull = charIDToTypeID("null");
            var ref = new ActionReference();
            ref.putProperty(charIDToTypeID("Chnl"), charIDToTypeID("fsel"));
            d.putReference(idnull, ref);
            var idT = charIDToTypeID("T   ");
            var ref2 = new ActionReference();
            ref2.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Chnl"), charIDToTypeID("grey"));
            d.putReference(idT, ref2);
            d.putBoolean(charIDToTypeID("Sbjc"), true);
            executeAction(idsetd, d, DialogModes.NO);
        });
    }

    L("RESULT ok=" + ok);

    // 若成功，把选区存成蒙版并保存一个抠图结果
    if (ok) {
        try {
            var b = doc.selection.bounds;
            L("final bounds: " + b[0] + "," + b[1] + "," + b[2] + "," + b[3]);
        } catch (e) { L("bounds read fail"); }
    }

    flush();
})();
