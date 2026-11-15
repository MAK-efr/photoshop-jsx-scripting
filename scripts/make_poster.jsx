#target photoshop
(function () {
    var ROOT = "/d/ai/Work buddy/2026-10-31-14-22-22/job-poster";
    var log = [];
    function L(s) { log.push(s); }
    function flush() {
        var d = new Date();
        function p(n) { return (n < 10 ? "0" : "") + n; }
        var ts = d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + "-" +
                 p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds());
        var lg = new Folder(ROOT + "/logs");
        if (!lg.exists) lg.create();
        var body = "=== run " + ts + " ===\n" + log.join("\n");
        // 历史留档：每次运行一份，不覆盖
        var fh = new File(ROOT + "/logs/poster_" + ts + ".txt");
        fh.encoding = "UTF8"; fh.open("w"); fh.write(body); fh.close();
        // 最新一份，方便快速查看
        var f = new File(ROOT + "/poster_log.txt");
        f.encoding = "UTF8"; f.open("w"); f.write(body); f.close();
    }
    function hex(h) { var c = new SolidColor(); c.rgb.hexValue = h; return c; }
    function pt(x, y) {
        var p = new ActionDescriptor();
        p.putDouble(charIDToTypeID("Hrzn"), x);
        p.putDouble(charIDToTypeID("Vrtc"), y);
        return p;
    }

    var W = 1080, H = 1440;
    var DARK = "191B18";
    var LIGHT = "EFE9DE";
    var ACC  = "C8892F";

    app.displayDialogs = DialogModes.NO;
    try { while (app.documents.length > 0) app.documents[0].close(SaveOptions.DONOTSAVECHANGES); } catch (e) {}

    var doc = app.documents.add(
        new UnitValue(W, "px"), new UnitValue(H, "px"), 72, "JobPoster",
        NewDocumentMode.RGB, DocumentFill.WHITE
    );

    doc.selection.select([[0, 0], [W, 0], [W, 992], [0, 992]]);
    doc.selection.fill(hex(DARK));
    doc.selection.deselect();

    // ---------- 人物 ----------
    var src = app.open(new File(ROOT + "/cutout.png"));
    var dup = src.activeLayer.duplicate(doc, ElementPlacement.PLACEATBEGINNING);
    src.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = doc;
    doc.activeLayer = dup;

    var S = 64;
    dup.resize(S, S, AnchorPosition.TOPLEFT);
    var b = dup.bounds;
    var bl = b[0].as("px"), bt = b[1].as("px"), br = b[2].as("px");
    var RATIO = 0.47775;
    var headCx = bl + (br - bl) * RATIO;
    var tgtHeadTop = 130, tgtHeadCx = 664;
    dup.translate(tgtHeadCx - headCx, tgtHeadTop - bt);
    var b2 = dup.bounds;
    L("portrait bounds: " + b2[0].as("px") + "," + b2[1].as("px") + " - " + b2[2].as("px") + "," + b2[3].as("px"));
    dup.name = "Portrait";

    // ---------- 调色：分通道曲线加暖 + 复合提亮 ----------
    try {
        var d = new ActionDescriptor();
        d.putEnumerated(stringIDToTypeID("presetKind"), stringIDToTypeID("presetKindType"), stringIDToTypeID("presetKindCustom"));
        var list = new ActionList();

        var chans = [
            [charIDToTypeID("Rd  "), 7, []],
            [charIDToTypeID("Grn "), 1, []],
            [charIDToTypeID("Bl  "), -11, [[232, 218]]]
        ];
        for (var i = 0; i < chans.length; i++) {
            var r = new ActionDescriptor();
            var rr = new ActionReference();
            rr.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Chnl"), chans[i][0]);
            r.putReference(charIDToTypeID("Chnl"), rr);
            var ps = new ActionList();
            ps.putObject(charIDToTypeID("Pnt "), pt(0, 0));
            ps.putObject(charIDToTypeID("Pnt "), pt(128, 128 + chans[i][1]));
            var extra = chans[i][2];
            for (var k = 0; k < extra.length; k++) {
                ps.putObject(charIDToTypeID("Pnt "), pt(extra[k][0], extra[k][1]));
            }
            ps.putObject(charIDToTypeID("Pnt "), pt(255, 255));
            r.putList(charIDToTypeID("Crv "), ps);
            list.putObject(charIDToTypeID("CrvA"), r);
        }
        d.putList(charIDToTypeID("Adjs"), list);
        executeAction(charIDToTypeID("Crvs"), d, DialogModes.NO);
        L("channel curves OK");
    } catch (e) { L("channel curves FAIL: " + e.message); }

    // 复合曲线：轻微提亮 + 微对比
    try {
        var d2 = new ActionDescriptor();
        d2.putEnumerated(stringIDToTypeID("presetKind"), stringIDToTypeID("presetKindType"), stringIDToTypeID("presetKindCustom"));
        var l2 = new ActionList();
        var r2 = new ActionDescriptor();
        var rr2 = new ActionReference();
        rr2.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Chnl"), charIDToTypeID("Cmps"));
        r2.putReference(charIDToTypeID("Chnl"), rr2);
        var ps2 = new ActionList();
        ps2.putObject(charIDToTypeID("Pnt "), pt(0, 0));
        ps2.putObject(charIDToTypeID("Pnt "), pt(64, 74));
        ps2.putObject(charIDToTypeID("Pnt "), pt(160, 168));
        ps2.putObject(charIDToTypeID("Pnt "), pt(255, 255));
        r2.putList(charIDToTypeID("Crv "), ps2);
        l2.putObject(charIDToTypeID("CrvA"), r2);
        d2.putList(charIDToTypeID("Adjs"), l2);
        executeAction(charIDToTypeID("Crvs"), d2, DialogModes.NO);
        L("composite curve OK");
    } catch (e) { L("composite curve FAIL: " + e.message); }

    // ---------- 米白面板 ----------
    var panel = doc.artLayers.add();
    panel.name = "LowerPanel";
    doc.activeLayer = panel;
    doc.selection.select([[0, 992], [W, 992], [W, H], [0, H]]);
    doc.selection.fill(hex(LIGHT));
    doc.selection.deselect();

    var line = doc.artLayers.add();
    line.name = "Divider";
    doc.activeLayer = line;
    doc.selection.select([[0, 989], [W, 989], [W, 995], [0, 995]]);
    doc.selection.fill(hex(ACC));
    doc.selection.deselect();

    // ---------- 文字 ----------
    function addText(contents, font, size, color, x, y, tracking, opacity) {
        var t = doc.artLayers.add();
        t.kind = LayerKind.TEXT;
        var ti = t.textItem;
        ti.kind = TextType.POINTTEXT;
        ti.contents = contents;
        try { ti.font = font; } catch (e) { L("font fail " + font + ": " + e.message); }
        ti.size = new UnitValue(size, "pt");
        ti.color = hex(color);
        ti.justification = Justification.LEFT;
        if (tracking !== undefined) { try { ti.tracking = tracking; } catch (e) {} }
        ti.position = [new UnitValue(x, "px"), new UnitValue(y, "px")];
        if (opacity !== undefined) { t.opacity = opacity; }
        t.name = "T" + Math.round(x) + "_" + Math.round(y);
        return t;
    }

    addText("RESUME  /  2026", "NotoSansSC-Medium", 21, "EFE9DE", 84, 96, 260, 60);

    // 琥珀竖条
    var bar = doc.artLayers.add();
    bar.name = "AccentBar";
    doc.activeLayer = bar;
    doc.selection.select([[84, 616], [90, 616], [90, 700], [84, 700]]);
    doc.selection.fill(hex(ACC));
    doc.selection.deselect();

    addText("FPGA", "NotoSansSC-Light", 38, "EFE9DE", 112, 662, 60, 40);
    addText("VERILOG", "NotoSansSC-Light", 38, "EFE9DE", 112, 716, 60, 40);
    addText("EMBEDDED", "NotoSansSC-Light", 38, "EFE9DE", 112, 770, 60, 40);
    addText("PCB", "NotoSansSC-Light", 38, "EFE9DE", 112, 824, 60, 40);

    addText("你的姓名", "NotoSansSC-Black", 96, "16211D", 84, 1150, 40);
    addText("目标岗位  ·  待填写", "NotoSansSC-Medium", 30, "C8892F", 88, 1208, 60);

    var rule = doc.artLayers.add();
    rule.name = "Rule";
    doc.activeLayer = rule;
    doc.selection.select([[88, 1250], [470, 1250], [470, 1252], [88, 1252]]);
    doc.selection.fill(hex("16211D"));
    doc.selection.deselect();
    rule.opacity = 28;

    addText("PHONE    138 0000 0000", "NotoSansSC-Regular", 22, "16211D", 88, 1302, 90, 76);
    addText("MAIL     your@email.com", "NotoSansSC-Regular", 22, "16211D", 88, 1347, 90, 76);
    addText("电子 / 嵌入式 / FPGA", "NotoSansSC-Light", 19, "16211D", 88, 1396, 120, 42);

    var psdOpts = new PhotoshopSaveOptions();
    psdOpts.layers = true;
    psdOpts.embedColorProfile = true;
    doc.saveAs(new File(ROOT + "/求职海报.psd"), psdOpts, false, Extension.LOWERCASE);

    var pngOpts = new PNGSaveOptions();
    pngOpts.compression = 6;
    doc.saveAs(new File(ROOT + "/求职海报.png"), pngOpts, true, Extension.LOWERCASE);
    L("done layers=" + doc.layers.length);
    flush();
})();
