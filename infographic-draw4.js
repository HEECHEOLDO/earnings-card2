/* 인포그래픽 4차 — 경제 지표용: 월별 막대 · 작은 그래프 여러 개 · 여러 선 */
(function () {
  var L = 100, R = 980, TOP = 330, BOT = 1140;
  var T = { ink: '#101216', soft: '#6B7078', rule: '#E6E4DD', up: '#D6362C', down: '#2B6CD9', gray: '#C9C6BC' };
  var FF = "'Noto Sans KR', sans-serif";
  function font(w, px) { return w + ' ' + px + 'px ' + FF; }
  var base = window.__vc;
  function rr(X, x, y, w, h, r) { r = Math.max(0, Math.min(r, w / 2, Math.abs(h) / 2)); X.beginPath(); X.moveTo(x + r, y); X.arcTo(x + w, y, x + w, y + h, r); X.arcTo(x + w, y + h, x, y + h, r); X.arcTo(x, y + h, x, y, r); X.arcTo(x, y, x + w, y, r); X.closePath(); }
  function head(X, o) { base.grainOnly(X); X.fillStyle = T.ink; window.__vcTitle(X, o.h1); }
  function foot(X, src) { window.__vcFoot(X, src); }
  function nice(lo, hi, n) { var st = Math.pow(10, Math.floor(Math.log10((hi - lo) / n || 1))); while ((hi - lo) / st > n + 1) st *= st.toString()[0] === '2' ? 2.5 : 2; return st; }

  /* 1) 월별 막대 — o.bars:[{lab, v, c, hi}], o.fmt(v), o.stats:[[큰 글자, 설명, 색]] · o.line: [v|null] (전년 같은 달 등 겹쳐 그리기) */
  function columns(X, o) {
    head(X, o);
    var top = o.stats ? TOP + 150 : TOP + 10, bot = BOT - 100;
    if (o.stats) {
      var sw = (R - L) / o.stats.length;
      o.stats.forEach(function (s, i) { var x = L + sw * i; X.textAlign = 'left'; X.fillStyle = s[2] || T.ink; X.font = font(900, 52); X.fillText(s[0], x, TOP + 44); X.fillStyle = T.soft; X.font = font(700, 21); X.fillText(s[1], x, TOP + 80); });
    }
    var vs = o.bars.map(function (b) { return b.v; }).concat((o.line || []).filter(function (v) { return v != null; }));
    var mx = Math.max.apply(null, vs) * 1.12, mn = Math.min(0, Math.min.apply(null, vs));
    var st = nice(mn, mx, 5), x0 = L + 70, n = o.bars.length, bw = (R - x0) / n;
    var yp = function (v) { return bot - (bot - top) * (v - mn) / (mx - mn); };
    for (var g = 0; g <= mx; g += st) { var y = yp(g); X.strokeStyle = g === 0 ? T.ink : T.rule; X.lineWidth = g === 0 ? 2 : 1; X.beginPath(); X.moveTo(x0, y); X.lineTo(R, y); X.stroke(); X.fillStyle = T.soft; X.font = font(700, 17); X.textAlign = 'right'; X.textBaseline = 'middle'; X.fillText(o.fmt(g), x0 - 8, y); }
    X.textBaseline = 'alphabetic';
    o.bars.forEach(function (b, i) {
      var x = x0 + i * bw, y = yp(b.v), h = yp(0) - y;
      X.fillStyle = b.c || '#7A8794'; rr(X, x + bw * 0.14, y, bw * 0.72, h, Math.min(5, bw * 0.2)); X.fill();
      if (b.hi) { X.fillStyle = T.ink; X.font = font(900, 19); X.textAlign = 'center'; X.fillText(b.hiLab || o.fmt(b.v), x + bw / 2, y - 10); }
      if (b.tick) { X.fillStyle = T.soft; X.font = font(700, 17); X.textAlign = 'center'; X.fillText(b.tick, x + bw / 2, bot + 26); }
    });
    if (o.line) {
      X.strokeStyle = T.ink; X.lineWidth = 3; X.setLineDash([7, 6]); X.beginPath(); var on = false;
      o.line.forEach(function (v, i) { if (v == null) { on = false; return; } var x = x0 + i * bw + bw / 2; if (on) X.lineTo(x, yp(v)); else X.moveTo(x, yp(v)); on = true; }); X.stroke(); X.setLineDash([]);
    }
    if (o.legend) { var lx = L, ly = bot + 64; o.legend.forEach(function (g2) { X.fillStyle = g2[1]; if (g2[2]) { X.fillRect(lx, ly - 9, 26, 3); } else { rr(X, lx, ly - 18, 22, 22, 4); X.fill(); } X.fillStyle = T.ink; X.font = font(700, 21); X.textAlign = 'left'; X.fillText(g2[0], lx + 32, ly); lx += X.measureText(g2[0]).width + 66; }); }
    foot(X, o.src);
  }

  /* 2) 작은 그래프 여러 개 — o.items:[{n, sub, big, chg, up, pts:[v...], c}] 2열 */
  function multiples(X, o) {
    head(X, o);
    var cols = o.cols || 2, n = o.items.length, rows = Math.ceil(n / cols), top = TOP, gap = 20, cw = (R - L - gap * (cols - 1)) / cols, ch = Math.min(260, (BOT - top - gap * (rows - 1)) / rows);
    o.items.forEach(function (it, i) {
      var x = L + (i % cols) * (cw + gap), y = top + Math.floor(i / cols) * (ch + gap);
      X.fillStyle = 'rgba(16,18,22,0.035)'; rr(X, x, y, cw, ch, 14); X.fill();
      X.fillStyle = T.ink; X.font = font(800, 24); X.textAlign = 'left'; X.fillText(it.n, x + 18, y + 38);
      X.fillStyle = T.soft; X.font = font(700, 17); X.fillText(it.sub || '', x + 18, y + 64);
      X.textAlign = 'right'; X.fillStyle = T.ink; X.font = font(900, 30); X.fillText(it.big, x + cw - 18, y + 40);
      if (it.chg) { X.fillStyle = it.up == null ? T.soft : it.up ? T.up : T.down; X.font = font(800, 19); X.fillText(it.chg, x + cw - 18, y + 66); }
      var p = it.pts.filter(function (v) { return v != null; }); if (p.length < 2) return;
      var lo = Math.min.apply(null, p), hi = Math.max.apply(null, p); if (hi === lo) hi = lo + 1;
      var gx0 = x + 18, gx1 = x + cw - 18, gy0 = y + 84, gy1 = y + ch - 26;
      var xp = function (k) { return gx0 + (gx1 - gx0) * k / (it.pts.length - 1); }, yp = function (v) { return gy1 - (gy1 - gy0) * (v - lo) / (hi - lo); };
      X.beginPath(); var first = true, lastK = 0;
      it.pts.forEach(function (v, k) { if (v == null) return; if (first) { X.moveTo(xp(k), yp(v)); first = false; } else X.lineTo(xp(k), yp(v)); lastK = k; });
      X.strokeStyle = it.c || T.down; X.lineWidth = 3.5; X.lineJoin = 'round'; X.stroke();
      X.lineTo(xp(lastK), gy1); X.lineTo(gx0, gy1); X.closePath(); X.globalAlpha = 0.12; X.fillStyle = it.c || T.down; X.fill(); X.globalAlpha = 1;
      X.fillStyle = it.c || T.down; X.beginPath(); X.arc(xp(lastK), yp(it.pts[lastK]), 6, 0, 7); X.fill();
      if (it.x0) { X.fillStyle = T.soft; X.font = font(700, 15); X.textAlign = 'left'; X.fillText(it.x0, gx0, y + ch - 6); X.textAlign = 'right'; X.fillText(it.x1, gx1, y + ch - 6); }
    });
    foot(X, o.src);
  }

  /* 3) 여러 선 — o.series:[{n, c, pts:[[t(0~1), v]], w}], o.ticks:[[t, 라벨]], o.fmt, o.zero(가로 기준선) */
  function lines(X, o) {
    head(X, o);
    var top = TOP + 10, bot = BOT - 40, x0 = L + 70, x1 = R - 190, all = [];
    o.series.forEach(function (s) { s.pts.forEach(function (p) { all.push(p[1]); }); });
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all), pad = (hi - lo) * 0.08 || 1; lo -= pad; hi += pad; if (o.zero != null) { lo = Math.min(lo, o.zero); hi = Math.max(hi, o.zero); }
    var xp = function (t) { return x0 + (x1 - x0) * t; }, yp = function (v) { return bot - (bot - top) * (v - lo) / (hi - lo); };
    var st = nice(lo, hi, 6);
    for (var g = Math.ceil(lo / st) * st; g <= hi; g += st) { var y = yp(g); X.strokeStyle = (o.zero != null && Math.abs(g - o.zero) < st / 1e3) ? T.ink : T.rule; X.lineWidth = 1.5; X.beginPath(); X.moveTo(x0, y); X.lineTo(x1, y); X.stroke(); X.fillStyle = T.soft; X.font = font(700, 17); X.textAlign = 'right'; X.textBaseline = 'middle'; X.fillText(o.fmt(g), x0 - 8, y); }
    X.textBaseline = 'alphabetic';
    o.ticks.forEach(function (t) { X.fillStyle = T.soft; X.font = font(700, 18); X.textAlign = 'center'; X.fillText(t[1], xp(t[0]), bot + 30); });
    if (o.target != null) { var ty = yp(o.target); X.strokeStyle = T.ink; X.globalAlpha = 0.55; X.setLineDash([10, 8]); X.lineWidth = 2; X.beginPath(); X.moveTo(x0, ty); X.lineTo(x1, ty); X.stroke(); X.setLineDash([]); X.globalAlpha = 1; X.fillStyle = T.ink; X.font = font(800, 19); X.textAlign = 'right'; X.fillText(o.targetLabel || '', x1 - 8, ty - 10); }
    (o.bands || []).forEach(function (b) { X.fillStyle = 'rgba(16,18,22,0.05)'; X.fillRect(xp(b[0]), top, xp(b[1]) - xp(b[0]), bot - top); X.fillStyle = T.soft; X.font = font(700, 16); X.textAlign = 'center'; X.fillText(b[2], (xp(b[0]) + xp(b[1])) / 2, top + 20); });
    o.series.slice().reverse().forEach(function (s) {
      X.strokeStyle = s.c; X.lineWidth = s.w || 4; X.lineJoin = 'round'; X.beginPath();
      s.pts.forEach(function (p, i) { if (i) X.lineTo(xp(p[0]), yp(p[1])); else X.moveTo(xp(p[0]), yp(p[1])); }); X.stroke();
    });
    var ends = o.series.map(function (s) { var p = s.pts[s.pts.length - 1]; return { s: s, v: p[1], x: xp(p[0]), y: yp(p[1]) }; }).sort(function (a, b) { return a.y - b.y; });
    for (var k = 1; k < ends.length; k++) if (ends[k].y - ends[k - 1].y < 50) ends[k].y = ends[k - 1].y + 50;
    ends.forEach(function (e) {
      X.fillStyle = e.s.c; X.beginPath(); X.arc(e.x, yp(e.v), 8, 0, 7); X.fill();
      X.textAlign = 'left'; X.textBaseline = 'middle'; X.fillStyle = T.ink; X.font = font(800, 20); X.fillText(e.s.n, x1 + 22, e.y - 11);
      X.fillStyle = e.s.c; X.font = font(900, 22); X.fillText(o.fmt(e.v), x1 + 22, e.y + 13); X.textBaseline = 'alphabetic';
    });
    foot(X, o.src);
  }

  base.columns = columns; base.multiples = multiples; base.lines = lines;
})();
