/* Visual Capitalist 느낌 시안 — 트리맵(업종·종목) · 순위 막대 */
(function () {
  var CW = 1080, CH = 1350, L = 70, R = 1010;
  var T = { paper: '#fafaf8', ink: '#101216', soft: '#6B7078', rule: '#E6E4DD', up: '#D6362C', down: '#2B6CD9' };
  var FF = "'Noto Sans KR', sans-serif";
  function font(w, px) { return w + ' ' + px + 'px ' + FF; }
  var G = null;
  function grain(X) {
    if (!G) {
      G = document.createElement('canvas'); G.width = CW; G.height = CH;
      var g = G.getContext('2d'); g.fillStyle = T.paper; g.fillRect(0, 0, CW, CH);
      var im = g.getImageData(0, 0, CW, CH), d = im.data, s = 7;
      for (var i = 0; i < d.length; i += 4) { s = (s * 16807) % 2147483647; var k = (s / 2147483647 - 0.5) * 14; d[i] += k; d[i + 1] += k; d[i + 2] += k; }
      g.putImageData(im, 0, 0);
    }
    X.drawImage(G, 0, 0);
  }
  function rr(X, x, y, w, h, r) { r = Math.min(r, w / 2, h / 2); X.beginPath(); X.moveTo(x + r, y); X.arcTo(x + w, y, x + w, y + h, r); X.arcTo(x + w, y + h, x, y + h, r); X.arcTo(x, y + h, x, y, r); X.arcTo(x, y, x + w, y, r); X.closePath(); }

  // 정사각형에 가깝게 나누는 트리맵 (squarified)
  function squarify(items, x, y, w, h) {
    var out = [], rest = items.slice().sort(function (a, b) { return b.v - a.v; });
    var total = rest.reduce(function (s, a) { return s + a.v; }, 0), scale = w * h / total;
    rest.forEach(function (a) { a.area = a.v * scale; });
    function worst(row, side) {
      var s = row.reduce(function (t, a) { return t + a.area; }, 0), mx = 0, mn = 1e18;
      row.forEach(function (a) { mx = Math.max(mx, a.area); mn = Math.min(mn, a.area); });
      return Math.max(side * side * mx / (s * s), s * s / (side * side * mn));
    }
    var row = [];
    while (rest.length) {
      var side = Math.min(w, h), c = rest[0];
      if (!row.length || worst(row.concat([c]), side) <= worst(row, side)) { row.push(c); rest.shift(); continue; }
      lay(); row = [];
    }
    if (row.length) lay();
    function lay() {
      var s = row.reduce(function (t, a) { return t + a.area; }, 0);
      if (w >= h) { var cw = s / h, yy = y; row.forEach(function (a) { var ch = a.area / cw; out.push({ it: a, x: x, y: yy, w: cw, h: ch }); yy += ch; }); x += cw; w -= cw; }
      else { var chh = s / w, xx = x; row.forEach(function (a) { var cww = a.area / chh; out.push({ it: a, x: xx, y: y, w: cww, h: chh }); xx += cww; }); y += chh; h -= chh; }
    }
    return out;
  }
  // 올해 수익률 → 색 (한국식: 오르면 빨강, 내리면 파랑)
  function retColor(y) {
    var t = Math.max(-1, Math.min(1, y / 120));
    var a = t >= 0 ? [214, 54, 44] : [43, 108, 217], k = Math.pow(Math.abs(t), 0.6), n = [214, 210, 202];
    return 'rgb(' + a.map(function (v, i) { return Math.round(n[i] + (v - n[i]) * (0.25 + 0.75 * k)); }).join(',') + ')';
  }
  function head(X, kicker, h1, h2) {
    X.textAlign = 'left'; X.textBaseline = 'alphabetic';
    X.fillStyle = T.up; X.font = font(800, 26); X.fillText(kicker, L, 110);
    X.fillStyle = T.ink; X.font = font(900, 64); X.fillText(h1, L, 186);
    X.fillStyle = T.soft; X.font = font(600, 30); X.fillText(h2, L, 236);
  }
  function foot(X, src) {
    X.strokeStyle = T.rule; X.lineWidth = 2; X.beginPath(); X.moveTo(L, 1286); X.lineTo(R, 1286); X.stroke();
    X.fillStyle = '#3A3E46'; X.textAlign = 'left'; X.font = font(700, 22); X.fillText('자료 : ' + src, L, 1320);
    X.textAlign = 'right'; X.font = font(800, 24); X.fillText('@돈굴돈굴', R, 1320);
  }

  /* A) 업종 트리맵 */
  function treemap(X, o) {
    grain(X); head(X, o.kicker, o.h1, o.h2);
    var top = 280, bot = 1180, gx = L, gw = R - L;
    var groups = squarify(o.groups, gx, top, gw, bot - top);
    groups.forEach(function (gc) {
      var g = gc.it, pad = 3, hb = 34;
      var cells = squarify(g.kids, gc.x + pad, gc.y + hb, gc.w - pad * 2, gc.h - hb - pad);
      X.fillStyle = '#2A2D33'; X.fillRect(gc.x, gc.y, gc.w, gc.h);
      cells.forEach(function (c) {
        var it = c.it;
        X.fillStyle = it.other || it.nodata ? '#C9C6BC' : retColor(it.y); X.fillRect(c.x + 1, c.y + 1, c.w - 2, c.h - 2);
        var m = Math.min(c.w, c.h);
        if (it.logo && m > 90) {
          var r = Math.min(m * 0.22, 46), lx = c.x + c.w / 2, ly = c.y + c.h / 2 - (m > 150 ? 26 : 12);
          X.save(); X.beginPath(); X.arc(lx, ly, r, 0, 7); X.clip(); X.fillStyle = '#fff'; X.fillRect(lx - r, ly - r, 2 * r, 2 * r); X.drawImage(it.logo, lx - r, ly - r, 2 * r, 2 * r); X.restore();
          X.fillStyle = '#fff'; X.textAlign = 'center';
          X.font = font(800, Math.min(28, m * 0.13)); X.fillText(it.n, lx, ly + r + Math.min(30, m * 0.15));
          if (!it.nodata) { X.font = font(900, Math.min(30, m * 0.14)); X.fillText((it.y >= 0 ? '+' : '') + Math.round(it.y) + '%', lx, ly + r + Math.min(62, m * 0.31)); }
        } else if (m > 54 && c.w > 70) {
          X.fillStyle = it.other || it.nodata ? '#3A3E46' : '#fff'; X.textAlign = 'center'; X.textBaseline = 'middle';
          X.font = font(800, 18); var nm = it.n; while (nm.length > 1 && X.measureText(nm).width > c.w - 10) nm = nm.slice(0, -1);
          X.fillText(nm, c.x + c.w / 2, c.y + c.h / 2 - (it.other ? 0 : 10));
          if (!it.other && !it.nodata) { X.font = font(900, 18); X.fillText((it.y >= 0 ? '+' : '') + Math.round(it.y) + '%', c.x + c.w / 2, c.y + c.h / 2 + 12); }
          X.textBaseline = 'alphabetic';
        }
      });
      // 업종 이름띠
      X.fillStyle = '#fff'; X.textAlign = 'left'; X.font = font(800, gc.w > 200 ? 22 : 17);
      var lab = g.n + (gc.w > 260 ? '  ' + g.capTxt : '');
      while (lab.length > 1 && X.measureText(lab).width > gc.w - 14) lab = lab.slice(0, -1);
      X.fillText(lab, gc.x + 8, gc.y + 24);
    });
    // 색 범례
    var ly0 = 1218, lx0 = L;
    X.fillStyle = T.soft; X.font = font(700, 22); X.textAlign = 'left'; X.fillText('올해 수익률', lx0, ly0 + 18);
    [-60, -20, 0, 20, 60, 120].forEach(function (v, i) {
      var x = lx0 + 140 + i * 90; X.fillStyle = retColor(v); X.fillRect(x, ly0, 84, 24);
      X.fillStyle = T.soft; X.font = font(700, 18); X.textAlign = 'center'; X.fillText((v > 0 ? '+' : '') + v + '%', x + 42, ly0 + 48);
    });
    foot(X, o.src);
  }

  /* B) 순위 막대 (로고 + 업종 꼬리표) */
  function ranked(X, o) {
    grain(X); head(X, o.kicker, o.h1, o.h2);
    var top = 290, rowH = 61, max = o.rows[0].v, x0 = L + 330, bw = R - 110 - x0;
    o.rows.forEach(function (r, i) {
      var y = top + i * rowH, cy = y + rowH / 2;
      X.fillStyle = T.soft; X.font = font(800, 22); X.textAlign = 'right'; X.textBaseline = 'middle'; X.fillText(i + 1, L + 26, cy);
      if (r.logo) { X.save(); X.beginPath(); X.arc(L + 62, cy, 22, 0, 7); X.clip(); X.fillStyle = '#fff'; X.fillRect(L + 40, cy - 22, 44, 44); X.drawImage(r.logo, L + 40, cy - 22, 44, 44); X.restore(); }
      X.textAlign = 'left'; X.fillStyle = T.ink; X.font = font(800, 26); X.fillText(r.n, L + 96, cy - 9);
      X.fillStyle = T.soft; X.font = font(600, 18); X.fillText(r.sector + ' · 시총 ' + r.capTxt, L + 96, cy + 17);
      var w = bw * r.v / max;
      X.fillStyle = r.c; rr(X, x0, cy - 17, w, 34, 6); X.fill();
      X.fillStyle = T.ink; X.font = font(900, 26); X.textAlign = 'left'; X.fillText('+' + Math.round(r.v) + '%', x0 + w + 10, cy + 1);
      X.strokeStyle = T.rule; X.lineWidth = 1; X.beginPath(); X.moveTo(L, y + rowH); X.lineTo(R, y + rowH); X.stroke();
    });
    X.textBaseline = 'alphabetic';
    // 업종 범례
    var lx = L, ly = top + o.rows.length * rowH + 40;
    o.legend.forEach(function (g) {
      X.fillStyle = g[1]; rr(X, lx, ly - 16, 22, 22, 4); X.fill();
      X.fillStyle = T.ink; X.font = font(700, 22); X.textAlign = 'left'; X.fillText(g[0], lx + 30, ly + 2);
      lx += X.measureText(g[0]).width + 70;
    });
    foot(X, o.src);
  }
  window.__vc = { treemap: treemap, ranked: ranked, grainOnly: grain };
})();
(function () {
  var CW = 1080, CH = 1350, L = 70, R = 1010;
  var T = { ink: '#101216', soft: '#6B7078', rule: '#E6E4DD', up: '#D6362C', down: '#2B6CD9', faint: '#D9D6CE' };
  var FF = "'Noto Sans KR', sans-serif";
  function font(w, px) { return w + ' ' + px + 'px ' + FF; }
  var base = window.__vc;
  function logoAt(X, im, x, y, r) {
    if (!im) return;
    X.save(); X.beginPath(); X.arc(x, y, r, 0, 7); X.clip(); X.fillStyle = '#fff'; X.fillRect(x - r, y - r, 2 * r, 2 * r); X.drawImage(im, x - r, y - r, 2 * r, 2 * r); X.restore();
    X.strokeStyle = 'rgba(0,0,0,0.1)'; X.lineWidth = 2; X.beginPath(); X.arc(x, y, r, 0, 7); X.stroke();
  }
  function head(X, kicker, h1, h2) {
    X.textAlign = 'left'; X.textBaseline = 'alphabetic';
    X.fillStyle = T.up; X.font = font(800, 26); X.fillText(kicker, L, 110);
    X.fillStyle = T.ink; X.font = font(900, 60); X.fillText(h1, L, 184);
    X.fillStyle = T.soft; X.font = font(600, 30); X.fillText(h2, L, 232);
  }
  function foot(X, src) {
    X.strokeStyle = T.rule; X.lineWidth = 2; X.beginPath(); X.moveTo(L, 1286); X.lineTo(R, 1286); X.stroke();
    X.fillStyle = '#3A3E46'; X.textAlign = 'left'; X.font = font(700, 22); X.fillText('자료 : ' + src, L, 1320);
    X.textAlign = 'right'; X.font = font(800, 24); X.fillText('@돈굴돈굴', R, 1320);
  }

  /* C) 순위 변천 (bump chart) */
  function bump(X, o) {
    base.grainOnly(X); head(X, o.kicker, o.h1, o.h2);
    var cols = o.cols, n = cols.length, x0 = L + 40, x1 = R - 190, top = 320, rowH = 86, N = 10;
    function xp(i) { return x0 + (x1 - x0) * i / (n - 1); }
    function yp(rk) { return top + (rk - 1) * rowH; }
    // 연도 눈금
    X.fillStyle = T.soft; X.font = font(700, 22); X.textAlign = 'center';
    cols.forEach(function (c, i) { X.fillText(c.label, xp(i), top - 40); });
    for (var k = 1; k <= N; k++) { X.fillStyle = T.soft; X.font = font(700, 20); X.textAlign = 'right'; X.fillText(k, L + 6, yp(k) + 7); }
    // 선 (흐린 것 먼저)
    var order = o.series.slice().sort(function (a, b) { return (a.hi ? 1 : 0) - (b.hi ? 1 : 0); });
    order.forEach(function (s) {
      X.strokeStyle = s.hi ? s.c : T.faint; X.lineWidth = s.hi ? 9 : 5; X.lineJoin = 'round'; X.lineCap = 'round';
      var seg = [];
      function flush() { if (seg.length > 1) { X.beginPath(); seg.forEach(function (p, j) { if (!j) X.moveTo(p[0], p[1]); else { var q = seg[j - 1], mx = (q[0] + p[0]) / 2; X.bezierCurveTo(mx, q[1], mx, p[1], p[0], p[1]); } }); X.stroke(); } seg = []; }
      s.ranks.forEach(function (rk, i) { if (rk && rk <= N) seg.push([xp(i), yp(rk)]); else flush(); });
      flush();
      s.ranks.forEach(function (rk, i) {
        if (!(rk && rk <= N)) return;
        X.fillStyle = s.hi ? s.c : T.faint; X.beginPath(); X.arc(xp(i), yp(rk), s.hi ? 12 : 8, 0, 7); X.fill();
      });
    });
    // 오른쪽 끝: 로고 + 이름
    o.series.forEach(function (s) {
      var rk = s.ranks[n - 1]; if (!(rk && rk <= N)) return;
      var x = xp(n - 1) + 40, y = yp(rk);
      logoAt(X, s.logo, x, y, 22);
      X.fillStyle = s.hi ? T.ink : T.soft; X.font = font(s.hi ? 800 : 700, 22); X.textAlign = 'left'; X.textBaseline = 'middle';
      X.fillText(s.n, x + 30, y + 1); X.textBaseline = 'alphabetic';
    });
    // 주석
    (o.notes || []).forEach(function (t) {
      var x = xp(t.i), y = yp(t.rk) + t.dy;
      X.fillStyle = t.c; X.font = font(800, 21); X.textAlign = t.align || 'center'; X.fillText(t.text, x, y);
    });
    foot(X, o.src);
  }

  /* D) 연초 → 지금 (dumbbell) */
  function dumbbell(X, o) {
    base.grainOnly(X); head(X, o.kicker, o.h1, o.h2);
    var top = 300, rowH = 62, x0 = L + 250, x1 = R - 20, max = o.max;
    function xp(v) { return x0 + (x1 - x0) * Math.sqrt(v / max); }   // 큰 차이가 많아 제곱근 눈금
    [10, 50, 100, 300, 600, 1000].forEach(function (t) {
      if (t > max) return; var x = xp(t);
      X.strokeStyle = T.rule; X.lineWidth = 1; X.beginPath(); X.moveTo(x, top - 20); X.lineTo(x, top + rowH * o.rows.length); X.stroke();
      X.fillStyle = T.soft; X.font = font(700, 18); X.textAlign = 'center'; X.fillText(t.toLocaleString() + '조', x, top - 30);
    });
    o.rows.forEach(function (r, i) {
      var cy = top + i * rowH + rowH / 2, a = xp(r.v0), b = xp(r.v1), up = r.v1 >= r.v0, col = up ? T.up : T.down;
      logoAt(X, r.logo, L + 20, cy, 20);
      X.fillStyle = T.ink; X.font = font(800, 23); X.textAlign = 'left'; X.textBaseline = 'middle'; X.fillText(r.n, L + 50, cy);
      X.strokeStyle = col; X.globalAlpha = 0.35; X.lineWidth = 10; X.lineCap = 'round'; X.beginPath(); X.moveTo(a, cy); X.lineTo(b, cy); X.stroke(); X.globalAlpha = 1;
      X.fillStyle = '#B9B6AE'; X.beginPath(); X.arc(a, cy, 9, 0, 7); X.fill();
      X.fillStyle = col; X.beginPath(); X.arc(b, cy, 12, 0, 7); X.fill();
      X.font = font(900, 21); X.fillStyle = col; X.textAlign = up ? 'left' : 'right';
      X.fillText((up ? '+' : '') + Math.round(r.y) + '%', up ? b + 18 : b - 18, cy + 1);
      X.textBaseline = 'alphabetic';
    });
    var ly = top + o.rows.length * rowH + 40;
    X.fillStyle = '#B9B6AE'; X.beginPath(); X.arc(L + 10, ly - 7, 9, 0, 7); X.fill();
    X.fillStyle = T.soft; X.font = font(700, 22); X.textAlign = 'left'; X.fillText('연초 시총', L + 28, ly);
    X.fillStyle = T.up; X.beginPath(); X.arc(L + 170, ly - 7, 12, 0, 7); X.fill();
    X.fillStyle = T.soft; X.fillText('지금 시총 (점 사이가 올해 움직임)', L + 192, ly);
    foot(X, o.src);
  }
  base.bump = bump; base.dumbbell = dumbbell;
})();
(function () {
  var CW = 1080, CH = 1350, L = 70, R = 1010;
  var T = { ink: '#101216', soft: '#6B7078', rule: '#E6E4DD', up: '#D6362C', down: '#2B6CD9', faint: '#D9D6CE' };
  var FF = "'Noto Sans KR', sans-serif";
  function font(w, px) { return w + ' ' + px + 'px ' + FF; }
  var base = window.__vc;
  function head(X, kicker, h1, h2) {
    X.textAlign = 'left'; X.textBaseline = 'alphabetic';
    X.fillStyle = T.up; X.font = font(800, 26); X.fillText(kicker, L, 110);
    X.fillStyle = T.ink; X.font = font(900, 60); X.fillText(h1, L, 184);
    X.fillStyle = T.soft; X.font = font(600, 30); X.fillText(h2, L, 232);
  }
  function foot(X, src) {
    X.strokeStyle = T.rule; X.lineWidth = 2; X.beginPath(); X.moveTo(L, 1286); X.lineTo(R, 1286); X.stroke();
    X.fillStyle = '#3A3E46'; X.textAlign = 'left'; X.font = font(700, 22); X.fillText('자료 : ' + src, L, 1320);
    X.textAlign = 'right'; X.font = font(800, 24); X.fillText('@돈굴돈굴', R, 1320);
  }
  function logoAt(X, im, x, y, r) {
    if (!im) return;
    X.save(); X.beginPath(); X.arc(x, y, r, 0, 7); X.clip(); X.fillStyle = '#fff'; X.fillRect(x - r, y - r, 2 * r, 2 * r); X.drawImage(im, x - r, y - r, 2 * r, 2 * r); X.restore();
  }
  function mix(c, k) { var h = c.replace('#', ''), a = [0, 2, 4].map(function (i) { return parseInt(h.substr(i, 2), 16); }); return 'rgb(' + a.map(function (v) { return Math.round(v + (255 - v) * k); }).join(',') + ')'; }
  function poly(X, p) { X.beginPath(); p.forEach(function (q, i) { X[i ? 'lineTo' : 'moveTo'](q[0], q[1]); }); X.closePath(); }
  function cen(p) { var a = 0, x = 0, y = 0; for (var i = 0; i < p.length; i++) { var q = p[i], r = p[(i + 1) % p.length], f = q[0] * r[1] - r[0] * q[1]; a += f; x += (q[0] + r[0]) * f; y += (q[1] + r[1]) * f; } return [x / (3 * a), y / (3 * a)]; }
  function inr(p, c) {                 // 가운데에서 가장 가까운 변까지 거리 (글자 넣을 여유)
    var m = 1e9;
    for (var i = 0; i < p.length; i++) {
      var a = p[i], b = p[(i + 1) % p.length], dx = b[0] - a[0], dy = b[1] - a[1], t = Math.max(0, Math.min(1, ((c[0] - a[0]) * dx + (c[1] - a[1]) * dy) / (dx * dx + dy * dy)));
      m = Math.min(m, Math.hypot(c[0] - a[0] - t * dx, c[1] - a[1] - t * dy));
    }
    return m;
  }

  /* E) 보로노이: 업종 → 종목 */
  function voronoi(X, o) {
    base.grainOnly(X); head(X, o.kicker, o.h1, o.h2);
    o.cells.forEach(function (g) {
      var col = o.colors[g.g] || '#7A8794';
      g.kids.forEach(function (k, i) {
        if (k.poly.length < 3) return;
        poly(X, k.poly); X.fillStyle = mix(col, Math.min(0.55, i * 0.07)); X.fill();
        X.strokeStyle = '#fff'; X.lineWidth = 2; X.stroke();
      });
      poly(X, g.poly); X.strokeStyle = '#fff'; X.lineWidth = 7; X.stroke();
    });
    o.cells.forEach(function (g) {
      g.kids.forEach(function (k) {
        if (k.poly.length < 3) return;
        var c = cen(k.poly), rr = inr(k.poly, c);
        if (rr < 24) return;
        var big = rr > 60, lr = Math.min(rr * 0.42, 40);
        X.textAlign = 'center'; X.textBaseline = 'middle'; X.fillStyle = '#fff';
        if (big && k.logo) { logoAt(X, k.logo, c[0], c[1] - lr * 0.7, lr); }
        var nm = k.ko || k.n; X.font = font(800, big ? Math.min(26, rr * 0.3) : Math.min(18, rr * 0.42));
        while (nm.length > 2 && X.measureText(nm).width > rr * 1.8) nm = nm.slice(0, -1);
        X.fillText(nm, c[0], big && k.logo ? c[1] + lr * 0.75 : c[1] - (rr > 34 ? 9 : 0));
        if (rr > 34) { X.font = font(900, big ? Math.min(28, rr * 0.32) : 17); X.fillText(k.cap, c[0], big && k.logo ? c[1] + lr * 0.75 + 30 : c[1] + 12); }
      });
    });
    // 업종 범례
    var lx = L, ly = 1238;
    o.legend.forEach(function (s) {
      X.font = font(800, 22); var w = X.measureText(s[0] + ' ' + s[1]).width + 44;
      if (lx + w > R) { lx = L; ly += 32; }
      X.fillStyle = o.colors[s[0]]; X.beginPath(); X.arc(lx + 9, ly - 7, 9, 0, 7); X.fill();
      X.fillStyle = T.ink; X.textAlign = 'left'; X.textBaseline = 'alphabetic'; X.fillText(s[0], lx + 24, ly);
      X.fillStyle = T.soft; X.font = font(700, 22); X.fillText(s[1], lx + 30 + X.measureText(s[0]).width + 2, ly);
      lx += w + 14;
    });
    foot(X, o.src);
  }

  /* F) 원형 막대: TOP 20 올해 수익률 */
  function radial(X, o) {
    base.grainOnly(X); head(X, o.kicker, o.h1, o.h2);
    var cx = CW / 2, cy = 770, r0 = 140, r1 = 330, n = o.rows.length, mx = o.max;   // 막대 끝 + 이름표가 카드 안에 들도록
    var step = Math.PI * 2 / n;
    // 0 고리, 눈금 고리
    function rv(v) { return r0 + (r1 - r0) * Math.sqrt(Math.min(Math.max(0, v), mx) / mx); }   // 제곱근 눈금 (큰 값이 너무 길지 않게)
    [0, 50, 100, 200].forEach(function (t) { X.strokeStyle = t ? T.rule : '#B9B6AE'; X.lineWidth = t ? 1 : 2; X.setLineDash(t ? [6, 6] : []); X.beginPath(); X.arc(cx, cy, rv(t), 0, 7); X.stroke(); X.setLineDash([]); });
    X.fillStyle = T.soft; X.font = font(700, 18); X.textAlign = 'left';
    [50, 100].forEach(function (t) { X.fillText('+' + t + '%', cx + 6, cy - rv(t) + 18); });
    o.rows.forEach(function (r, i) {
      var a = -Math.PI / 2 + i * step + step / 2, w = step * 0.62, up = r.v >= 0;
      var ra = up ? rv(r.v) : r0 - Math.min(80, 80 * Math.sqrt(Math.abs(r.v) / 60));
      X.fillStyle = up ? r.c : T.down;
      X.beginPath(); X.arc(cx, cy, Math.max(ra, r0), a - w / 2, a + w / 2); X.arc(cx, cy, Math.min(ra, r0), a + w / 2, a - w / 2, true); X.closePath(); X.fill();
      // 바깥 이름표 (막대 끝 바깥, 글자는 바깥 방향으로)
      var tr = Math.max(ra, r0) + 14;
      X.save(); X.translate(cx + Math.cos(a) * tr, cy + Math.sin(a) * tr);
      var flip = Math.cos(a) < 0; X.rotate(flip ? a + Math.PI : a);
      X.textAlign = flip ? 'right' : 'left'; X.textBaseline = 'middle';
      X.fillStyle = T.ink; X.font = font(800, 20); X.fillText(r.n + '  ' + (up ? '+' : '') + Math.round(r.v) + '%', 0, 0);
      X.restore();
    });
    X.textAlign = 'center'; X.textBaseline = 'middle';
    X.fillStyle = T.soft; X.font = font(700, 24); X.fillText(o.centerTop, cx, cy - 26);
    X.fillStyle = T.ink; X.font = font(900, 46); X.fillText(o.centerBig, cx, cy + 22);
    X.textBaseline = 'alphabetic';
    foot(X, o.src);
  }

  /* G) 그때 vs 지금: 1995 TOP 10 → 2026 TOP 10 (기울기) */
  function thenNow(X, o) {
    base.grainOnly(X); head(X, o.kicker, o.h1, o.h2);
    var top = 330, rowH = 86, xl = L + 250, xr = R - 250;
    X.fillStyle = T.soft; X.font = font(800, 30); X.textAlign = 'center';
    X.fillText(o.leftLabel, xl - 110, top - 40); X.fillText(o.rightLabel, xr + 110, top - 40);
    var same = {}; o.right.forEach(function (r, i) { same[r.key] = i; });
    o.left.forEach(function (l, i) {
      var y = top + i * rowH, j = same[l.key];
      X.textAlign = 'right'; X.textBaseline = 'middle';
      X.fillStyle = j !== undefined ? T.ink : T.soft; X.font = font(j !== undefined ? 800 : 700, 26); X.fillText(l.n, xl - 20, y - 8);
      X.fillStyle = T.soft; X.font = font(700, 18); X.fillText(l.cap, xl - 20, y + 20);
      X.fillStyle = j !== undefined ? T.up : '#C9C6BC'; X.beginPath(); X.arc(xl, y, 10, 0, 7); X.fill();
      if (j !== undefined) {
        var y2 = top + j * rowH; X.strokeStyle = T.up; X.lineWidth = 5;
        X.beginPath(); X.moveTo(xl + 12, y); X.bezierCurveTo((xl + xr) / 2, y, (xl + xr) / 2, y2, xr - 12, y2); X.stroke();
      } else { X.strokeStyle = '#D9D6CE'; X.lineWidth = 3; X.beginPath(); X.moveTo(xl + 12, y); X.lineTo(xl + 70, y); X.stroke(); X.fillStyle = '#B9B6AE'; X.font = font(700, 18); X.textAlign = 'left'; X.fillText(l.fate || '', xl + 78, y + 1); }
    });
    o.right.forEach(function (r, i) {
      var y = top + i * rowH, old = o.left.some(function (l) { return l.key === r.key; });
      X.fillStyle = old ? T.up : T.ink; X.beginPath(); X.arc(xr, y, 10, 0, 7); X.fill();
      if (r.logo) logoAt(X, r.logo, xr + 42, y, 20);
      X.textAlign = 'left'; X.textBaseline = 'middle'; X.fillStyle = T.ink; X.font = font(800, 26); X.fillText(r.n, xr + 72, y - 8);
      X.fillStyle = T.soft; X.font = font(700, 18); X.fillText(r.cap, xr + 72, y + 20);
    });
    X.textBaseline = 'alphabetic';
    X.fillStyle = T.ink; X.font = font(800, 28); X.textAlign = 'left'; X.fillText(o.note, L, top + 10 * rowH + 20);
    foot(X, o.src);
  }

  /* H) 크기 비교: 원 넓이 = 시총 — 위 줄 큰 둘, 아래 줄 작은 것들 */
  function compare(X, o) {
    base.grainOnly(X); head(X, o.kicker, o.h1, o.h2);
    var a = o.items[0], b = o.items[1], gap = 30;
    var k = (R - L - gap) / (2 * (Math.sqrt(a.v) + Math.sqrt(b.v)));
    var ra = k * Math.sqrt(a.v), rb = k * Math.sqrt(b.v), y1 = 300 + ra + 30;
    var pos = [[L + ra, y1], [R - rb, y1 - ra + rb + 40]];
    var x = R, y2 = Math.max(pos[0][1] + ra, pos[1][1] + rb) + 40;
    o.items.slice(2).forEach(function (it) { var r = k * Math.sqrt(it.v); x -= r; pos.push([x, y2 + r]); x -= r + 24; });
    o.items.forEach(function (it, i) {
      var r = k * Math.sqrt(it.v), cx = pos[i][0], cy = pos[i][1];
      X.fillStyle = it.c; X.beginPath(); X.arc(cx, cy, r, 0, 7); X.fill();
      X.textAlign = 'center'; X.textBaseline = 'middle';
      if (it.logo && r > 70) logoAt(X, it.logo, cx, cy - r * 0.32, Math.min(60, r * 0.24));
      if (r > 70) {
        X.fillStyle = '#fff'; X.font = font(800, Math.min(34, r * 0.13)); X.fillText(it.n, cx, cy + (it.logo ? r * 0.08 : -r * 0.1));
        X.font = font(900, Math.min(52, r * 0.2)); X.fillText(it.cap, cx, cy + (it.logo ? r * 0.3 : r * 0.14));
        if (it.times && r > 150) { X.font = font(800, Math.min(28, r * 0.11)); X.fillStyle = 'rgba(255,255,255,0.85)'; X.fillText(it.times, cx, cy + r * 0.38); }
        else if (it.times) { X.fillStyle = T.soft; X.font = font(800, 24); X.fillText(it.times, cx, cy + r + 28); }
      } else {
        if (it.logo) logoAt(X, it.logo, cx, cy, Math.min(r * 0.55, 40));
        X.fillStyle = T.ink; X.font = font(800, 24); X.textAlign = 'right'; X.fillText(it.n + '  ' + it.cap, cx - r - 14, cy - 4);
        if (it.times) { X.fillStyle = T.soft; X.font = font(700, 20); X.fillText(it.times, cx - r - 14, cy + 24); }
      }
      X.textBaseline = 'alphabetic';
    });
    if (o.note) { X.fillStyle = T.ink; X.font = font(800, 28); X.textAlign = 'left'; X.fillText(o.note, L, 1240); }
    foot(X, o.src);
  }
  base.voronoi = voronoi; base.radial = radial; base.thenNow = thenNow; base.compare = compare;
})();
