#target photoshop
(function () {
    var ROOT = "/d/ai/Work buddy/2026-10-31-14-22-22/job-poster";
    var out = [];
    var doc = null;

    // 不依赖 activeDocument：优先找已打开的目标文档，找不到再从磁盘开
    for (var i = 0; i < app.documents.length; i++) {
        if (app.documents[i].name.indexOf("求职海报") === 0) { doc = app.documents[i]; break; }
    }
    if (!doc) {
        try {
            doc = app.open(new File(ROOT + "/求职海报.psd"));
        } catch (e) {
            var f0 = new File(ROOT + "/layers.txt");
            f0.encoding = "UTF8"; f0.open("w");
            f0.write("OPEN FAIL: " + e.message + "\n已打开文档数: " + app.documents.length);
            f0.close();
            return;
        }
    }

    out.push("DOC: " + doc.name + "  " + doc.width + " x " + doc.height + "  mode=" + doc.mode);
    out.push("LAYERS (" + doc.layers.length + "):");
    for (var k = 0; k < doc.layers.length; k++) {
        var l = doc.layers[k];
        var kind = "pixels";
        var txt = "";
        try {
            if (l.kind == LayerKind.TEXT) {
                kind = "TEXT";
                txt = "  \"" + l.textItem.contents + "\"";
            }
        } catch (e) {}
        out.push("  [" + k + "] " + l.name + "  kind=" + kind + "  visible=" + l.visible + txt);
    }

    var f = new File(ROOT + "/layers.txt");
    f.encoding = "UTF8"; f.open("w"); f.write(out.join("\n")); f.close();
})();
