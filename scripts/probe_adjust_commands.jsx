#target photoshop
(function () {
    var ROOT = "/d/ai/Work buddy/2026-10-31-14-22-22/job-poster";
    var log = [];
    function L(s) { log.push(s); }

    app.displayDialogs = DialogModes.NO;

    function fresh() {
        try { while (app.documents.length > 0) app.documents[0].close(SaveOptions.DONOTSAVECHANGES); } catch (e) {}
        return app.open(new File(ROOT + "/portrait.jpg"));
    }

    function pt(x, y) {
        var p = new ActionDescriptor();
        p.putDouble(charIDToTypeID("Hrzn"), x);
        p.putDouble(charIDToTypeID("Vrtc"), y);
        return p;
    }

    // ---- 测试 1: 复合曲线 ----
    try {
        var doc = fresh();
        var d = new ActionDescriptor();
        d.putEnumerated(stringIDToTypeID("presetKind"), stringIDToTypeID("presetKindType"), stringIDToTypeID("presetKindCustom"));
        var list = new ActionList();
        var rec = new ActionDescriptor();
        var ref = new ActionReference();
        ref.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Chnl"), charIDToTypeID("Cmps"));
        rec.putReference(charIDToTypeID("Chnl"), ref);
        var pts = new ActionList();
        pts.putObject(charIDToTypeID("Pnt "), pt(0, 0));
        pts.putObject(charIDToTypeID("Pnt "), pt(128, 134));
        pts.putObject(charIDToTypeID("Pnt "), pt(255, 255));
        rec.putList(charIDToTypeID("Crv "), pts);
        list.putObject(charIDToTypeID("CrvA"), rec);
        d.putList(charIDToTypeID("Adjs"), list);
        executeAction(charIDToTypeID("Crvs"), d, DialogModes.NO);
        L("TEST1 composite curves: OK");
    } catch (e) { L("TEST1 composite curves: FAIL " + e.message); }

    // ---- 测试 2: 分通道曲线（加暖）----
    try {
        var doc2 = fresh();
        var d2 = new ActionDescriptor();
        d2.putEnumerated(stringIDToTypeID("presetKind"), stringIDToTypeID("presetKindType"), stringIDToTypeID("presetKindCustom"));
        var l2 = new ActionList();

        var chans = [
            [charIDToTypeID("Rd  "), 6],
            [charIDToTypeID("Grn "), 0],
            [charIDToTypeID("Bl  "), -9]
        ];
        for (var i = 0; i < chans.length; i++) {
            var r = new ActionDescriptor();
            var rr = new ActionReference();
            rr.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Chnl"), chans[i][0]);
            r.putReference(charIDToTypeID("Chnl"), rr);
            var ps = new ActionList();
            ps.putObject(charIDToTypeID("Pnt "), pt(0, 0));
            ps.putObject(charIDToTypeID("Pnt "), pt(128, 128 + chans[i][1]));
            ps.putObject(charIDToTypeID("Pnt "), pt(255, 255));
            r.putList(charIDToTypeID("Crv "), ps);
            l2.putObject(charIDToTypeID("CrvA"), r);
        }
        d2.putList(charIDToTypeID("Adjs"), l2);
        executeAction(charIDToTypeID("Crvs"), d2, DialogModes.NO);
        L("TEST2 per-channel curves: OK");
    } catch (e) { L("TEST2 per-channel curves: FAIL " + e.message); }

    // ---- 测试 3: 色彩平衡（去掉 PrsL）----
    try {
        var doc3 = fresh();
        var d3 = new ActionDescriptor();
        d3.putEnumerated(stringIDToTypeID("presetKind"), stringIDToTypeID("presetKindType"), stringIDToTypeID("presetKindCustom"));
        var l3 = new ActionList();
        var c3 = new ActionDescriptor();
        c3.putInteger(charIDToTypeID("ShdL"), 0);
        c3.putInteger(charIDToTypeID("ShdA"), 0);
        c3.putInteger(charIDToTypeID("ShdB"), 0);
        c3.putInteger(charIDToTypeID("MdtL"), 8);
        c3.putInteger(charIDToTypeID("MdtA"), 0);
        c3.putInteger(charIDToTypeID("MdtB"), -8);
        c3.putInteger(charIDToTypeID("HghL"), 5);
        c3.putInteger(charIDToTypeID("HghA"), 0);
        c3.putInteger(charIDToTypeID("HghB"), -5);
        l3.putObject(charIDToTypeID("ClrB"), c3);
        d3.putList(charIDToTypeID("Adjs"), l3);
        executeAction(charIDToTypeID("ClrB"), d3, DialogModes.NO);
        L("TEST3 colorbalance(no PrsL): OK");
    } catch (e) { L("TEST3 colorbalance(no PrsL): FAIL " + e.message); }

    // ---- 测试 4: 照片滤镜（暖色）----
    try {
        var doc4 = fresh();
        var d4 = new ActionDescriptor();
        d4.putEnumerated(stringIDToTypeID("presetKind"), stringIDToTypeID("presetKindType"), stringIDToTypeID("presetKindCustom"));
        var l4 = new ActionList();
        var c4 = new ActionDescriptor();
        var col = new ActionDescriptor();
        col.putDouble(charIDToTypeID("Rd  "), 236);
        col.putDouble(charIDToTypeID("Grn "), 138);
        col.putDouble(charIDToTypeID("Bl  "), 0);
        c4.putObject(charIDToTypeID("Clr "), charIDToTypeID("RGBC"), col);
        c4.putInteger(charIDToTypeID("Dnst"), 25);
        l4.putObject(charIDToTypeID("Fltr"), c4);
        d4.putList(charIDToTypeID("Adjs"), l4);
        executeAction(stringIDToTypeID("photoFilter"), d4, DialogModes.NO);
        L("TEST4 photoFilter: OK");
    } catch (e) { L("TEST4 photoFilter: FAIL " + e.message); }

    // ---- 测试 5: 可选颜色（调白/中性色）----
    try {
        var doc5 = fresh();
        var d5 = new ActionDescriptor();
        d5.putEnumerated(stringIDToTypeID("presetKind"), stringIDToTypeID("presetKindType"), stringIDToTypeID("presetKindCustom"));
        var l5 = new ActionList();
        var c5 = new ActionDescriptor();
        c5.putEnumerated(charIDToTypeID("Clrs"), charIDToTypeID("Clrs"), charIDToTypeID("Ntrl"));
        c5.putInteger(charIDToTypeID("Cyn "), -6);
        c5.putInteger(charIDToTypeID("Mgnt"), 0);
        c5.putInteger(charIDToTypeID("Ylw "), 4);
        c5.putInteger(charIDToTypeID("Blck"), 0);
        c5.putBoolean(charIDToTypeID("Mthd"), true);
        l5.putObject(charIDToTypeID("ClrS"), c5);
        d5.putList(charIDToTypeID("Adjs"), l5);
        executeAction(charIDToTypeID("ClrS"), d5, DialogModes.NO);
        L("TEST5 selectiveColor neutral: OK");
    } catch (e) { L("TEST5 selectiveColor neutral: FAIL " + e.message); }

    var f = new File(ROOT + "/adjust_test.txt");
    f.encoding = "UTF8"; f.open("w"); f.write(log.join("\n")); f.close();
})();
