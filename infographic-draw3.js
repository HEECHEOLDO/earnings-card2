/* 인포그래픽 3차 — 분포(히스토그램) · 나비 막대 · 달력 · 월별 열지도 · 고점 대비 하락 · 산점도 · 기울기 */
(function () {
  var L = 70, R = 1010;
  var T = { ink: '#101216', soft: '#6B7078', rule: '#E6E4DD', up: '#D6362C', down: '#2B6CD9', faint: '#D9D6CE', gray: '#C9C6BC' };
  var FF = "'Noto Sans KR', sans-serif";
  function font(w, px) { return w + ' ' + px + 'px ' + FF; }
  var base = window.__vc;
  function rr(X, x, y, w, h, r) { r = Math.max(0, Math.min(r, w / 2, h / 2)); X.beginPath(); X.moveTo(x + r, y); X.arcTo(x + w, y, x + w, y + h, r); X.arcTo(x + w, y + h, x, y + h, r); X.arcTo(x, y + h, x, y, r); X.arcTo(x, y, x + w, y, r); X.closePath(); }
  function logoAt(X, im, x, y, r) {
    if (!im) return;
    X.save(); X.beginPath(); X.arc(x, y, r, 0, 7); X.clip(); X.fillStyle = '#fff'; X.fillRect(x - r, y - r, 2 * r, 2 * r); X.drawImage(im, x - r, y - r, 2 * r, 2 * r); X.restore();
  }
  function head(X, o) {
    base.grainOnly(X);
    X.textAlign = 'left'; X.textBaseline = 'alphabetic';
    X.fillStyle = T.up; X.font = font(800, 26); X.fillText(o.kicker, L, 110);
    X.fillStyle = T.ink; var px = 64; X.font = font(900, px);
    while (px > 40 && X.measureText(o.h1).width > R - L) { px -= 2; X.font = font(900, px); }
    X.fillText(o.h1, L, 186);
  }
  function foot(X, src) {
    X.strokeStyle = T.rule; X.lineWidth = 2; X.beginPath(); X.moveTo(L, 1286); X.lineTo(R, 1286); X.stroke();
    X.fillStyle = '#3A3E46'; X.textAlign = 'left'; X.textBaseline = 'alphabetic'; X.font = font(700, 22); X.fillText(src, L, 1320);
    X.textAlign = 'right'; X.font = font(800, 24); X.fillText('@돈굴돈굴', R, 1320);
  }
  function fit(X, s, w) { if (X.measureText(s).width <= w) return s; while (s.length > 1 && X.measureText(s + '…').width > w) s = s.slice(0, -1); return s + '…'; }
  // 등락률 → 색 (한국식: 오르면 빨강) · k 는 진하기 기준
  function heat(v, k) {
    var t = Math.max(-1, Math.min(1, v / k)), a = t >= 0 ? [214, 54, 44] : [43, 108, 217], n = [232, 229, 222], m = Math.pow(Math.abs(t), 0.7);
    return 'rgb(' + a.map(function (c, i) { return Math.round(n[i] + (c - n[i]) * m); }).join(',') + ')';
  }
  function pct(v, d) { return (v > 0 ? '+' : '') + v.toFixed(d == null ? 0 : d) + '%'; }

  /* 1) 분포 — o.bins:[{lo, hi, n}], o.mark:{v, label}, o.stats:[[큰 글자, 설명]] */
  function hist(X, o) {
    head(X, o);
    // 위쪽 숫자 셋
    var sw = (R - L) / o.stats.length;
    o.stats.forEach(function (s, i) {
      var x = L + sw * i; X.textAlign = 'left';
      X.fillStyle = s[2] || T.ink; X.font = font(900, 58); X.fillText(s[0], x, 300);
      X.fillStyle = T.soft; X.font = font(700, 22); X.fillText(s[1], x, 336);
    });
    var top = 420, bot = 1110, n = o.bins.length, bw = (R - L) / n, mx = Math.max.apply(null, o.bins.map(function (b) { return b.n; }));
    o.bins.forEach(function (b, i) {
      var h = (bot - top) * b.n / mx, x = L + i * bw, mid = (b.lo + b.hi) / 2;
      X.fillStyle = mid >= 0 ? heat(Math.max(mid, 15), 80) : heat(Math.min(mid, -15), 60); rr(X, x + 2, bot - h, bw - 4, h, 4); X.fill();
      if (b.n && h > 26) { X.fillStyle = T.soft; X.font = font(700, 15); X.textAlign = 'center'; X.fillText(b.n, x + bw / 2, bot - h - 8); }
    });
    X.strokeStyle = T.ink; X.lineWidth = 2; X.beginPath(); X.moveTo(L, bot); X.lineTo(R, bot); X.stroke();
    X.fillStyle = T.soft; X.font = font(700, 18); X.textAlign = 'center';
    o.bins.forEach(function (b, i) { if (i % 2 === 0) X.fillText(b.tick, L + i * bw, bot + 30); });
    X.fillText(o.bins[n - 1].tickEnd || '', R, bot + 30);
    if (o.mark) {
      var lo = o.bins[0].lo, hi = o.bins[n - 1].hi, mxv = Math.max(lo, Math.min(hi, o.mark.v)), x = L + (R - L) * (mxv - lo) / (hi - lo);
      X.strokeStyle = T.ink; X.setLineDash([8, 6]); X.lineWidth = 3; X.beginPath(); X.moveTo(x, top - 30); X.lineTo(x, bot); X.stroke(); X.setLineDash([]);
      X.fillStyle = T.ink; X.font = font(800, 22); X.textAlign = x > R - 200 ? 'right' : 'left'; X.fillText(o.mark.label, x + (x > R - 200 ? -10 : 10), top - 10);
    }
    X.fillStyle = T.soft; X.font = font(700, 20); X.textAlign = 'center'; X.fillText(o.axis || '', (L + R) / 2, bot + 66);
    if (o.note) { X.textAlign = 'left'; X.fillStyle = T.ink; X.font = font(800, 26); X.fillText(o.note, L, 1240); }
    foot(X, o.src);
  }

  /* 2) 나비 막대 — 왼쪽 o.left 이름, 오른쪽 o.right 이름. rows:[{n, a, b}] (%) */
  function butterfly(X, o) {
    head(X, o);
    var top = 300, rowH = Math.min(60, 880 / o.rows.length), mid = (L + R) / 2, lab = 150, half = (R - L - lab) / 2 - 70;
    var mx = Math.max.apply(null, o.rows.map(function (r) { return Math.max(r.a, r.b); }));
    X.font = font(800, 24); X.textAlign = 'right'; X.fillStyle = o.ca; X.fillText(o.left, mid - lab / 2 - 10, top - 14);
    X.textAlign = 'left'; X.fillStyle = o.cb; X.fillText(o.right, mid + lab / 2 + 10, top - 14);
    o.rows.forEach(function (r, i) {
      var cy = top + i * rowH + rowH / 2, wa = half * r.a / mx, wb = half * r.b / mx, bh = rowH * 0.62;
      X.fillStyle = o.ca; rr(X, mid - lab / 2 - wa, cy - bh / 2, Math.max(wa, 2), bh, 5); X.fill();
      X.fillStyle = o.cb; rr(X, mid + lab / 2, cy - bh / 2, Math.max(wb, 2), bh, 5); X.fill();
      X.textBaseline = 'middle'; X.fillStyle = T.ink; X.font = font(800, 21); X.textAlign = 'center'; X.fillText(fit(X, r.n, lab - 8), mid, cy);
      X.font = font(800, 19); X.textAlign = 'right'; X.fillText(r.a.toFixed(1) + '%', mid - lab / 2 - wa - 8, cy);
      X.textAlign = 'left'; X.fillText(r.b.toFixed(1) + '%', mid + lab / 2 + wb + 8, cy);
      X.textBaseline = 'alphabetic';
    });
    if (o.note) { X.textAlign = 'left'; X.fillStyle = T.ink; X.font = font(800, 26); X.fillText(o.note, L, 1240); }
    foot(X, o.src);
  }

  /* 3) 달력 — o.days:[[YYYYMMDD, 등락%]], 월별 7열 달력을 4×3 */
  function calendar(X, o) {
    head(X, o);
    var by = {}; o.days.forEach(function (d) { var k = String(d[0]).slice(0, 6); (by[k] = by[k] || []).push(d); });
    var months = Object.keys(by).sort().slice(-12), cw = (R - L - 3 * 24) / 4, cell = Math.floor((cw - 6) / 7), top = 270, mh = cell * 6 + 50;
    months.forEach(function (m, i) {
      var gx = L + (i % 4) * (cw + 24), gy = top + Math.floor(i / 4) * (mh + 14), y = +m.slice(0, 4), mo = +m.slice(4) - 1;
      var first = new Date(y, mo, 1).getDay(), sum = by[m].reduce(function (t, d) { return t * (1 + d[1] / 100); }, 1) - 1;
      X.fillStyle = T.ink; X.font = font(800, 22); X.textAlign = 'left'; X.fillText((mo + 1) + '월', gx, gy + 22);
      X.fillStyle = sum >= 0 ? T.up : T.down; X.font = font(800, 19); X.textAlign = 'right'; X.fillText(pct(sum * 100, 1), gx + cell * 7, gy + 22);
      var map = {}; by[m].forEach(function (d) { map[+String(d[0]).slice(6)] = d[1]; });
      var nd = new Date(y, mo + 1, 0).getDate();
      for (var d = 1; d <= nd; d++) {
        var p = first + d - 1, cx = gx + (p % 7) * cell, cy = gy + 34 + Math.floor(p / 7) * cell, v = map[d];
        X.fillStyle = v == null ? 'rgba(16,18,22,0.05)' : heat(v, 3); rr(X, cx + 1.5, cy + 1.5, cell - 3, cell - 3, 4); X.fill();
      }
    });
    // 범례
    var ly = 1218; X.fillStyle = T.soft; X.font = font(700, 20); X.textAlign = 'left'; X.fillText('하루 등락률', L, ly + 18);
    [-3, -1.5, -0.5, 0.5, 1.5, 3].forEach(function (v, i) { var x = L + 130 + i * 70; X.fillStyle = heat(v, 3); rr(X, x, ly, 62, 24, 4); X.fill(); X.fillStyle = T.soft; X.font = font(700, 16); X.textAlign = 'center'; X.fillText(pct(v, v % 1 ? 1 : 0), x + 31, ly + 46); });
    if (o.note) { X.textAlign = 'right'; X.fillStyle = T.ink; X.font = font(800, 22); X.fillText(o.note, R, ly + 18); }
    foot(X, o.src);
  }

  /* 4) 월별 열지도 — o.years:[연], o.rows:{연:[12개월 %|null]}, o.total:{연:%} */
  function heatgrid(X, o) {
    head(X, o);
    var top = 290, ny = o.years.length, lw = 76, tw = 104, cw = (R - L - lw - tw) / 12, ch = Math.min(74, 900 / (ny + 1));
    X.fillStyle = T.soft; X.font = font(800, 19); X.textAlign = 'center';
    for (var m = 0; m < 12; m++) X.fillText((m + 1) + '월', L + lw + cw * m + cw / 2, top - 12);
    X.fillText('1년', R - tw / 2, top - 12);
    o.years.forEach(function (y, i) {
      var cy = top + i * ch;
      X.fillStyle = T.ink; X.font = font(800, 22); X.textAlign = 'left'; X.textBaseline = 'middle'; X.fillText("'" + String(y).slice(2), L, cy + ch / 2);
      o.rows[y].forEach(function (v, m) {
        var x = L + lw + cw * m;
        X.fillStyle = v == null ? 'rgba(16,18,22,0.05)' : heat(v, 10); rr(X, x + 2, cy + 2, cw - 4, ch - 4, 6); X.fill();
        if (v != null) { X.fillStyle = Math.abs(v) >= 6 ? '#fff' : '#111214'; X.font = font(800, 17); X.textAlign = 'center'; X.fillText(v.toFixed(1), x + cw / 2, cy + ch / 2 + 1); }
      });
      var t = o.total[y]; if (t != null) {
        X.fillStyle = heat(t, 40); rr(X, R - tw + 8, cy + 2, tw - 8, ch - 4, 6); X.fill();
        X.fillStyle = Math.abs(t) >= 20 ? '#fff' : '#111214'; X.font = font(900, 19); X.textAlign = 'center'; X.fillText(pct(t, 1), R - tw / 2 + 4, cy + ch / 2 + 1);
      }
      X.textBaseline = 'alphabetic';
    });
    // 월별 평균
    var ay = top + ny * ch + 18;
    X.fillStyle = T.ink; X.font = font(800, 20); X.textAlign = 'left'; X.fillText('평균', L, ay + 26);
    for (m = 0; m < 12; m++) {
      var vs = o.years.map(function (y) { return o.rows[y][m]; }).filter(function (v) { return v != null; }), a = vs.reduce(function (s, v) { return s + v; }, 0) / (vs.length || 1);
      X.fillStyle = a >= 0 ? T.up : T.down; X.font = font(900, 19); X.textAlign = 'center'; X.fillText(a.toFixed(1), L + lw + cw * m + cw / 2, ay + 26);
    }
    if (o.note) { X.textAlign = 'left'; X.fillStyle = T.ink; X.font = font(800, 26); X.fillText(o.note, L, 1240); }
    foot(X, o.src);
  }

  /* 5) 고점 대비 하락 (언더워터) — o.series:[{n, c, pts:[[t, dd%]]}], t 는 0~1 위치. o.ticks:[[t, 라벨]] */
  function underwater(X, o) {
    head(X, o);
    var top = 300, bot = 1150, x0 = L + 60, x1 = R, lo = Math.min.apply(null, o.series.map(function (s) { return Math.min.apply(null, s.pts.map(function (p) { return p[1]; })); }));
    lo = Math.floor(lo / 10) * 10; if (lo > -20) lo = -20;
    var yp = function (v) { return top + (bot - top) * v / lo; }, xp = function (t) { return x0 + (x1 - x0) * t; };
    for (var g = 0; g >= lo; g -= 10) { var y = yp(g); X.strokeStyle = g === 0 ? T.ink : T.rule; X.lineWidth = g === 0 ? 2 : 1; X.beginPath(); X.moveTo(x0, y); X.lineTo(x1, y); X.stroke(); X.fillStyle = T.soft; X.font = font(700, 18); X.textAlign = 'right'; X.textBaseline = 'middle'; X.fillText(g + '%', x0 - 10, y); }
    X.textBaseline = 'alphabetic';
    o.ticks.forEach(function (t) { X.fillStyle = T.soft; X.font = font(700, 18); X.textAlign = 'center'; X.fillText(t[1], xp(t[0]), bot + 30); });
    o.series.forEach(function (s, k) {
      X.beginPath(); X.moveTo(xp(s.pts[0][0]), yp(0)); s.pts.forEach(function (p) { X.lineTo(xp(p[0]), yp(p[1])); }); X.lineTo(xp(s.pts[s.pts.length - 1][0]), yp(0)); X.closePath();
      X.globalAlpha = k === 0 ? 0.28 : 0.0; X.fillStyle = s.c; X.fill(); X.globalAlpha = 1;
      X.strokeStyle = s.c; X.lineWidth = k === 0 ? 4 : 3; X.beginPath(); s.pts.forEach(function (p, i) { if (i) X.lineTo(xp(p[0]), yp(p[1])); else X.moveTo(xp(p[0]), yp(p[1])); }); X.stroke();
    });
    // 범례 + 최저점
    var lx = L; o.series.forEach(function (s) {
      X.fillStyle = s.c; rr(X, lx, 248, 26, 10, 3); X.fill(); X.fillStyle = T.ink; X.font = font(800, 22); X.textAlign = 'left'; X.fillText(s.n, lx + 34, 258);
      lx += X.measureText(s.n).width + 70;
      var m = s.pts.reduce(function (a, p) { return p[1] < a[1] ? p : a; }, s.pts[0]);
      X.fillStyle = s.c; X.beginPath(); X.arc(xp(m[0]), yp(m[1]), 7, 0, 7); X.fill();
      X.font = font(800, 19); X.textAlign = xp(m[0]) > R - 160 ? 'right' : 'left'; X.fillText(s.n + ' ' + m[1].toFixed(0) + '%' + (m[2] ? ' (' + m[2] + ')' : ''), xp(m[0]) + (X.textAlign === 'right' ? -10 : 10), yp(m[1]) + 26);
    });
    if (o.note) { X.textAlign = 'left'; X.fillStyle = T.ink; X.font = font(800, 26); X.fillText(o.note, L, 1240); }
    foot(X, o.src);
  }

  /* 6) 산점도 — o.pts:[{n, x, y, v, c, logo, lab}], o.xr/yr:[lo,hi], 축 이름 o.xl/o.yl */
  function scatter(X, o) {
    head(X, o);
    var top = 270, bot = 1170, x0 = L + 50, x1 = R - 10, xr = o.xr, yr = o.yr;
    var xp = function (v) { return x0 + (x1 - x0) * (Math.max(xr[0], Math.min(xr[1], v)) - xr[0]) / (xr[1] - xr[0]); }, yp = function (v) { return bot - (bot - top) * (Math.max(yr[0], Math.min(yr[1], v)) - yr[0]) / (yr[1] - yr[0]); };
    // 사분면 바탕
    X.fillStyle = 'rgba(214,54,44,0.06)'; X.fillRect(xp(0), top, x1 - xp(0), yp(0) - top);
    X.fillStyle = 'rgba(43,108,217,0.06)'; X.fillRect(x0, yp(0), xp(0) - x0, bot - yp(0));
    o.xt.forEach(function (v) { X.strokeStyle = v === 0 ? T.ink : T.rule; X.lineWidth = v === 0 ? 2 : 1; X.beginPath(); X.moveTo(xp(v), top); X.lineTo(xp(v), bot); X.stroke(); X.fillStyle = T.soft; X.font = font(700, 17); X.textAlign = 'center'; X.fillText(pct(v), xp(v), bot + 26); });
    o.yt.forEach(function (v) { X.strokeStyle = v === 0 ? T.ink : T.rule; X.lineWidth = v === 0 ? 2 : 1; X.beginPath(); X.moveTo(x0, yp(v)); X.lineTo(x1, yp(v)); X.stroke(); X.fillStyle = T.soft; X.font = font(700, 17); X.textAlign = 'right'; X.textBaseline = 'middle'; X.fillText(pct(v), x0 - 8, yp(v)); X.textBaseline = 'alphabetic'; });
    X.fillStyle = T.soft; X.font = font(800, 20); X.textAlign = 'center'; X.fillText(o.xl, (x0 + x1) / 2, bot + 58);
    X.save(); X.translate(L - 30, (top + bot) / 2); X.rotate(-Math.PI / 2); X.fillText(o.yl, 0, 0); X.restore();
    // 사분면 이름
    X.font = font(800, 20); X.fillStyle = T.up; X.textAlign = 'right'; X.fillText(o.q1 || '', x1 - 10, top + 28);
    X.fillStyle = T.down; X.textAlign = 'left'; X.fillText(o.q3 || '', x0 + 10, bot - 14);
    var mv = Math.max.apply(null, o.pts.map(function (p) { return p.v; }));
    var pts = o.pts.slice().sort(function (a, b) { return b.v - a.v; }), placed = [];
    pts.forEach(function (p) {
      var r = 8 + 42 * Math.sqrt(p.v / mv), x = xp(p.x), y = yp(p.y);
      X.globalAlpha = 0.78; X.fillStyle = p.c; X.beginPath(); X.arc(x, y, r, 0, 7); X.fill(); X.globalAlpha = 1;
      X.strokeStyle = 'rgba(255,255,255,0.9)'; X.lineWidth = 2; X.stroke();
      if (r > 22) logoAt(X, p.logo, x, y, Math.min(18, r * 0.5));
    });
    // 이름표: 큰 것부터, 겹치면 건너뜀
    pts.forEach(function (p, i) {
      if (i >= (o.labels || 14)) return;
      var r = 8 + 42 * Math.sqrt(p.v / mv), x = xp(p.x), y = yp(p.y) - r - 8;
      X.font = font(800, 18); var w = X.measureText(p.n).width, box = [x - w / 2, y - 16, x + w / 2, y + 4];
      if (box[0] < x0 || box[2] > x1 || placed.some(function (b) { return !(box[2] < b[0] || box[0] > b[2] || box[3] < b[1] || box[1] > b[3]); })) return;
      placed.push(box); X.fillStyle = T.ink; X.textAlign = 'center'; X.fillText(p.n, x, y);
    });
    foot(X, o.src);
  }

  /* 7) 기울기 — 왼쪽 순위 → 오른쪽 순위. o.rows:[{n, a(순위|null), b(순위|null), logo, c}] */
  function slope(X, o) {
    head(X, o);
    var n = o.n, top = 300, rowH = 900 / n, xa = L + 250, xb = R - 250;
    X.fillStyle = T.soft; X.font = font(800, 24); X.textAlign = 'center'; X.fillText(o.la, xa, top - 26); X.fillText(o.lb, xb, top - 26);
    var yp = function (k) { return top + (k - 0.5) * rowH; };
    o.rows.forEach(function (r) {
      var ya = r.a && r.a <= n ? yp(r.a) : null, yb = r.b && r.b <= n ? yp(r.b) : null, c = r.c;
      if (ya != null && yb != null) { X.strokeStyle = c; X.lineWidth = r.hi ? 5 : 3; X.beginPath(); X.moveTo(xa, ya); X.lineTo(xb, yb); X.stroke(); }
      else if (ya != null) { X.strokeStyle = c; X.setLineDash([6, 6]); X.lineWidth = 3; X.beginPath(); X.moveTo(xa, ya); X.lineTo(xa + 90, ya + 26); X.stroke(); X.setLineDash([]); }
      else if (yb != null) { X.strokeStyle = c; X.setLineDash([6, 6]); X.lineWidth = 3; X.beginPath(); X.moveTo(xb - 90, yb + 26); X.lineTo(xb, yb); X.stroke(); X.setLineDash([]); }
      X.textBaseline = 'middle';
      if (ya != null) {
        X.fillStyle = c; X.beginPath(); X.arc(xa, ya, 8, 0, 7); X.fill();
        X.fillStyle = T.ink; X.font = font(800, 20); X.textAlign = 'right'; X.fillText(fit(X, r.n, 190), xa - 20, ya);
        X.fillStyle = T.soft; X.font = font(800, 17); X.fillText(r.a, L + 20, ya);
      }
      if (yb != null) {
        X.fillStyle = c; X.beginPath(); X.arc(xb, yb, 8, 0, 7); X.fill();
        logoAt(X, r.logo, xb + 30, yb, 14);
        X.fillStyle = T.ink; X.font = font(800, 20); X.textAlign = 'left'; X.fillText(fit(X, r.n, 150), xb + 52, yb);
        var d = r.a ? r.a - r.b : null;
        X.textAlign = 'right'; X.font = font(900, 18); X.fillStyle = d == null || d > 0 ? T.up : d < 0 ? T.down : T.soft;
        X.fillText(d == null ? 'NEW' : d > 0 ? '▲' + d : d < 0 ? '▼' + (-d) : '–', R, yb);
      }
      X.textBaseline = 'alphabetic';
    });
    foot(X, o.src);
  }


  /* 8) 선 하나 — o.pts:[[t(0~1), v, 라벨]], o.ticks:[[t, 라벨]], o.fmt(v), o.marks:[인덱스] (최고·최저 등) */
  function line(X, o) {
    head(X, o);
    var top = 300, bot = 1130, x0 = L + 70, x1 = R - 20, vs = o.pts.map(function (p) { return p[1]; });
    var lo = Math.min.apply(null, vs), hi = Math.max.apply(null, vs), pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
    var xp = function (t) { return x0 + (x1 - x0) * t; }, yp = function (v) { return bot - (bot - top) * (v - lo) / (hi - lo); };
    var step = Math.pow(10, Math.floor(Math.log10((hi - lo) / 5))); while ((hi - lo) / step > 7) step *= 2;
    for (var g = Math.ceil(lo / step) * step; g <= hi; g += step) { var y = yp(g); X.strokeStyle = T.rule; X.lineWidth = 1; X.beginPath(); X.moveTo(x0, y); X.lineTo(x1, y); X.stroke(); X.fillStyle = T.soft; X.font = font(700, 18); X.textAlign = 'right'; X.textBaseline = 'middle'; X.fillText(o.fmt(g), x0 - 10, y); }
    X.textBaseline = 'alphabetic';
    o.ticks.forEach(function (t) { X.fillStyle = T.soft; X.font = font(700, 18); X.textAlign = 'center'; X.fillText(t[1], xp(t[0]), bot + 30); });
    X.beginPath(); o.pts.forEach(function (p, i) { if (i) X.lineTo(xp(p[0]), yp(p[1])); else X.moveTo(xp(p[0]), yp(p[1])); });
    X.lineTo(xp(o.pts[o.pts.length - 1][0]), bot); X.lineTo(xp(o.pts[0][0]), bot); X.closePath(); X.fillStyle = 'rgba(43,108,217,0.10)'; X.fill();
    X.strokeStyle = o.c || T.down; X.lineWidth = 4; X.lineJoin = 'round'; X.beginPath(); o.pts.forEach(function (p, i) { if (i) X.lineTo(xp(p[0]), yp(p[1])); else X.moveTo(xp(p[0]), yp(p[1])); }); X.stroke();
    (o.marks || []).forEach(function (k) {
      var p = o.pts[k], x = xp(p[0]), y = yp(p[1]), hiPt = p[1] > (lo + hi) / 2;
      X.fillStyle = T.ink; X.beginPath(); X.arc(x, y, 7, 0, 7); X.fill();
      X.font = font(800, 20); X.textAlign = x > x1 - 120 ? 'right' : x < x0 + 120 ? 'left' : 'center';
      X.fillText(o.fmt(p[1]) + ' (' + p[2] + ')', x, hiPt ? y - 16 : y + 32);
    });
    var e = o.pts[o.pts.length - 1];
    X.fillStyle = o.c || T.down; X.beginPath(); X.arc(xp(e[0]), yp(e[1]), 9, 0, 7); X.fill();
    if (o.note) { X.textAlign = 'left'; X.fillStyle = T.ink; X.font = font(800, 26); X.fillText(o.note, L, 1240); }
    foot(X, o.src);
  }
  base.line = line;
  base.hist = hist; base.butterfly = butterfly; base.calendar = calendar; base.heatgrid = heatgrid; base.underwater = underwater; base.scatter = scatter; base.slope = slope;
})();
