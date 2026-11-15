#target photoshop
(function () {
    var log = [];
    function L(s) { log.push(s); }
    var ROOT = "/d/ai/Work buddy/2026-10-31-14-22-22/job-poster";
    function flush() {
        var d = new Date();
        function p(n) { return (n < 10 ? "0" : "") + n; }
        var ts = d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + "-" +
                 p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds());
        var lg = new Folder(ROOT + "/logs");
        if (!lg.exists) lg.create();
        var body = "=== run " + ts + " ===\n" + log.join("\n");
        var fh = new File(ROOT + "/logs/cutout_" + ts + ".txt");
        fh.encoding = "UTF8"; fh.open("w"); fh.write(body); fh.close();
        var f = new File(ROOT + "/cutout_log.txt");
        f.encoding = "UTF8"; f.open("w"); f.write(body); f.close();
    }

    app.displayDialogs = DialogModes.NO;

    try {
        while (app.documents.length > 0) { app.documents[0].close(SaveOptions.DONOTSAVECHANGES); }
    } catch (e) { L("cleanup: " + e.message); }

    var doc = app.open(new File(ROOT + "/portrait.jpg"));
    L("opened " + doc.width + "x" + doc.height);

    executeAction(stringIDToTypeID("autoCutout"), undefined, DialogModes.NO);
    var b = doc.selection.bounds;
    L("raw selection: " + b[0] + " " + b[1] + " " + b[2] + " " + b[3]);

    // 关键：向内收缩，剔除人物与亮背景的混合像素（青边来源）
    try {
        doc.selection.contract(2);
        L("contract 2px ok");
    } catch (e) { L("contract fail: " + e.message); }

    // 轻羽化保持边缘平滑（比之前 0.8 更轻）
    try {
        doc.selection.feather(0.5);
        L("feather 0.5 ok");
    } catch (e) { L("feather fail: " + e.message); }

    var b2 = doc.selection.bounds;
    L("after contract: " + b2[0] + " " + b2[1] + " " + b2[2] + " " + b2[3]);

    // 复制到透明文档
    doc.selection.copy();
    var out = app.documents.add(
        doc.width, doc.height, doc.resolution,
        "Cutout", NewDocumentMode.RGB, DocumentFill.TRANSPARENT
    );
    out.paste();
    L("pasted, layers=" + out.layers.length);

    // 在抠图本身上做一次「去边」，进一步压掉残留色边
    try {
        var d = new ActionDescriptor();
        d.putUnitDouble(charIDToTypeID("Wth "), charIDToTypeID("#Pxl"), 1);
        executeAction(stringIDToTypeID("defringe"), d, DialogModes.NO);
        L("defringe ok");
    } catch (e) { L("defringe FAIL: " + e.message); }

    var pngOpts = new PNGSaveOptions();
    pngOpts.compression = 6;
    out.saveAs(new File(ROOT + "/cutout.png"), pngOpts, true, Extension.LOWERCASE);
    L("saved cutout.png");

    flush();
})();
