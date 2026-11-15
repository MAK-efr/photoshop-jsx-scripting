// 分通道曲线校色温 + 复合曲线提亮
// 用途：阴天/室内冷光下拍的人像，换深色底后头发/肩部发青蓝
// 作用于当前图层或调整层
#target photoshop
(function () {
    function pt(x, y) {
        var p = new ActionDescriptor();
        p.putDouble(charIDToTypeID("Hrzn"), x);
        p.putDouble(charIDToTypeID("Vrtc"), y);
        return p;
    }

    function applyCurves(channels) {
        var d = new ActionDescriptor();
        d.putEnumerated(stringIDToTypeID("presetKind"),
            stringIDToTypeID("presetKindType"), stringIDToTypeID("presetKindCustom"));
        var list = new ActionList();
        for (var i = 0; i < channels.length; i++) {
            var ch = channels[i];
            var r = new ActionDescriptor();
            var rr = new ActionReference();
            rr.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Chnl"), ch.id);
            r.putReference(charIDToTypeID("Chnl"), rr);
            var ps = new ActionList();
            // ch.points = [[in,out], ...] 必须包含 (0,0) 和 (255,255)
            for (var k = 0; k < ch.points.length; k++) {
                ps.putObject(charIDToTypeID("Pnt "), pt(ch.points[k][0], ch.points[k][1]));
            }
            r.putList(charIDToTypeID("Crv "), ps);
            list.putObject(charIDToTypeID("CrvA"), r);
        }
        d.putList(charIDToTypeID("Adjs"), list);
        executeAction(charIDToTypeID("Crvs"), d, DialogModes.NO);
    }

    // ---- 1) 校色温：加暖去青 ----
    applyCurves([
        { id: charIDToTypeID("Rd  "), points: [[0, 0], [128, 135], [255, 255]] },
        { id: charIDToTypeID("Grn "), points: [[0, 0], [128, 129], [255, 255]] },
        // B 通道：中调压暗 + 高光端额外压（专治顶部蓝边）
        { id: charIDToTypeID("Bl  "), points: [[0, 0], [128, 117], [232, 218], [255, 255]] }
    ]);

    // ---- 2) 复合曲线：提亮中间调 + 轻微 S 对比 ----
    applyCurves([
        { id: charIDToTypeID("Cmps"), points: [[0, 0], [64, 74], [160, 168], [255, 255]] }
    ]);
})();
