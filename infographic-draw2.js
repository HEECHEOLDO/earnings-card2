/* 인포그래픽 2차 — 부호 있는 막대 · 돈의 흐름(생키) · 100% 막대 · 수익률 퀼트 · 성장 곡선 · 와플 · 맞수 비교
   window.__vc 에 덧붙인다 (infographic-draw.js 다음에 읽는다). 색은 밝은 모드 기준으로 쓰고, 어두운 모드는 card-theme.js 가 바꾼다. */
(function () {
  var CW = 1080, CH = 1350, L = 100, R = 980, TOP = 330, BOT = 1140;
  var T = { ink: '#101216', soft: '#6B7078', rule: '#E6E4DD', up: '#D6362C', down: '#2B6CD9', faint: '#D9D6CE', gray: '#C9C6BC' };
  var FF = "'Noto Sans KR', sans-serif";
  function font(w, px) { return w + ' ' + px + 'px ' + FF; }
  var base = window.__vc;
  function rr(X, x, y, w, h, r) { r = Math.max(0, Math.min(r, w / 2, h / 2)); X.beginPath(); X.moveTo(x + r, y); X.arcTo(x + w, y, x + w, y + h, r); X.arcTo(x + w, y + h, x, y + h, r); X.arcTo(x, y + h, x, y, r); X.arcTo(x, y, x + w, y, r); X.closePath(); }
  function logoAt(X, im, x, y, r) {
    if (!im) return;
    X.save(); X.beginPath(); X.arc(x, y, r, 0, 7); X.clip(); X.fillStyle = '#fff'; X.fillRect(x - r, y - r, 2 * r, 2 * r); X.drawImage(im, x - r, y - r, 2 * r, 2 * r); X.restore();
  }
  function head(X, o) { base.grainOnly(X); X.fillStyle = T.ink; window.__vcTitle(X, o.h1); }
  function foot(X, src) { window.__vcFoot(X, src); }
  function fit(X, s, w) { var f = X.font, mm = f.match(/(\d+)px/), px = mm ? +mm[1] : 20; while (px > 15 && X.measureText(s).width > w) { px -= 1; X.font = f.replace(/\d+px/, px + 'px'); } if (X.measureText(s).width <= w) return s; while (s.length > 1 && X.measureText(s + '…').width > w) s = s.slice(0, -1); return s + '…'; }

  /* 1) 부호 있는 막대 — 행: {n, sub, v, lab, logo, c} · 음수가 있으면 가운데 0 축 */
  function bars(X, o) {
    head(X, o);
    var rows = o.rows, n = rows.length, top = TOP, avail = BOT - top - (o.legend ? 46 : 0), rowH = Math.min(n <= 10 ? 190 : 78, avail / n), huge = rowH >= 100;
    var neg = rows.some(function (r) { return r.v < 0; }), pos = rows.some(function (r) { return r.v > 0; });
    var mx = Math.max.apply(null, rows.map(function (r) { return Math.abs(r.v); })) || 1;
    var labF = font(900, huge ? 34 : rowH >= 66 ? 27 : 25); X.font = labF;
    var RP = R - Math.max(60, Math.max.apply(null, rows.map(function (r) { return r.v >= 0 ? X.measureText(r.lab).width : 0; })) + 14);   // 오른쪽 숫자가 데드존을 넘지 않게
    var x0 = L + 310, bw = RP - x0, zero = neg && pos ? x0 + bw * 0.35 : neg ? RP : x0;
    var span = neg && pos ? bw * 0.65 : bw, nspan = neg && pos ? bw * 0.35 - 10 : bw;
    if (neg && pos) { var mp = Math.max.apply(null, rows.map(function (r) { return r.v; })), mn = -Math.min.apply(null, rows.map(function (r) { return r.v; })); var f = mp / (mp + mn); var lw0 = huge ? 140 : 90; zero = x0 + lw0 + (bw - lw0) * (1 - f) * 0.85; span = RP - zero; nspan = zero - x0 - lw0; mx = Math.max(mp, 1e-9); var mxn = Math.max(mn, 1e-9); }
    rows.forEach(function (r, i) {
      var y = top + i * rowH, cy = y + rowH / 2, big = rowH >= 66;
      X.fillStyle = T.soft; X.font = font(800, 22); X.textAlign = 'right'; X.textBaseline = 'middle'; X.fillText(i + 1, L + 26, cy);
      logoAt(X, r.logo, L + 62, cy, huge ? 28 : big ? 24 : 21);
      X.textAlign = 'left'; X.fillStyle = T.ink; var nf = huge ? 34 : big ? 29 : 27; X.font = font(800, nf);
      while (nf > 16 && X.measureText(r.n).width > x0 - L - 110) { nf -= 1; X.font = font(800, nf); }   // 이름은 자르지 않고 줄인다 · 회색 설명 줄은 없음
      X.fillText(r.n, L + 100, cy + 1);
      var w = r.v >= 0 ? span * r.v / mx : nspan * (-r.v) / (mxn || mx), bh = huge ? Math.min(56, rowH * 0.45) : Math.min(36, rowH * 0.56);
      X.fillStyle = r.c || (r.v >= 0 ? T.up : T.down);
      if (r.v >= 0) rr(X, zero, cy - bh / 2, Math.max(w, 3), bh, 6); else rr(X, zero - w, cy - bh / 2, Math.max(w, 3), bh, 6);
      X.fill();
      X.fillStyle = T.ink; X.font = font(900, huge ? 34 : big ? 27 : 25);
      if (r.v >= 0) { X.textAlign = 'left'; X.fillText(r.lab, zero + w + 10, cy + 1); }
      else { X.textAlign = 'right'; X.fillText(r.lab, zero - w - 10, cy + 1); }
      X.strokeStyle = T.rule; X.lineWidth = 1; X.beginPath(); X.moveTo(L, y + rowH); X.lineTo(R, y + rowH); X.stroke();
    });
    if (neg && pos) { X.strokeStyle = T.soft; X.lineWidth = 2; X.beginPath(); X.moveTo(zero, top - 6); X.lineTo(zero, top + n * rowH + 6); X.stroke(); }
    X.textBaseline = 'alphabetic';
    if (o.legend) {
      var lx = L, ly = top + n * rowH + 40;
      o.legend.forEach(function (g) {
        X.fillStyle = g[1]; rr(X, lx, ly - 16, 22, 22, 4); X.fill();
        X.fillStyle = T.ink; X.font = font(700, 22); X.textAlign = 'left'; X.fillText(g[0], lx + 30, ly + 2);
        lx += X.measureText(g[0]).width + 70;
      });
    }
    foot(X, o.src);
  }

  /* 2) 돈의 흐름 (생키) — 매출 → 영업이익·영업비용 → 순이익·세금 등. o: {rev, op, ni, money(v), pct(v), period, logo} */
  function ribbon(X, xa, ya0, ya1, xb, yb0, yb1, col) {
    var m = (xa + xb) / 2;
    X.fillStyle = darkRib(col); X.beginPath(); X.moveTo(xa, ya0); X.bezierCurveTo(m, ya0, m, yb0, xb, yb0); X.lineTo(xb, yb1); X.bezierCurveTo(m, yb1, m, ya1, xa, ya1); X.closePath(); X.fill();
  }
  function sankey(X, o) {
    head(X, o);
    var GREEN = '#2E9E6B', RED = '#D9677B', GR = '#5D636D', GS = 'rgba(46,158,107,0.30)', RS = 'rgba(217,103,123,0.28)', NS = 'rgba(93,99,109,0.22)';
    var rev = o.rev, op = Math.max(o.op, 0), ni = o.ni, cost = rev - op, extra = Math.max(ni - op, 0), tax = Math.max(op - Math.max(ni, 0), 0), nip = Math.max(ni, 0);
    var top = TOP + 10, H = BOT - TOP - 20, s = H / Math.max(rev, op + extra) * 0.94, gap = 40, nw = 28;
    var xA = L + 150, xB = 490, xC = 780;
    // 노드
    var hRev = rev * s, yRev = top + (H - hRev) / 2 - 20;
    var hOp = op * s, hCost = cost * s, yOp = top, hEx = extra * s, yEx = yOp + hOp + gap * 0.5, yCost = extra > 0 ? yEx + hEx + gap * 0.7 : yOp + hOp + gap;
    var hNi = nip * s, hTax = tax * s, yNi = top - (extra ? 0 : 0), yTax = yNi + hNi + gap;
    // 리본: 매출 → 영업이익 / 영업비용
    ribbon(X, xA + nw, yRev, yRev + hOp, xB, yOp, yOp + hOp, GS);
    ribbon(X, xA + nw, yRev + hOp, yRev + hRev, xB, yCost, yCost + hCost, RS);
    // 영업이익 → 순이익 / 세금 등,  영업외 이익(있으면) → 순이익
    if (nip > 0) ribbon(X, xB + nw, yOp, yOp + Math.min(hOp, hNi), xC, yNi, yNi + Math.min(hOp, hNi), GS);
    if (hTax > 0.5) ribbon(X, xB + nw, yOp + hNi, yOp + hOp, xC, yTax, yTax + hTax, NS);
    if (extra > 0) { X.fillStyle = GREEN; X.fillRect(xB, yEx, nw, hEx); ribbon(X, xB + nw, yEx, yEx + hEx, xC, yNi + hOp, yNi + hNi, GS); }
    X.fillStyle = GR; X.fillRect(xA, yRev, nw, hRev);
    X.fillStyle = GREEN; X.fillRect(xB, yOp, nw, Math.max(hOp, 2));
    X.fillStyle = RED; X.fillRect(xB, yCost, nw, hCost);
    if (nip > 0) { X.fillStyle = GREEN; X.fillRect(xC, yNi, nw, Math.max(hNi, 2)); }
    if (hTax > 0.5) { X.fillStyle = GR; X.fillRect(xC, yTax, nw, Math.max(hTax, 2)); }
    // 이름표
    function lab(x, y, align, name, val, sub, col) {
      X.textAlign = align; X.textBaseline = 'alphabetic';
      X.fillStyle = T.soft; X.font = font(700, 22); X.fillText(name, x, y);
      X.fillStyle = col || T.ink; X.font = font(900, 34); X.fillText(val, x, y + 38);
      if (sub) { X.fillStyle = T.soft; X.font = font(700, 19); X.fillText(sub, x, y + 64); }
    }
    logoAt(X, o.logo, xA - 70, yRev + hRev / 2 - 70, 40);
    lab(xA - 16, yRev + hRev / 2 - 6, 'right', '매출', o.money(rev), o.period);
    lab(xB + nw + 14, yOp + Math.max(hOp, 0) / 2 - 20 - (hOp < 90 ? 30 : 0), 'left', o.op >= 0 ? '영업이익' : '영업손실', o.money(o.op), '100원 중 ' + Math.round(o.op / rev * 100) + '원', GREEN);
    lab(xB + nw + 14, yCost + Math.min(hCost / 2, 150) - 20, 'left', '영업비용', o.money(cost), '원가·판관비', RED);
    if (nip > 0) lab(xC + nw + 14, yNi + Math.min(hNi / 2, 120) - 20 - (hNi < 90 ? 20 : 0), 'left', '순이익', o.money(ni), '100원 중 ' + Math.round(ni / rev * 100) + '원', GREEN);
    else lab(xC + nw + 14, yNi + 20, 'left', '순손실', o.money(ni), '', T.down);
    if (hTax > 0.5) lab(xC + nw + 14, yTax + Math.min(hTax / 2, 60) - 10 + (hTax < 60 ? 10 : 0), 'left', '세금·영업외', o.money(-tax), '', T.soft);
    if (extra > 0) { X.textAlign = 'right'; X.fillStyle = GREEN; X.font = font(800, 20); X.fillText('영업외 이익 +' + o.money(extra), xB - 10, yEx + hEx / 2 + 7); }
    // 100원으로 다시 말하기
    foot(X, o.src);
  }

  /* 3) 100% 쌓은 막대 — 행: {n, logo, parts:[v...]} · o.keys:[[이름, 색, 글자색]] */
  function stack100(X, o) {
    head(X, o);
    var rows = o.rows, top = TOP + 50, rowH = Math.min(rows.length <= 6 ? 170 : 46, (BOT - top) / rows.length), x0 = L + 230, w = R - x0;
    // 범례
    var lx = L, ly = TOP + 10;
    o.keys.forEach(function (k) { X.fillStyle = k[1]; rr(X, lx, ly - 18, 22, 22, 4); X.fill(); X.fillStyle = T.ink; X.font = font(700, 22); X.textAlign = 'left'; X.fillText(k[0], lx + 30, ly); lx += X.measureText(k[0]).width + 62; });
    rows.forEach(function (r, i) {
      var cy = top + i * rowH + rowH / 2, x = x0, bh = Math.min(rowH - 10, 100);
      logoAt(X, r.logo, L + 18, cy, 17);
      X.fillStyle = T.ink; X.font = font(800, 22); X.textAlign = 'left'; X.textBaseline = 'middle'; X.fillText(fit(X, r.n, x0 - L - 56), L + 46, cy);
      r.parts.forEach(function (v, j) {
        var pw = w * v / 100; if (pw <= 0) return;
        X.fillStyle = o.keys[j][1]; X.fillRect(x, cy - bh / 2, pw, bh);
        if (pw > 54) { X.fillStyle = o.keys[j][2]; X.font = font(800, 18); X.textAlign = 'center'; X.fillText(Math.round(v) + '%', x + pw / 2, cy + 1); }
        x += pw;
      });
    });
    X.textBaseline = 'alphabetic';
    // 50% 선
    X.strokeStyle = 'rgba(16,18,22,0.35)'; X.setLineDash([6, 6]); X.lineWidth = 2; X.beginPath(); X.moveTo(x0 + w / 2, top - 8); X.lineTo(x0 + w / 2, top + rows.length * rowH + 4); X.stroke(); X.setLineDash([]);
    X.fillStyle = T.soft; X.font = font(700, 18); X.textAlign = 'center'; X.fillText('50%', x0 + w / 2, top + rows.length * rowH + 28);
    foot(X, o.src);
  }

  /* 4) 해마다 1등부터 꼴찌까지 (수익률 퀼트) — o.cols:[라벨], o.assets:[{n, c, ink, years:[v|null]}] */
  function quilt(X, o) {
    head(X, o);
    var nc = o.cols.length, na = o.assets.length, top = TOP + 30, cw = (R - L) / nc, ch = Math.min(100, (BOT - 10 - top) / na);
    X.textAlign = 'center'; X.fillStyle = T.soft; X.font = font(800, 22);
    o.cols.forEach(function (c, i) { X.fillText(c, L + cw * i + cw / 2, top - 16); });
    o.cols.forEach(function (c, i) {
      var col = o.assets.map(function (a) { return { a: a, v: a.years[i] }; }).filter(function (x) { return x.v != null; }).sort(function (p, q) { return q.v - p.v; });
      col.forEach(function (x, j) {
        var cx = L + cw * i, cy = top + j * ch;
        X.fillStyle = x.a.c; rr(X, cx + 2, cy + 2, cw - 4, ch - 4, 8); X.fill();
        X.fillStyle = x.a.ink || '#111214'; X.textAlign = 'center'; X.textBaseline = 'middle';
        X.font = font(800, 15); X.fillText(fit(X, x.a.s || x.a.n, cw - 10), cx + cw / 2, cy + ch / 2 - 13);
        X.font = font(900, 19); X.fillText((x.v > 0 ? '+' : '') + (Math.abs(x.v) >= 100 ? Math.round(x.v) : x.v.toFixed(0)) + '%', cx + cw / 2, cy + ch / 2 + 13);
      });
    });
    X.textBaseline = 'alphabetic';
    X.textAlign = 'left'; X.fillStyle = T.soft; X.font = font(700, 20);
    foot(X, o.src);
  }

  /* 5) 성장 곡선 — o.cols:[라벨], o.series:[{n, c, vals:[원]}], 로그 눈금 */
  function growth(X, o) {
    head(X, o);
    var top = TOP + 10, bot = BOT - 44, x1 = R - 200, all = [];
    o.series.forEach(function (s) { s.vals.forEach(function (v) { if (v) all.push(v); }); });
    var lo = Math.min.apply(null, all) * 0.9, hi = Math.max.apply(null, all) * 1.1, LL = Math.log(lo), LH = Math.log(hi);
    var xp = function (i) { return x0 + (x1 - x0) * i / (o.cols.length - 1); }, yp = function (v) { return bot - (bot - top) * (Math.log(v) - LL) / (LH - LL); };
    var ticks = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000].map(function (m) { return m * 1e4; }).filter(function (v) { return v >= lo && v <= hi; });
    X.font = font(700, 18); var x0 = L + 10 + Math.max.apply(null, ticks.map(function (v) { return X.measureText(o.money(v)).width; }).concat([40]));   // 세로 눈금 글자 폭만큼
    ticks.forEach(function (v) {
      var y = yp(v); X.strokeStyle = v === 1e6 ? 'rgba(16,18,22,0.45)' : T.rule; X.lineWidth = v === 1e6 ? 2 : 1; X.beginPath(); X.moveTo(x0, y); X.lineTo(x1, y); X.stroke();
      X.fillStyle = T.soft; X.font = font(700, 18); X.textAlign = 'right'; X.textBaseline = 'middle'; X.fillText(o.money(v), x0 - 10, y);
    });
    X.textAlign = 'center'; X.textBaseline = 'alphabetic';
    o.cols.forEach(function (c, i) { if (i % 2 === 0 || i === o.cols.length - 1) { X.fillStyle = T.soft; X.font = font(700, 19); X.fillText(c, xp(i), bot + 34); } });
    o.series.slice().reverse().forEach(function (s) {
      X.strokeStyle = s.c; X.lineWidth = 6; X.lineJoin = 'round'; X.lineCap = 'round'; X.beginPath();
      s.vals.forEach(function (v, i) { if (i === 0) X.moveTo(xp(i), yp(v)); else X.lineTo(xp(i), yp(v)); }); X.stroke();
    });
    // 끝 이름표 (겹치지 않게 아래로 민다)
    var ends = o.series.map(function (s) { var v = s.vals[s.vals.length - 1]; return { s: s, v: v, y: yp(v) }; }).sort(function (a, b) { return a.y - b.y; });
    for (var k = 1; k < ends.length; k++) if (ends[k].y - ends[k - 1].y < 54) ends[k].y = ends[k - 1].y + 54;
    var over = ends.length ? ends[ends.length - 1].y - (bot + 10) : 0; if (over > 0) ends.forEach(function (e) { e.y -= over; });
    ends.forEach(function (e) {
      X.fillStyle = e.s.c; X.beginPath(); X.arc(xp(o.cols.length - 1), yp(e.v), 9, 0, 7); X.fill();
      logoAt(X, e.s.logo, x1 + 34, e.y, 17);
      X.textAlign = 'left'; X.textBaseline = 'middle'; X.fillStyle = T.ink; X.font = font(800, 20); X.fillText(fit(X, e.s.n, 150), x1 + 58, e.y - 11);
      X.fillStyle = e.s.c; X.font = font(900, 22); X.fillText(o.money(e.v), x1 + 58, e.y + 13);
    });
    X.textBaseline = 'alphabetic';
    foot(X, o.src);
  }

  /* 6) 와플 (100칸) — o.items:[{n, w(%), c, logo}] 남는 칸은 '그 외' */
  function waffle(X, o) {
    head(X, o);
    var gx = L, cell = 58, g = 6, side = 10 * (cell + g) - g, gy = TOP + Math.max(0, (BOT - TOP - side) / 2), cells = [], used = 0;
    o.items.forEach(function (it, i) { var k = Math.round(it.w); if (used + k > 100) k = 100 - used; for (var j = 0; j < k; j++) cells.push(it.c); used += k; });
    while (cells.length < 100) cells.push(T.gray);
    for (var i = 0; i < 100; i++) { var cx = gx + (i % 10) * (cell + g), cy = gy + Math.floor(i / 10) * (cell + g); X.fillStyle = cells[i]; rr(X, cx, cy, cell, cell, 8); X.fill(); }
    var lx = gx + side + 28, rowH = Math.min(64, side / (o.items.length + 1)), ly = gy + (side - rowH * (o.items.length + 1)) / 2;
    o.items.concat([{ n: '그 외', w: Math.max(0, 100 - o.items.reduce(function (s, x) { return s + x.w; }, 0)), c: T.gray }]).forEach(function (it, i) {
      var cy = ly + i * rowH + rowH / 2;
      X.fillStyle = it.c; rr(X, lx, cy - 13, 26, 26, 6); X.fill();
      if (it.logo) logoAt(X, it.logo, lx + 52, cy, 17);
      var tx = lx + (it.logo ? 78 : 40); X.fillStyle = T.ink; X.font = font(800, 21); X.textAlign = 'left'; X.textBaseline = 'middle';
      X.fillText(fit(X, it.n, R - tx), tx, cy - 11);
      X.font = font(900, 22); X.fillText(it.w.toFixed(1) + '%', tx, cy + 13);
    });
    X.textBaseline = 'alphabetic';
    var by = gy + 10 * (cell + g) + 46;
    foot(X, o.src);
  }

  /* 7) 맞수 비교 — o.pairs:[{cat, a:{n,cap,v,logo,c}, b:{...}}] 원 넓이 = 시총 */
  function rivals(X, o) {
    head(X, o);
    var top = TOP, rowH = Math.min(150, (BOT - TOP) / o.pairs.length), mx = 0;
    o.pairs.forEach(function (p) { mx = Math.max(mx, p.a.v, p.b.v); });
    var rmax = rowH * 0.36, rad = function (v) { return Math.max(5, rmax * Math.sqrt(v / mx)); };
    var xa = 350, xb = 600;
    o.pairs.forEach(function (p, i) {
      var y = top + i * rowH, cy = y + rowH / 2 + 10;
      X.fillStyle = T.up; X.font = font(800, 20); X.textAlign = 'left'; X.textBaseline = 'alphabetic'; X.fillText(p.cat, L, y + 26);
      [[p.a, xa, 'right'], [p.b, xb, 'left']].forEach(function (q) {
        var it = q[0], x = q[1], r = rad(it.v);
        X.fillStyle = it.c; X.beginPath(); X.arc(x, cy, r, 0, 7); X.fill();
        if (r > 26) logoAt(X, it.logo, x, cy, Math.min(r * 0.55, 30)); else logoAt(X, it.logo, x + (q[2] === 'right' ? -r - 22 : r + 22), cy, 16);
        var tx = q[2] === 'right' ? x - Math.max(r, 40) - 16 - (r > 26 ? 0 : 0) : x + Math.max(r, 40) + 16;
        if (r <= 26) tx = q[2] === 'right' ? x - r - 48 : x + r + 48;
        X.textAlign = q[2]; X.textBaseline = 'middle'; X.fillStyle = T.ink; X.font = font(800, 23); X.fillText(it.n, tx, cy - 13);
        X.fillStyle = T.soft; X.font = font(800, 20); X.fillText(it.cap, tx, cy + 15);
      });
      var big = p.a.v >= p.b.v ? p.a : p.b, sm = big === p.a ? p.b : p.a, k = big.v / sm.v;
      X.textAlign = 'right'; X.fillStyle = T.ink; X.font = font(900, 40); X.fillText((k >= 10 ? Math.round(k) : k.toFixed(1)) + '배', R, cy - 6);
      X.fillStyle = T.soft; X.font = font(700, 18); X.fillText(big.n + '가 더 큼', R, cy + 26);
      if (i < o.pairs.length - 1) { X.strokeStyle = T.rule; X.lineWidth = 1; X.beginPath(); X.moveTo(L, y + rowH); X.lineTo(R, y + rowH); X.stroke(); }
    });
    X.textBaseline = 'alphabetic';
    X.textAlign = 'center'; X.fillStyle = T.soft; X.font = font(800, 20); X.fillText('미국', xa, top + 4); X.fillText('한국', xb, top + 4);
    foot(X, o.src);
  }

  base.bars = bars; base.sankey = sankey; base.stack100 = stack100; base.quilt = quilt; base.growth = growth; base.waffle = waffle; base.rivals = rivals;
})();
/* 돈의 흐름 (세부) — 매출 → 매출총이익·매출원가 → 영업이익·판관비(연구개발·판매관리 등) → 순이익·법인세·영업외 */
(function () {
  var L = 100, R = 980, TOP = 330, BOT = 1140;
  var T = { ink: '#101216', soft: '#6B7078' };
  var FF = "'Noto Sans KR', sans-serif";
  function font(w, px) { return w + ' ' + px + 'px ' + FF; }
  var base = window.__vc;
  function ribbon(X, xa, ya0, ya1, xb, yb0, yb1, col) {
    var m = (xa + xb) / 2;
    X.fillStyle = darkRib(col); X.beginPath(); X.moveTo(xa, ya0); X.bezierCurveTo(m, ya0, m, yb0, xb, yb0); X.lineTo(xb, yb1); X.bezierCurveTo(m, yb1, m, ya1, xa, ya1); X.closePath(); X.fill();
  }
  function logoAt(X, im, x, y, r) { if (!im) return; X.save(); X.beginPath(); X.arc(x, y, r, 0, 7); X.clip(); X.fillStyle = '#fff'; X.fillRect(x - r, y - r, 2 * r, 2 * r); X.drawImage(im, x - r, y - r, 2 * r, 2 * r); X.restore(); }
  var G1 = '#2E9E6B', GS = 'rgba(46,158,107,0.28)', RD = ['#D9677B', '#E58C6B', '#C77DB5', '#E3A35A'], RS = 'rgba(217,103,123,0.24)', GR = '#7A808A', GRS = 'rgba(122,128,138,0.24)';
  function sankey2(X, o) {
    base.grainOnly(X); X.fillStyle = T.ink; window.__vcTitle(X, o.h1);
    var d = o.d, rev = d.rev, op = d.op, ni = d.ni, money = o.money, p100 = function (v) { return '100원 중 ' + Math.round(v / rev * 100) + '원'; };
    var hasG = d.cogs != null && d.cogs > 0 && d.gross > 0;
    var gross = hasG ? d.gross : rev, cogs = hasG ? d.cogs : 0;
    // 영업비용 쪼개기
    var ox = [];
    if (d.rnd) ox.push(['연구개발비', d.rnd]);
    if (d.sga) ox.push([d.rnd ? '판매·관리비' : '판관비', d.sga]);
    else { if (d.sm) ox.push(['마케팅비', d.sm]); if (d.ga) ox.push(['일반관리비', d.ga]); }
    var used = ox.reduce(function (s, x) { return s + x[1]; }, 0), etc = gross - op - used;
    if (etc > rev * 0.01) ox.push([ox.length ? '기타 영업비용' : '영업비용', etc]);
    else if (etc < -rev * 0.01 && ox.length) { var sc = (gross - op) / used; ox.forEach(function (x) { x[1] *= sc; }); }   // 기타 영업이익이 있으면 비례로 맞춘다
    var tax = Math.max(0, d.tax || 0), nonop = op - tax - ni;   // + 면 영업외 손실, - 면 영업외 이익
    var top = TOP + 10, gap = 16, H = BOT - top - 10;
    var cnt3 = 1 + ox.length, s = (H - gap * Math.max(cnt3, 2)) / Math.max(rev, gross + Math.max(0, -nonop));
    var nw = 22, xA = L + 120, xB = L + 330, xC = L + 555, xD = L + 760;
    // 노드 위치
    var hRev = rev * s, yRev = top;
    var yG = top, hG = gross * s, yC = yG + hG + gap, hC = cogs * s;
    var yOp = top, hOp = op * s, nodes3 = [], y = yOp + hOp + gap;
    ox.forEach(function (x, i) { var h = x[1] * s; nodes3.push({ n: x[0], v: x[1], y: y, h: h, c: RD[i % RD.length] }); y += h + gap * 0.6; });
    var yNi = top, hNi = Math.max(0, ni) * s, n4 = [], y4 = yNi + hNi + gap;
    if (tax > 0) { n4.push({ n: '법인세', v: tax, y: y4, h: tax * s, c: GR }); y4 += tax * s + gap * 0.6; }
    if (nonop > rev * 0.002) { n4.push({ n: '영업외 손실', v: nonop, y: y4, h: nonop * s, c: GR }); }
    // 리본: 매출 → 매출총이익 / 매출원가
    if (hasG) { ribbon(X, xA + nw, yRev, yRev + hG, xB, yG, yG + hG, GS); ribbon(X, xA + nw, yRev + hG, yRev + hRev, xB, yC, yC + hC, RS); }
    var srcX = hasG ? xB : xA, srcY = hasG ? yG : yRev;
    // 매출총이익 → 영업이익 / 영업비용들
    ribbon(X, srcX + nw, srcY, srcY + hOp, xC, yOp, yOp + hOp, GS);
    var cur = srcY + hOp; nodes3.forEach(function (n) { ribbon(X, srcX + nw, cur, cur + n.h, xC, n.y, n.y + n.h, RS); cur += n.h; });
    // 영업이익 → 순이익 / 법인세 / 영업외
    var cu = yOp, take = Math.min(hNi, hOp);
    if (take > 0) ribbon(X, xC + nw, cu, cu + take, xD, yNi, yNi + take, GS); cu += take;
    n4.forEach(function (n) { ribbon(X, xC + nw, cu, cu + n.h, xD, n.y, n.y + n.h, GRS); cu += n.h; });
    var yEx = null;
    if (nonop < -rev * 0.002) {                   // 영업외 이익이 순이익으로 들어온다
      var hEx = -nonop * s; yEx = yOp + hOp + gap * 0.4;
      ribbon(X, xC + nw, yEx, yEx + hEx, xD, yNi + take, yNi + hNi, GS);
      X.fillStyle = G1; X.fillRect(xC, yEx, nw, hEx);
      nodes3.forEach(function (n) { if (n.y < yEx + hEx + gap * 0.6) { var sh = yEx + hEx + gap * 0.6 - n.y; n.y += sh; } });
    }
    // 노드 막대
    X.fillStyle = '#5D636D'; X.fillRect(xA, yRev, nw, hRev);
    if (hasG) { X.fillStyle = G1; X.fillRect(xB, yG, nw, hG); X.fillStyle = RD[0]; X.fillRect(xB, yC, nw, Math.max(2, hC)); }
    X.fillStyle = G1; X.fillRect(xC, yOp, nw, Math.max(2, hOp));
    nodes3.forEach(function (n) { X.fillStyle = n.c; X.fillRect(xC, n.y, nw, Math.max(2, n.h)); });
    if (hNi > 0) { X.fillStyle = G1; X.fillRect(xD, yNi, nw, hNi); }
    n4.forEach(function (n) { X.fillStyle = n.c; X.fillRect(xD, n.y, nw, Math.max(2, n.h)); });
    // 이름표 — 한 열 안에서 겹치지 않게 아래로 민다
    function labels(list, x, maxW) {
      list.sort(function (a, b) { return a.y - b.y; });
      var last = -1e9;
      list.forEach(function (t) {
        var h = t.sub ? 82 : 58, y0 = Math.max(t.y - h / 2, last + 6); last = y0 + h;
        X.textAlign = 'left'; X.textBaseline = 'alphabetic';
        X.fillStyle = T.soft; X.font = font(700, 20); X.fillText(t.n, x, y0 + 20);
        X.fillStyle = t.c || T.ink; var fs = t.big ? 32 : 27; X.font = font(900, fs); while (fs > 18 && X.measureText(t.v).width > maxW) { fs -= 1; X.font = font(900, fs); }
        X.fillText(t.v, x, y0 + 20 + fs + 2);
        if (t.sub) { X.fillStyle = T.soft; X.font = font(700, 18); X.fillText(t.sub, x, y0 + 20 + fs + 26); }
      });
    }
    logoAt(X, o.logo, xA - 60, yRev + hRev / 2 - 70, 34);
    X.textAlign = 'right'; X.fillStyle = T.soft; X.font = font(700, 20); X.fillText('매출', xA - 12, yRev + hRev / 2 - 16);
    var rf = 34; X.fillStyle = T.ink; X.font = font(900, rf); while (rf > 22 && X.measureText(money(rev)).width > xA - L - 16) { rf -= 2; X.font = font(900, rf); } X.fillText(money(rev), xA - 12, yRev + hRev / 2 + 20);
    X.fillStyle = T.soft; X.font = font(700, 18); X.fillText(o.period, xA - 12, yRev + hRev / 2 + 46);
    if (hasG) labels([{ n: '매출총이익', v: money(gross), sub: p100(gross), y: yG + Math.min(hG, 160) / 2, c: G1, big: 1 }, { n: '매출원가', v: money(cogs), y: yC + Math.min(hC, 140) / 2, c: RD[0] }], xB + nw + 10, xC - xB - nw - 20);
    var l3 = [{ n: '영업이익', v: money(op), sub: p100(op), y: yOp + Math.min(hOp, 140) / 2, c: G1, big: 1 }];
    nodes3.forEach(function (n) { l3.push({ n: n.n, v: money(n.v), y: n.y + Math.min(n.h, 120) / 2, c: n.c }); });
    if (yEx != null) l3.push({ n: '영업외 이익', v: '+' + money(-nonop), y: yEx + (-nonop * s) / 2, c: G1 });
    labels(l3, xC + nw + 10, xD - xC - nw - 20);
    var l4 = [{ n: ni >= 0 ? '순이익' : '순손실', v: money(ni), sub: p100(ni), y: yNi + Math.min(hNi, 140) / 2, c: G1, big: 1 }];
    n4.forEach(function (n) { l4.push({ n: n.n, v: '-' + money(n.v), y: n.y + n.h / 2, c: T.soft }); });
    labels(l4, xD + nw + 10, R - xD - nw - 10);
    window.__vcFoot(X, o.src);
  }
  base.sankey2 = sankey2;
})();
/* 돈의 흐름 (레퍼런스 배치) — 왼쪽 매출 종류(파랑) → 총 매출 → 위로 이익(초록) 계단, 아래로 비용(빨강) 갈래
   o: {segs:[{n,v}], rev, cogs, op, opex, items:[{n,v}] (영업비용 세부), ni, tax, nonop(+ 손실 / - 이익), money, period, logo} */
(function () {
  var L = 100, R = 980, TOP = 330, BOT = 1140;
  var FF = "'Noto Sans KR', sans-serif";
  function font(w, px) { return w + ' ' + px + 'px ' + FF; }
  var base = window.__vc;
  var REC = null, GID = 0;
  var RB = [], BB = [], TB = [], WIDE = false;   // 지금 그리는 카드의 리본·막대·글자 상자 — 이름표 자리를 고를 때 피한다   // 글자 크기 고르기용 시험 그리기 — 글자·막대 상자를 모은다
  var BL = '#3E74D6', BLS = 'rgba(62,116,214,0.26)', GN = '#2E9E6B', GNS = 'rgba(46,158,107,0.30)', RD = '#C8434F', RDS = 'rgba(200,67,79,0.26)', INK = '#101216', SOFT = '#6B7078';
  // 다크 모드: 옅은 리본은 검정 바탕에서 거의 안 보이니 진하기(불투명도)만 올린다 — 색은 그대로
  function darkRib(col) {
    var k = window.__ribK != null ? window.__ribK : 1.9;
    if (!(window.CardTheme && CardTheme.isDark && CardTheme.isDark()) || k === 1) return col;
    var mm = /^rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)$/.exec(col);
    if (!mm) return col;
    var RV = window.__ribV != null ? window.__ribV : 0.5;
    if (RV) {                                                // 선명하게: 채도는 올리고 밝기는 중간 이상으로 (흰색을 섞지 않아 탁해지지 않게)
      var v = vivid(+mm[1], +mm[2], +mm[3], RV);
      return 'rgba(' + v[0] + ',' + v[1] + ',' + v[2] + ',' + Math.min(0.85, +mm[4] * k).toFixed(3) + ')';
    }
    var L = window.__ribL != null ? window.__ribL : 0, f = function (v) { return Math.round(+v + (255 - v) * L); };   // 색을 흰색 쪽으로 L 만큼 밝게 (검정에 섞여 탁해지지 않게)
    return 'rgba(' + f(mm[1]) + ',' + f(mm[2]) + ',' + f(mm[3]) + ',' + Math.min(0.85, +mm[4] * k).toFixed(3) + ')';
  }
  function vivid(r, g, b, lv) {
    r /= 255; g /= 255; b /= 255;
    var mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, d = mx - mn, h = 0, s = 0;
    if (d) { s = d / (1 - Math.abs(2 * l - 1)); h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h *= 60; if (h < 0) h += 360; }
    if (s > 0.15) s = Math.max(s, 0.72);
    l = Math.max(l, lv + (h > 195 && h < 265 ? 0.1 : 0));              // 파랑은 같은 밝기여도 어둡게 보여서 한 단계 더 밝게
    var C = (1 - Math.abs(2 * l - 1)) * s, x = C * (1 - Math.abs((h / 60) % 2 - 1)), m = l - C / 2;
    var q = h < 60 ? [C, x, 0] : h < 120 ? [x, C, 0] : h < 180 ? [0, C, x] : h < 240 ? [0, x, C] : h < 300 ? [x, 0, C] : [C, 0, x];
    return [Math.round((q[0] + m) * 255), Math.round((q[1] + m) * 255), Math.round((q[2] + m) * 255)];
  }
  function darkBar(col) {                                               // 다크 모드: 막대 색도 한 단계 밝게 (같은 색 계열)
    var BV = window.__barV != null ? window.__barV : 0.58;
    if (BV && window.CardTheme && CardTheme.isDark && CardTheme.isDark() && /^#[0-9a-f]{6}$/i.test(col)) {
      var v = vivid(parseInt(col.substr(1, 2), 16), parseInt(col.substr(3, 2), 16), parseInt(col.substr(5, 2), 16), BV);
      return '#' + v.map(function (z) { return ('0' + z.toString(16)).slice(-2); }).join('');
    }
    var L = window.__barL != null ? window.__barL : 0;
    if (!L || !(window.CardTheme && CardTheme.isDark && CardTheme.isDark()) || !/^#[0-9a-f]{6}$/i.test(col)) return col;
    var h = function (i) { var v = parseInt(col.substr(i, 2), 16); return ('0' + Math.round(v + (255 - v) * L).toString(16)).slice(-2); };
    return '#' + h(1) + h(3) + h(5);
  }
  function rib(X, xa, ya0, ya1, xb, yb0, yb1, col) {
    var m = (xa + xb) / 2;
    X.fillStyle = darkRib(col); X.beginPath(); X.moveTo(xa, ya0); X.bezierCurveTo(m, ya0, m, yb0, xb, yb0); X.lineTo(xb, yb1); X.bezierCurveTo(m, yb1, m, ya1, xa, ya1); X.closePath(); X.fill();
    if (window.__sankeyDbg) window.__sankeyDbg.ribs.push([xa, ya0, ya1, xb, yb0, yb1]);
    var rr = { rib: 1, xa: xa, xb: xb, ya0: ya0, ya1: ya1, yb0: yb0, yb1: yb1 };
    if (Math.max(Math.abs(ya1 - ya0), Math.abs(yb1 - yb0)) > 0.4) { RB.push(rr); if (REC) REC.push(rr); }
  }
  /* 이름표 자리 고르기 — 후보 자리를 차례로 재 보고, 리본·막대·다른 글자·데드존에 닿지 않는 첫 자리에 그린다.
     lines: [글, 굵기, 크기, 색, 기준점에서 y 차이]  cands: [x, y, 정렬] */
  function boxOf(X, lines, c) {
    var bx = null;
    lines.forEach(function (l) {
      X.font = font(l[1], l[2]); X.textAlign = c[2] || 'center';
      var mm = X.measureText(l[0]), x = c[0], y = c[1] + l[4];
      var b0 = [x - mm.actualBoundingBoxLeft, y - mm.actualBoundingBoxAscent, x + mm.actualBoundingBoxRight, y + mm.actualBoundingBoxDescent];
      bx = bx ? [Math.min(bx[0], b0[0]), Math.min(bx[1], b0[1]), Math.max(bx[2], b0[2]), Math.max(bx[3], b0[3])] : b0;
    });
    return { x0: bx[0], y0: bx[1], x1: bx[2], y1: bx[3] };
  }
  function clash(a, all) {                                            // 0 = 깨끗. all 이면 몇 군데 닿는지 센다 (가장 덜 나쁜 자리 고르기용)
    var n = 0, k = REC ? 0 : 2;     // 실제 그릴 때는 2px 여유 — 시험 그리기와 글자 폭이 1px 다르게 재지는 일이 있어, 시험에서 고른 자리가 그대로 뽑히게
    if (a.x0 < L - 4 - k || a.x1 > R + 4 + k || a.y0 < TOP + 34 - k || a.y1 > BOT + 22 + k) { if (!all) return 1; n += 5; }   // 위쪽은 범례 줄보다 아래
    var ov = function (c, p) { return Math.min(a.x1, c.x1) - Math.max(a.x0, c.x0) > -p && Math.min(a.y1, c.y1) - Math.max(a.y0, c.y0) > -p; };
    for (var i = 0; i < BB.length; i++) if (ov(BB[i], 3 - k)) { if (!all) return 1; n += 3; }
    for (i = 0; i < TB.length; i++) if (ov(TB[i], 6 - k)) { if (!all) return 1; n += 3; }
    for (i = 0; i < RB.length; i++) if (ribHit(RB[i], a, 3 - k)) { if (!all) return 1; n += 1; }
    return n;
  }
  function group(X, lines, cands) {
    var pick = cands[0];
    var found = false;
    for (var i = 0; i < cands.length; i++) if (!clash(boxOf(X, lines, cands[i]))) { pick = cands[i]; found = true; break; }
    if (!found && WIDE) {                                                // (가장 작은 글자로도 안 될 때만) 첫 자리 둘레를 가까운 순서로 넓게 훑는다
      var ring = [];
      for (var dx = -90; dx <= 90; dx += 10) for (var dy = -110; dy <= 60; dy += 10) ring.push([dx, dy, dx * dx + dy * dy * 1.5]);
      ring.sort(function (p, q) { return p[2] - q[2]; });
      for (i = 0; i < ring.length; i++) { var c = [cands[0][0] + ring[i][0], cands[0][1] + ring[i][1], cands[0][2]]; if (!clash(boxOf(X, lines, c))) { pick = c; found = true; break; } }
    }
    if (!found) {                                                        // 어디도 깨끗하지 않으면 가장 덜 닿는 후보
      var bs = 1e9;
      for (i = 0; i < cands.length; i++) { var sc = clash(boxOf(X, lines, cands[i]), 1) + i * 0.001; if (sc < bs) { bs = sc; pick = cands[i]; } }
    }
    GID++;
    lines.forEach(function (l) { txt(X, l[0], pick[0], pick[1] + l[4], l[1], l[2], l[3], pick[2] || 'center'); });
    return pick;
  }
  // 막대 위 이름표 후보: 제자리 → 오른쪽·왼쪽으로 조금씩 → 위로 조금씩 (기둥 사이 범위 안)
  function aboveCands(x, y, w, xl, xr) {
    // 막대 바로 위에서만 고른다 — 이름표가 늘 자기 막대 위를 덮고 있어야 어느 막대 이름인지 헷갈리지 않는다 (WIDE 일 때만 더 멀리)
    var out = [], dys = WIDE ? [0, -10, -20, -32, -46, -62, -80, -100, -124] : [0, -10, -20, -32, -46, -62, -80, -100], dxs = WIDE ? [0, 0.3, -0.3, 0.6, -0.6, 0.9, -0.9, 1.2, -1.2] : [0, 0.3, -0.3, 0.6, -0.6, 0.85, -0.85];
    dys.forEach(function (dy) { dxs.forEach(function (k) { out.push([x + k * w, y + dy, 'center']); }); });   // 겹침 여부는 clash 가 다 본다
    return out;
  }
  // 글자 상자가 리본(굽은 띠)과 겹치는지 — 띠의 위·아래 곡선은 같은 x(t)를 쓰므로 t 를 촘촘히 훑는다
  function ribHit(r, a, p) {
    for (var i = 0; i <= 48; i++) {
      var t = i / 48, u = 1 - t, bx = u * u * u * r.xa + 3 * u * u * t * ((r.xa + r.xb) / 2) + 3 * u * t * t * ((r.xa + r.xb) / 2) + t * t * t * r.xb;
      if (bx < a.x0 - p || bx > a.x1 + p) continue;
      var e = u * u * u + 3 * u * u * t, f = 3 * u * t * t + t * t * t;           // 위·아래 곡선의 y 가중치
      var y0 = e * r.ya0 + f * r.yb0, y1 = e * r.ya1 + f * r.yb1;
      if (Math.min(y1, a.y1 + p) - Math.max(y0, a.y0 - p) > 0) return true;
    }
    return false;
  }
  function bar(X, x, y, w, h, col, v) { BB.push({ x0: x, x1: x + w, y0: y, y1: y + h }); if (REC) REC.push({ bar: 1, x0: x, x1: x + w, y0: y, y1: y + h }); X.fillStyle = darkBar(col); X.fillRect(x, y, w, h); if (window.__sankeyDbg) window.__sankeyDbg.bars.push([x, y, w, h, v == null ? null : v]); }
  function logoAt(X, im, x, y, r) { if (!im) return; X.save(); X.beginPath(); X.arc(x, y, r, 0, 7); X.clip(); X.fillStyle = '#fff'; X.fillRect(x - r, y - r, 2 * r, 2 * r); X.drawImage(im, x - r, y - r, 2 * r, 2 * r); X.restore(); }
  function txt(X, s, x, y, w, px, col, align, maxW) {
    X.font = font(w, px); if (maxW) while (px > 14 && X.measureText(s).width > maxW) { px -= 1; X.font = font(w, px); }
    X.fillStyle = col; X.textAlign = align || 'left';
    var m0 = X.measureText(s); TB.push({ x0: x - m0.actualBoundingBoxLeft, x1: x + m0.actualBoundingBoxRight, y0: y - m0.actualBoundingBoxAscent, y1: y + m0.actualBoundingBoxDescent });
    if (REC) { var mm = m0; REC.push({ g: GID, t: s, x0: x - mm.actualBoundingBoxLeft, x1: x + mm.actualBoundingBoxRight, y0: y - mm.actualBoundingBoxAscent, y1: y + mm.actualBoundingBoxDescent }); return px; }
    X.fillText(s, x, y); return px;
  }
  /* 영업손실인 회사 — 영업비용이 매출총이익보다 크다. 모자란 만큼(영업손실)을 위에서 들여와 영업비용을 채운다 */
  /* 매출 종류 이름표 — 막대 옆에. 많아서 아래로 밀리면 간격·글자를 줄이고, 바닥을 넘지 않게 위로 되민다 */
  /* 매출 구분 → 총 매출 리본. 부문 합이 총매출보다 크면(부문끼리 사고판 내부 거래) 줄여 그리지 않고,
     넘치는 만큼을 총 매출 막대 밑 회색 '내부거래 제거' 막대로 흘려 보낸다 — 막대 높이 = 금액 그대로 */
  function segFlow(X, segs, s, g, x0, x1, nw, ys, gapS, rev, elim) {
    var tS = segs.reduce(function (a, x) { return a + x.v; }, 0), E = elim ? Math.max(0, tS - rev) : 0, kS = E > 0 ? 1 : rev / tS;
    var cur = g.yR, cum = 0, sy = g.yR + g.hR + 22, sc = sy;
    segs.forEach(function (sg) {
      var h = sg.v * s * kS, p1 = Math.max(0, Math.min(h, g.hR - cum)), p2 = h - p1; sg.y = ys; sg.h = h;
      if (p1 > 0) rib(X, x0 + nw, ys, ys + p1, x1, cur, cur + p1, BLS);
      if (p2 > 0.01) { rib(X, x0 + nw, ys + p1, ys + h, x1, sc, sc + p2, 'rgba(150,155,165,0.32)'); sc += p2; }
      cum += h; cur += p1; ys += h + gapS;
    });
    return E > 0 ? { y: sy, h: E * s, v: E } : null;
  }
  function elimDraw(X, el, x1, nw, m, FS) {
    if (!el) return;
    bar(X, x1, el.y, nw, Math.max(2, el.h), '#9aa0a8', el.v);
    var cx = x1 + nw / 2, by = el.y + Math.max(2, el.h) + 22 * FS;
    var lnI = [['내부거래 제거', 700, Math.round(17 * FS), SOFT, 0], ['−' + m(el.v), 900, Math.round(22 * FS), SOFT, 26 * FS]], cI = [];
    [0, 14, 28, 44].forEach(function (dy) { cI.push([cx, by + dy, 'center']); cI.push([x1 - 8, by - 10 + dy, 'right']); cI.push([cx - 30, by + dy, 'center']); });
    group(X, lnI, cI);
  }
  function segLabels(X, segs, x0, top, bot, m, FS) {
    FS = FS || 1;
    var n = segs.length, H0 = 60 * FS, step = Math.min(H0, (bot - top) / n), k = step / 60, ys = [];
    segs.forEach(function (sg, i) { ys[i] = Math.max(sg.y + sg.h / 2 - 12 * k, i ? ys[i - 1] + step : top + 18); });
    for (var i = n - 1; i >= 0; i--) {                                  // 바닥 넘으면 위로
      var lim = (i === n - 1 ? bot - 32 * k : ys[i + 1] - step);
      if (ys[i] > lim) ys[i] = lim;
    }
    segs.forEach(function (sg, i) {
      GID++; var kk = Math.min(FS, Math.max(0.62, k * 0.94));                  // 줄 간격(step)보다 글자가 크면 겹친다 — 간격에 맞춰 줄인다
      txt(X, sg.n, x0 - 10, ys[i], 700, Math.round(21 * kk), BL, 'right', x0 - L - 12);
      txt(X, m(sg.v), x0 - 10, ys[i] + 31 * kk, 900, Math.round(26 * kk), BL, 'right', x0 - L - 12);
    });
  }
  function sankeyLoss(X, o) {
    var m = o.money, rev = o.rev, cogs = Math.max(0, o.cogs || 0), gross = rev - cogs, op = o.op, L0 = -op, opex = gross - op, ni = o.ni;
    var segs = (o.segs || []).filter(function (x) { return x.v > rev * 0.002; }), items = (o.items || []).filter(function (x) { return x.v > opex * 0.004; });
    var hasSeg = segs.length >= 2, hasG = cogs > rev * 0.005 && gross > 0, hasItems = items.length >= 2, DK = '#8E2430', DKS = 'rgba(142,36,48,0.30)';
    var lx = L, ly = TOP + 2;
    [['매출', BL], ['이익', GN], ['비용·손실', RD]].forEach(function (k) { X.fillStyle = k[1]; X.fillRect(lx, ly - 4, 30, 6); X.fillStyle = SOFT; X.font = font(700, 20); X.textAlign = 'left'; X.fillText(k[0], lx + 38, ly + 4); lx += k[0].length > 2 ? 134 : 104; });
    if (o.fxNote) { X.fillStyle = SOFT; X.font = font(700, 20); X.textAlign = 'right'; X.fillText(o.fxNote, R, ly + 4); }
    var FS = o.__FS || 1.18;
    function tw(s, w, px) { X.font = font(w, px); return X.measureText(s).width; }
    var segW = hasSeg ? Math.min(230, Math.max.apply(null, segs.map(function (sg) { return Math.max(tw(sg.n, 700, 21 * FS), tw(m(sg.v), 900, 26 * FS)); }))) : 0;
    var rightW = Math.min(210, Math.max(96, Math.max.apply(null, (hasItems ? items : [{ n: '영업비용', v: opex }]).map(function (it) { return Math.max(tw(it.n, 700, 19 * FS), tw(m(it.v), 900, 26 * FS)); }))));
    var nw = 20, x0 = hasSeg ? L + segW + 14 : L, x1 = hasSeg ? x0 + 150 : L + Math.max(40, tw(m(rev), 900, 30 * FS) / 2 + 4), x4 = R - rightW - nw - 12, x2 = x1 + (x4 - x1) * 0.36, x3 = x1 + (x4 - x1) * 0.68;
    var top = TOP + 100, bot = BOT - 8, LH = Math.max(62, 54 * FS);
    // 위 이름표(총 매출 · 영업손실 · 영업비용)가 옆끼리 겹칠 만큼 기둥이 가까우면, 겹치는 수만큼 맨 위 자리를 더 비운다
    var HHl = 13 + 56 * FS + (window.__flowMargin ? 26 * FS : 0), lwl = function (nm, v) { return Math.max(tw(nm, 800, Math.round(22 * FS)), tw(v, 900, Math.round(30 * FS)), window.__flowMargin ? tw('이익률 -00%', 700, Math.round(17 * FS)) : 0) / 2 + 6; };
    var wRl = lwl('총 매출', m(rev)), wLl = lwl('영업손실', m(op)), wEl = lwl('영업비용', m(opex)), lev = 1 + (x2 - x1 < wRl + wLl ? 1 : 0) + (x3 - x2 < wLl + wEl ? 1 : 0);
    var LDOWN = (window.__flowDir || 'down') === 'down';
    function place(s) {
      var g = { s: s, hR: rev * s, hG: Math.max(0, gross) * s, hC: cogs * s, hL: L0 * s, hE: opex * s };
      if (LDOWN) {                                                                             // 내려가는 배치: 총 매출 맨 위 → 매출총이익·영업비용 한 칸씩 아래, 영업손실은 매출총이익 밑에서 영업비용 아래쪽을 채운다
        g.yR = Math.max(top + 40, TOP + 30 + HHl * (hasG && x2 - x1 < wRl + lwl('매출총이익', m(gross)) ? 2 : 1)); g.yG = g.yR + (hasG ? 30 : 0); g.yE = g.yG + 40;   // 이름표가 옆으로 겹치면 한 줄 더 비운다
        g.yL = g.yG + g.hG + HHl + 10; g.yC = g.yL + g.hL + 50;
      } else {
        g.yL = Math.max(top + 40, TOP + 30 + HHl * lev);                                          // 영업손실(모자란 돈) — 맨 위
        g.yG = g.yL + g.hL + 50; g.yR = g.yG; g.yC = g.yG + g.hG + 50; g.yE = g.yL;
      }
      var y = g.yE; g.right = [];
      if (hasItems) {
        var sum = items.reduce(function (a, x) { return a + Math.max(x.v * s, LH); }, 0), slot = Math.min(40, Math.max(8, (bot - y - sum) / items.length));
        items.forEach(function (it) { var h = it.v * s; g.right.push({ n: it.n, v: it.v, y: y + Math.max(0, (LH - h) / 2), h: h }); y += Math.max(h, LH) + slot; });
      }
      g.low = Math.max(g.yR + g.hR, hasG ? g.yC + g.hC + 60 : 0, g.yE + g.hE + 60, y - 10);
      return g;
    }
    var sc = (bot - top) * 0.6 / Math.max(rev, L0 + gross), g = place(sc);
    for (var k = 0; k < 16 && g.low > bot; k++) { sc *= 0.92; g = place(sc); }
    for (k = 0; k < 12 && g.low < bot - 60; k++) { var g2 = place(sc * 1.06); if (g2.low > bot) break; sc *= 1.06; g = g2; }
    var s = g.s;
    if (hasSeg) {
      var nS = segs.length, gapS = Math.max(Math.min(30, (bot - top - g.hR) / (nS + 1)), Math.min((66 * nS - g.hR) / Math.max(1, nS - 1), (bot - top - g.hR) / Math.max(1, nS - 1))), tot = g.hR * (o.segElim ? Math.max(1, segs.reduce(function (a, x) { return a + x.v; }, 0) / rev) : 1) + gapS * (nS - 1), ys = Math.min(Math.max(top, g.yR + g.hR / 2 - tot / 2), bot - tot), cur = g.yR;   // 이름표가 막대 옆에 들어갈 만큼 막대 사이를 띄운다
      var EL = segFlow(X, segs, s, g, x0, x1, nw, ys, gapS, rev, o.segElim);
    }
    if (hasG) { rib(X, x1 + nw, g.yR, g.yR + g.hG, x2, g.yG, g.yG + g.hG, GNS); rib(X, x1 + nw, g.yR + g.hG, g.yR + g.hR, x2, g.yC, g.yC + g.hC, RDS); }
    var gx = hasG ? x2 : x1;
    if (LDOWN) {
      if (g.hG > 0) rib(X, gx + nw, g.yG, g.yG + g.hG, x3, g.yE, g.yE + g.hG, hasG ? GNS : BLS);          // 매출총이익(원가 없으면 매출) → 영업비용 위쪽
      rib(X, x2 + nw, g.yL, g.yL + g.hL, x3, g.yE + g.hG, g.yE + g.hE, DKS);                               // 영업손실 → 영업비용 아래쪽
    } else {
      rib(X, x2 + nw, g.yL, g.yL + g.hL, x3, g.yE, g.yE + g.hL, DKS);                         // 영업손실 → 영업비용 위쪽
      if (g.hG > 0) rib(X, gx + nw, g.yG, g.yG + g.hG, x3, g.yE + g.hL, g.yE + g.hE, hasG ? GNS : BLS);   // 매출총이익(원가 없으면 매출) → 영업비용 아래쪽
    }
    var need = g.right.reduce(function (a, r) { return a + r.h; }, 0), kE = need > 0 ? g.hE / need : 1, ce = g.yE;
    g.right.forEach(function (r) { var h = r.h * kE; rib(X, x3 + nw, ce, ce + h, x4, r.y, r.y + r.h, RDS); ce += h; });
    if (hasSeg) segs.forEach(function (sg) { bar(X, x0, sg.y, nw, Math.max(2, sg.h), BL, sg.v); });
    bar(X, x1, g.yR, nw, g.hR, BL, rev);
    if (hasSeg) elimDraw(X, EL, x1, nw, m, FS);
    if (hasG) { bar(X, x2, g.yG, nw, Math.max(2, g.hG), GN, gross); bar(X, x2, g.yC, nw, Math.max(2, g.hC), RD, cogs); }
    bar(X, x2, g.yL, nw, Math.max(2, g.hL), DK, -op);
    bar(X, x3, g.yE, nw, Math.max(2, g.hE), RD, opex);
    g.right.forEach(function (r) { bar(X, x4, r.y, nw, Math.max(2, r.h), RD, r.v); });
    X.textBaseline = 'alphabetic';
    if (hasSeg) segLabels(X, segs, x0, top, bot, m, FS);
    var MG = !!window.__flowMargin, pc = function (v) { var p = v / rev * 100; return (Math.abs(p) < 1 && p !== 0 ? p.toFixed(1) : Math.round(p)) + '%'; };
    var lboxes = [];
    function above(x, y, name, val, col, sub, more) {
      GID++;
      var w = Math.max(tw(name, 800, Math.round(22 * FS)), tw(val, 900, Math.round(30 * FS)), sub ? tw(sub, 700, Math.round(17 * FS)) : 0) / 2 + 6, hh = 13 + 56 * FS + (sub ? 26 * FS : 0);
      lboxes.forEach(function (bx) { if (x - w < bx[1] && x + w > bx[0] && y - hh < bx[3] && y > bx[2]) y = bx[2] - 4; });   // 옆 이름표와 겹치면 위로
      GID--;
      var d0 = sub ? 26 * FS : 0, ln = (sub ? [[sub, 700, Math.round(17 * FS), SOFT, -12]] : []).concat([[val, 900, Math.round(30 * FS), col, -13 - d0], [name, 800, Math.round(22 * FS), col, -13 - 36 * FS - d0]]);
      var cs = aboveCands(x, y, w);
      if (more) cs = cs.slice(0, 30).concat(more(ln, d0)).concat(cs.slice(30));
      var pk = group(X, ln, cs);
      lboxes.push([pk[0] - w, pk[0] + w, pk[1] - hh, pk[1]]);
    }
    above(x1 + nw / 2, g.yR, '총 매출', m(rev), BL);
    above(x2 + nw / 2, g.yL, '영업손실', m(op), DK, MG ? '이익률 ' + pc(op) : '', function (ln, d0) {   // 영업손실 막대 왼쪽·아래 자리도 본다 (막대 위는 리본이 지나가는 일이 많다)
      var out = [], hL = Math.max(2, g.hL), top0 = 13 + 36 * FS + d0 + 22 * FS;
      [0.5, 0.3, 0.7, 0.15, 0.85].forEach(function (k) { out.push([x2 - 10, g.yL + hL * k + top0 / 2 - 8, 'right']); });
      [0, 20, 40].forEach(function (dy) { out.push([x2 + nw / 2, g.yL + hL + top0 + 10 + dy, 'center']); });
      [0, 16, 32, 52, 76].forEach(function (dy) { out.push([x2 + nw + 10, g.yL + hL + top0 / 2 + dy, 'left']); out.push([x2 - 10, g.yL + hL + top0 / 2 + dy, 'right']); });   // 막대 오른쪽·왼쪽 아래
      return out;
    });
    if (hasG && LDOWN) {                                                     // 내려가는 배치: 매출총이익 이름표는 막대 위, 매출원가는 막대 오른쪽
      above(x2 + nw / 2, g.yG, '매출총이익', m(gross), GN, MG ? '이익률 ' + pc(gross) : '');
      var lnC2 = [['매출원가', 800, Math.round(24 * FS), RD, 0], [m(cogs), 900, Math.round(32 * FS), RD, 36 * FS]], cC2 = [], cy2 = g.yC + Math.min(g.hC, 220) / 2;
      [0, 20, 40, -20, 64, 90].forEach(function (dy) { cC2.push([x2 + nw + 12, cy2 + dy, 'left']); });
      [0, 30].forEach(function (dy) { cC2.push([x2 - 10, cy2 + dy, 'right']); cC2.push([x2 + nw / 2, g.yC + Math.max(2, g.hC) + 30 * FS + dy, 'center']); });
      group(X, lnC2, cC2);
    } else if (hasG) {
      var gw = Math.max(tw('매출총이익', 800, Math.round(22 * FS)), tw(m(gross), 900, Math.round(28 * FS))), gl = gw > x3 - (x2 + nw + 12) - 8 && x2 - 10 - gw > x1 + nw + 8;   // 영업비용 막대까지 자리가 없으면 막대 왼쪽에
      var gxx = gl ? x2 - 10 : x2 + nw + 12, gal = gl ? 'right' : 'left';
      GID++; txt(X, '매출총이익', gxx, g.yG + Math.min(g.hG, 120) / 2 + 4, 800, Math.round(22 * FS), GN, gal); txt(X, m(gross), gxx, g.yG + Math.min(g.hG, 120) / 2 + 4 + 32 * FS, 900, Math.round(28 * FS), GN, gal);
      if (MG) txt(X, '이익률 ' + pc(gross), gxx, g.yG + Math.min(g.hG, 120) / 2 + 4 + 56 * FS, 700, Math.round(17 * FS), SOFT, gal);
      var cyl = g.yC + Math.min(g.hC, 220) / 2;
      if (!gl) cyl = Math.max(cyl, g.yG + Math.min(g.hG, 120) / 2 + 4 + (MG ? 56 : 32) * FS + 10 + 24 * FS);   // 매출총이익 이름표 밑으로
      GID++; txt(X, '매출원가', x2 + nw + 12, cyl, 800, Math.round(24 * FS), RD, 'left'); txt(X, m(cogs), x2 + nw + 12, cyl + 36 * FS, 900, Math.round(32 * FS), RD, 'left');
    }
    above(x3 + nw / 2, g.yE, '영업비용', m(opex), RD);
    var rx = x4 + nw + 10, mw = R - rx, lastR = -1e9;
    // 오른쪽 이름표 — 위에서부터 쌓고, 바닥(데드존)을 넘으면 아래에서부터 다시 밀어 올린다
    var ys = g.right.map(function (r) { var y0 = Math.max(r.y + r.h / 2 - 27 * FS, lastR + 4); lastR = y0 + 54 * FS; return y0; });
    for (var k = ys.length - 1, lim = BOT + 6 - 54 * FS; k >= 0; k--) { if (ys[k] > lim) ys[k] = lim; lim = ys[k] - 4 - 54 * FS; }
    lastR = ys.length ? ys[ys.length - 1] + 54 * FS : lastR;
    g.right.forEach(function (r, k) { GID++; var y0 = ys[k]; txt(X, r.n, rx, y0 + 18.6 * FS, 700, Math.round(19 * FS), RD, 'left', mw); txt(X, m(r.v), rx, y0 + 46.6 * FS, 900, Math.round(26 * FS), RD, 'left', mw); });
    if (false) { GID++; txt(X, '영업비용', x3 + nw + 12, g.yE + Math.min(g.hE, 200) / 2, 800, Math.round(23 * FS), RD, 'left'); }
    // 순이익(손실)은 숫자로만 — 영업이익이 없어 흐름으로 이어 그릴 곳이 없다
    // 순이익(손실) 글 — 오른쪽 막대들 아래에 자리가 있으면 거기, 없으면 막대 왼쪽에
    var rb = Math.max.apply(null, g.right.map(function (r) { return r.y + Math.max(2, r.h); }).concat([lastR, g.low])), nx = R, ny = rb + 34 * FS;
    if (ny > BOT + 12) { nx = x4 - 12; ny = Math.max(g.low + 20, bot - 40); ny = Math.min(bot - 4, ny); }
    if (ni != null) {                                                    // 리본·다른 글자를 피해 자리 고르기
      var lnN = [[(ni >= 0 ? '순이익 ' : '순손실 ') + m(ni), 900, Math.round(26 * FS), ni >= 0 ? GN : DK, 0]].concat(MG ? [['이익률 ' + pc(ni), 700, Math.round(17 * FS), SOFT, -32 * FS]] : []), cN = [];
      [0, 16, 32, -16, -32, 48].forEach(function (dy) { cN.push([nx, ny + dy, 'right']); });
      [0, 20, 40].forEach(function (dy) { cN.push([R, BOT + 4 - dy, 'right']); cN.push([x4 - 12, Math.min(bot - 4, Math.max(g.low + 20, bot - 40)) - dy, 'right']); cN.push([x3 + nw / 2, g.yE + Math.max(2, g.hE) + 40 * FS + dy, 'center']); });
      group(X, lnN, cN);
    }
    if (!o.__dry) window.__vcFoot(X, o.src);
  }
  /* 글자 크기 고르기 — 큰 글자부터 시험 삼아 그려 보고(글자 상자만 잼), 겹침·데드존 넘침이 없는 가장 큰 크기로 그린다 */
  var trialCv = null;
  function sankey3(X, o) {
    if (!trialCv) { trialCv = document.createElement('canvas'); trialCv.width = 1080; trialCv.height = 1350; }
    var TX = trialCv.getContext('2d'), best = null, dbg = window.__sankeyDbg, why = window.__fsWhy = [];
    window.__sankeyDbg = null;
    var TRY = [];
    // 큰 글자 + 막대 바로 위 → 큰 글자 + 조금 넓게 → 작은 글자 + 막대 바로 위 → 작은 글자 + 조금 넓게
    [[1.34, 1.26, 1.18, 1.1], [1.02, 0.94, 0.88]].forEach(function (fl) { [false, true].forEach(function (wd) { fl.forEach(function (fs) { TRY.push([fs, wd]); }); }); });
    TRY.some(function (tr) {
      var fs = tr[0]; WIDE = tr[1]; var fsT = fs + (WIDE ? 'w' : '');
      REC = []; o.__FS = fs; o.__dry = true;
      try { sankey3c(TX, o); } catch (e) { REC = null; o.__dry = false; window.__sankeyDbg = dbg; throw e; }
      var b = REC, bad = 0, P = 6;    // 글자끼리·글자와 막대는 6px 넘게 떨어져야 한다
      if (o.__span && o.__span < 118) { bad += 2; why.push(fsT + ' 좁은 기둥 ' + Math.round(o.__span)); }
      if (o.__hR != null && o.__hR < 200) { bad += 2; why.push(fsT + ' 그래프가 너무 작음 ' + Math.round(o.__hR)); }   // 글자를 키우느라 막대가 쪼그라들면 안 된다   // 글자를 키우느라 그래프가 너무 좁아지면 안 된다
      b.forEach(function (a, i) {
        if (a.rib) return;
        if (a.bar) { if (a.y1 > BOT + 4 || a.y0 < TOP + 20) { bad += 3; why.push(fsT + ' 막대 넘침'); } return; }
        for (var q = 0; q < b.length; q++) if (b[q].rib && ribHit(b[q], a, 2)) { bad++; why.push(fsT + ' RIB ' + a.t); break; }   // 글자가 리본 위에 올라가면 안 된다
        if (a.x0 < L - 4 || a.x1 > R + 4 || a.y0 < TOP + 24 || a.y1 > BOT + 22) { bad++; why.push(fsT + ' OUT ' + a.t); }
        for (var j = 0; j < b.length; j++) {
          var c = b[j]; if (j === i || c.rib || (!c.bar && j < i)) continue;
          var p = c.bar ? 3 : c.g === a.g ? 1 : P; if (Math.min(a.x1, c.x1) - Math.max(a.x0, c.x0) > -p && Math.min(a.y1, c.y1) - Math.max(a.y0, c.y0) > -p) { bad++; why.push(fsT + ' OVL ' + a.t + [a.x0, a.y0, a.x1, a.y1].map(Math.round) + '×' + (c.bar ? '막대' + [c.x0, c.y0, c.x1, c.y1].map(Math.round) : c.t)); }
        }
      });
      if (!best || bad < best.bad) best = { fs: fs, bad: bad, wide: WIDE };
      return bad === 0;
    });
    REC = null; o.__dry = false; o.__FS = best.fs; WIDE = best.wide; window.__sankeyDbg = dbg;
    if (window.__sankeyDbg) window.__sankeyDbg.fs = best.fs + (best.wide ? 'w' : '');
    sankey3c(X, o); WIDE = false;
  }
  function sankey3c(X, o) {
    RB = []; BB = []; TB = [];
    if (window.__sankeyDbg) { window.__sankeyDbg.ribs = []; window.__sankeyDbg.bars = []; window.__sankeyDbg.o = o; }
    if (!o.__dry) { base.grainOnly(X); X.fillStyle = INK; window.__vcTitle(X, o.h1, o.logo, { tail: /[은는]$/ }); }
    if (o.op <= 0) { sankeyLoss(X, o); return; }
    var m = o.money, rev = o.rev, cogs = Math.max(0, o.cogs || 0), gross = rev - cogs, op = o.op, opex = gross - op, ni = o.ni, tax = Math.max(0, o.tax || 0);
    var nonop = op - tax - ni, exIn = nonop < -rev * 0.002 ? -nonop : 0, exOut = nonop > rev * 0.002 ? nonop : 0;   // 영업외 손익은 작아도 그린다 — 안 그리면 막대 높이가 안 맞아 리본이 끊긴다
    var segs = (o.segs || []).filter(function (x) { return x.v > rev * 0.002; }), items = (o.items || []).filter(function (x) { return x.v > rev * 0.002; });
    var hasSeg = segs.length >= 2, hasG = cogs > rev * 0.005, hasItems = items.length >= 2;
    // 범례 · 로고
    var lx = L, ly = TOP + 2;
    [['매출', BL], ['이익', GN], ['비용', RD]].forEach(function (k) { X.fillStyle = k[1]; X.fillRect(lx, ly - 4, 30, 6); X.fillStyle = SOFT; X.font = font(700, 20); X.textAlign = 'left'; X.fillText(k[0], lx + 38, ly + 4); lx += 104; });
    if (o.fxNote) { X.fillStyle = SOFT; X.font = font(700, 20); X.textAlign = 'right'; X.fillText(o.fxNote, R, ly + 4); }   // 해외 회사: 원화로 바꾼 환율
    // 글자를 키우고(×1.18), 양옆 이름표 폭을 실제 글자 길이로 재서 그래프를 데드존(L·R) 끝까지 넓힌다
    var FS = o.__FS || 1.18;
    function tw(s, w, px) { X.font = font(w, px); return X.measureText(s).width; }
    var segW = hasSeg ? Math.min(230, Math.max.apply(null, segs.map(function (sg) { return Math.max(tw(sg.n, 700, 21 * FS), tw(m(sg.v), 900, 26 * FS)); }))) : 0;
    var rNames = [ni >= 0 ? '순이익' : '순손실', m(ni)].concat(tax > 0 ? ['법인세', m(tax)] : []).concat(exOut > 0 ? ['영업외 손실', m(exOut)] : [])
      .concat(hasItems ? items.reduce(function (a, it) { return a.concat([it.n, m(it.v)]); }, []) : []);
    var rightW = Math.min(210, Math.max(96, Math.max.apply(null, rNames.map(function (s2, ix) { return tw(s2, ix % 2 ? 900 : 700, (ix % 2 ? 26 : 19) * FS); }))));
    var nw = 20, x0 = hasSeg ? L + segW + 14 : L, x1 = hasSeg ? x0 + 150 : L + Math.max(40, tw(m(rev), 900, 30 * FS) / 2 + 4), x4 = R - rightW - nw - 12, x2 = x1 + (x4 - x1) * 0.33, x3 = hasG ? x1 + (x4 - x1) * 0.66 : x1 + (x4 - x1) * 0.45, xm = (window.__flowDir || 'down') === 'down' ? Math.max((x3 + x4) / 2, x4 - nw - 46) : (x3 + x4) / 2;   // 내려가는 배치: 영업외 이익 막대를 순이익 막대 바로 옆에 — 영업이익→순이익 흐름 위에 놓이지 않게
    o.__span = hasG ? Math.min(x2 - x1, x3 - x2, x4 - x3) : Math.min(x3 - x1, x4 - x3);
    var top = TOP + 60, bot = BOT - 8, HH = 13 + 56 * FS + (window.__flowMargin ? 26 * FS : 0);   // 위 이름표 높이
    // 기둥 사이가 좁아 위 이름표끼리 옆으로 겹치면 계단을 이름표 높이만큼 벌린다
    var lw = function (nm, v) { return Math.max(tw(nm, 800, Math.round(22 * FS)), tw(v, 900, Math.round(30 * FS)), window.__flowMargin ? tw('이익률 00%', 700, Math.round(17 * FS)) : 0) / 2 + 8; };
    var wR = lw('총 매출', m(rev)), wG = lw('매출총이익', m(gross)), wO = lw('영업이익', m(op));
    var stGO = hasG ? (x3 - x2 < wG + wO ? HH + 6 : 40) : 40, stGR = hasG ? (x2 - x1 < wR + wG ? HH + 6 : 40) : (x3 - x1 < wR + wO ? HH + 6 : 40);
    // 자리 잡기 — 맨 아래가 바닥을 넘으면 배율을 줄여 다시
    function place(s) {
      var g = { s: s };
      g.hR = rev * s; g.hG = gross * s; g.hC = cogs * s; g.hO = Math.max(0, op) * s; g.hE = opex * s; g.hEx = exIn * s; g.hN = Math.max(0, ni) * s;
      var DIR = window.__flowDir || 'down', base = Math.max(top + 70, TOP + 34 + HH), exRoom = exIn ? g.hEx + Math.max(110, HH + 10) : 0;
      if (DIR === 'down') {                                                    // 총 매출이 맨 위 → 오른쪽으로 갈수록 한 칸씩 내려간다
        g.yR = base; g.yG = g.yR + stGR; g.yO = g.yG + stGO;
      } else if (DIR === 'flat') {                                             // 윗선을 한 줄로 맞춘다
        g.yR = g.yG = g.yO = base + exRoom;
      } else {
        g.yO = base + exRoom;                                                  // 영업이익: 위 (영업외 이익이 있으면 그 아래)
        g.yG = g.yO + stGO; g.yR = g.yG + stGR;                                // 매출총이익·총 매출은 한 칸씩 아래 (계단)
      }
      g.yC = g.yG + g.hG + 50; g.yE = g.yO + g.hO + 50;
      g.yX = g.yO - g.hEx - Math.max(110, HH + 10); g.yN = Math.max(top + 10, (exIn ? g.yX : g.yO) - 10);
      if (DIR === 'down') { g.yN = base; g.yX = base; }      // 내려가는 배치: 순이익은 맨 위, 영업외 이익은 순이익 윗부분과 같은 높이 — 법인세로 가는 흐름과 엇갈리지 않게
      var LH = Math.max(62, 54 * FS);                                                          // 오른쪽 이름표 한 칸 높이 — 막대가 얇아도 이름표가 막대 옆에 오도록
      var y = g.yN + Math.max(g.hN, 62) + 14; g.right = [];
      if (tax > 0) { g.right.push({ n: '법인세', v: tax, y: y + Math.max(0, (LH - tax * s) / 2), h: tax * s, from: 'op' }); y += Math.max(tax * s, LH) + 10; }
      if (exOut > 0) { g.right.push({ n: '영업외 손실', v: exOut, y: y + Math.max(0, (LH - exOut * s) / 2), h: exOut * s, from: 'op' }); y += Math.max(exOut * s, LH) + 10; }
      if (hasItems) {
        y = Math.max(y + 10, g.yE - 30);
        var sum = items.reduce(function (t, x) { return t + Math.max(x.v * s, LH); }, 0), slot = Math.min(40, Math.max(8, (bot - y - sum) / items.length));
        items.forEach(function (it) { var h = it.v * s; g.right.push({ n: it.n, v: it.v, y: y + Math.max(0, (LH - h) / 2), h: h, from: 'ex' }); y += Math.max(h, LH) + slot; });
      }
      g.low = Math.max(g.yR + g.hR, hasG ? g.yC + g.hC + 60 : 0, g.yE + g.hE + 50, y - 10);
      return g;
    }
    function fit() {
      var sc = (bot - top) * 0.7 / Math.max(rev, gross + exIn), g = place(sc);
      for (var k = 0; k < 40 && g.low > bot; k++) { sc *= 0.92; g = place(sc); }
      for (k = 0; k < 12 && g.low < bot - 60; k++) { var g2 = place(sc * 1.06); if (g2.low > bot) break; sc *= 1.06; g = g2; }   // 남는 아래 공간은 키워서 채운다
      return g;
    }
    var EXPUSH = true, g = fit();
    o.__hR = null;
    if (exIn) { EXPUSH = false; var gNo = fit(); if (g.s < gNo.s * 0.8) g = gNo; else { EXPUSH = true; g = fit(); } }   // 영업외 이익 자리 때문에 그래프가 20% 넘게 작아지면 그 자리 비우기를 포기
    var s = g.s; o.__hR = g.hR;
    // ---- 리본
    if (hasSeg) {
      var nS = segs.length, gapS = Math.max(Math.min(30, (bot - top - g.hR) / (nS + 1)), Math.min((66 * nS - g.hR) / Math.max(1, nS - 1), (bot - top - g.hR) / Math.max(1, nS - 1))), tot = g.hR * (o.segElim ? Math.max(1, segs.reduce(function (a, x) { return a + x.v; }, 0) / rev) : 1) + gapS * (nS - 1), ys = Math.min(Math.max(top, g.yR + g.hR / 2 - tot / 2), bot - tot), cur = g.yR;   // 이름표가 막대 옆에 들어갈 만큼 막대 사이를 띄운다
      var EL = segFlow(X, segs, s, g, x0, x1, nw, ys, gapS, rev, o.segElim);
    }
    var sx = hasG ? x2 : x1, sy = hasG ? g.yG : g.yR;
    if (hasG) { rib(X, x1 + nw, g.yR, g.yR + g.hG, x2, g.yG, g.yG + g.hG, GNS); rib(X, x1 + nw, g.yR + g.hG, g.yR + g.hR, x2, g.yC, g.yC + g.hC, RDS); }
    rib(X, sx + nw, sy, sy + g.hO, x3, g.yO, g.yO + g.hO, GNS);
    rib(X, sx + nw, sy + g.hO, sy + g.hO + g.hE, x3, g.yE, g.yE + g.hE, RDS);
    /* 이익 쪽 나눠 주기 — 들어오는 곳: 영업외 이익(위) · 영업이익. 나가는 곳: 순이익 · 법인세 · 영업외 손실 (위에서부터).
       순서대로 채워서 막대마다 들어오고 나가는 양이 꼭 맞게 한다 (세금이 영업이익보다 큰 지주회사도). */
    var pools = [], outs = [{ y: g.yN, h: g.hN, c: GNS }];
    if (exIn) pools.push({ x: xm + nw, y: g.yX, h: g.hEx });
    if (g.hO > 0) pools.push({ x: x3 + nw, y: g.yO, h: g.hO });
    g.right.forEach(function (r) { if (r.from === 'op') outs.push({ y: r.y, h: r.h, c: RDS }); });
    var supply = pools.reduce(function (a, p) { return a + p.h; }, 0), demand = outs.reduce(function (a, o) { return a + o.h; }, 0);
    var kD = demand > 0 && supply > 0 ? supply / demand : 1;            // 반올림·적자로 어긋나면 나가는 쪽을 비율로 맞춘다
    var pi = 0, pu = 0;
    outs.forEach(function (o) {
      var need = o.h * kD, yo = o.y, oh = o.h;
      while (need > 0.2 && pi < pools.length) {
        var p = pools[pi], h = Math.min(need, p.h - pu);
        if (h > 0.2) rib(X, p.x, p.y + pu, p.y + pu + h, x4, yo, yo + h / kD, o.c);
        need -= h; pu += h; yo += h / kD;
        if (p.h - pu < 0.2) { pi++; pu = 0; }
      }
    });
    var ce = g.yE;
    var needE = g.right.reduce(function (t, r) { return t + (r.from === 'ex' ? r.h : 0); }, 0), kE = needE > 0 ? g.hE / needE : 1;
    g.right.forEach(function (r) {
      if (r.from === 'ex') { var h2 = r.h * kE; rib(X, x3 + nw, ce, ce + h2, x4, r.y, r.y + r.h, RDS); ce += h2; }
    });
    // ---- 막대
    if (hasSeg) segs.forEach(function (sg) { bar(X, x0, sg.y, nw, Math.max(2, sg.h), BL, sg.v); });
    bar(X, x1, g.yR, nw, g.hR, BL, rev);
    if (hasSeg) elimDraw(X, EL, x1, nw, m, FS);
    if (hasG) { bar(X, x2, g.yG, nw, g.hG, GN, gross); bar(X, x2, g.yC, nw, Math.max(2, g.hC), RD, cogs); }
    bar(X, x3, g.yO, nw, Math.max(2, g.hO), GN, op); bar(X, x3, g.yE, nw, Math.max(2, g.hE), RD, opex);
    if (exIn) bar(X, xm, g.yX, nw, Math.max(2, g.hEx), GN, exIn);
    if (g.hN > 0) bar(X, x4, g.yN, nw, g.hN, GN, ni);
    g.right.forEach(function (r) { bar(X, x4, r.y, nw, Math.max(2, r.h), RD, r.v); });
    // ---- 이름표
    X.textBaseline = 'alphabetic';
    var pc = function (v) { var p = v / rev * 100; return (Math.abs(p) < 1 && p !== 0 ? p.toFixed(1) : Math.round(p)) + '%'; };
    if (hasSeg) {
      var lastY = -1e9;
      segLabels(X, segs, x0, top, bot, m, FS);
    }
    var MG = !!window.__flowMargin, mg = function (lab, v) { return MG ? lab + ' ' + pc(v) : ''; };
    var boxes = [];
    function above(x, y, name, val, sub, col, xr, xl) {
      GID++;
      // 옆 기둥 이름표와 겹치면 위로 올린다 (기둥 사이가 좁은 회사)
      var w = Math.max(tw(name, 800, Math.round(22 * FS)), tw(val, 900, Math.round(30 * FS)), sub ? tw(sub, 700, Math.round(17 * FS)) : 0) / 2 + 6;
      var x00 = x, y00 = y;
      if (xr && x + w > xr) x = xr - w;            // 오른쪽 기둥(더 높이 솟은 막대)에 닿지 않게 왼쪽으로
      if (xl && x - w < xl) x = xl + w;
      var hh = 13 + 56 * FS + (sub ? 26 * FS : 0);
      boxes.forEach(function (bx) { if (x - w < bx[1] && x + w > bx[0] && y - hh < bx[3] && y > bx[2]) y = bx[2] - 4; });
      GID--;
      var d0 = sub ? 26 * FS : 0, ln = (sub ? [[sub, 700, Math.round(17 * FS), SOFT, -12]] : []).concat([[val, 900, Math.round(30 * FS), col, -13 - d0], [name, 800, Math.round(22 * FS), col, -13 - 36 * FS - d0]]);
      var pk = group(X, ln, aboveCands(x, y, w, xl, xr).concat(y !== y00 ? aboveCands(x00, y00, w) : []));
      boxes.push([pk[0] - w, pk[0] + w, pk[1] - hh, pk[1]]);
    }
    above(x1 + nw / 2, g.yR, '총 매출', m(rev), '', BL, (hasG ? x2 : x3) - 4, hasSeg ? x0 + nw + 4 : 0);
    if (hasG) {
      above(x2 + nw / 2, g.yG, '매출총이익', m(gross), mg('이익률', gross), GN, x3 - 4, x1 + nw + 4);
    }
    above(x3 + nw / 2, g.yO, '영업이익', m(op), mg('이익률', op), GN, exIn ? 0 : x4 - 4, (hasG ? x2 : x1) + nw + 4);
    var ey = g.yE + Math.min(g.hE, 180) / 2 + 2, ew = Math.max(tw('영업비용', 800, Math.round(23 * FS)), tw(m(opex), 900, Math.round(30 * FS))), ex = x3 - 10, ea = 'right';
    if (ew > x3 - 10 - (x2 + nw) - 12) { ex = x3 + nw / 2; ea = 'center'; ey = g.yE + g.hE + 26 * FS; }   // 기둥 사이가 좁으면 영업비용 막대 아래로
    var lnE = [['영업비용', 800, Math.round(23 * FS), RD, 0], [m(opex), 900, Math.round(30 * FS), RD, 32 * FS]], cE = [];
    [0, 16, -16, 32, -32, 50, -50, 72, -72, 96, 120].forEach(function (dy) { cE.push([ex, ey + dy, ea]); });
    [0, 20, 44, 70].forEach(function (dy) { [0, 0.5, -0.5, 1].forEach(function (k) { cE.push([x3 + nw / 2 + k * ew / 2, g.yE + g.hE + 26 * FS + dy, 'center']); }); });   // 영업비용 막대 바로 아래
    group(X, lnE, cE);
    if (hasG) {   // 매출원가 이름표 — 영업비용 이름표와 부딪히면 그 아래로
      var cy = g.yC + Math.min(g.hC, 220) / 2, cw = Math.max(tw('매출원가', 800, Math.round(24 * FS)), tw(m(cogs), 900, Math.round(32 * FS)));
      var down = (window.__flowDir || 'down') === 'down', cx = x2 + nw + 12, ca = 'left';
      cy = Math.max(cy, g.yG + 30 * FS);                                  // 매출총이익 이름표(막대 위)와 겹치지 않게
      if (down && x2 - 10 - cw > x1 + nw + 8) { cx = x2 - 10; ca = 'right'; cy = Math.max(cy, g.yR + g.hR + 24 * FS + 8); }   // 내려가는 배치: 매출원가 막대 왼쪽(총 매출 막대 아래)에
      else if (down) { cx = x2 + nw / 2; ca = 'center'; cy = g.yC + Math.max(2, g.hC) + 30 * FS; }                    // 왼쪽 자리가 없으면 매출원가 막대 바로 아래
      else if (x2 + nw + 12 + cw > (ea === 'right' ? x3 - 10 - ew : x3 + nw / 2 - ew / 2) && cy < ey + 32 * FS + 40 * FS && cy + 36 * FS > ey - 24 * FS) cy = ey + 32 * FS + 34 * FS;
      var lnC = [['매출원가', 800, Math.round(24 * FS), RD, 0], [m(cogs), 900, Math.round(32 * FS), RD, 36 * FS]], cC = [];
      [0, 20, 40, 64, 90, 120, -20].forEach(function (dy) { cC.push([cx, cy + dy, ca]); });
      [0, 20, 44].forEach(function (dy) { [0, -0.5, 0.5].forEach(function (k) { cC.push([x2 + nw / 2 + k * cw / 2, g.yC + Math.max(2, g.hC) + 30 * FS + dy, 'center']); }); });   // 매출원가 막대 바로 아래
      [0, 30, 60].forEach(function (dy) { cC.push([x2 - 10, Math.max(cy, g.yR + g.hR + 24 * FS + 8) + dy, 'right']); });
      group(X, lnC, cC);
    }
    var rx = x4 + nw + 10, mw = R - rx, lastR = -1e9;
    var rl = [{ n: ni >= 0 ? '순이익' : '순손실', v: m(ni), sub: mg('이익률', ni), y: g.yN + Math.min(g.hN, 120) / 2, c: ni >= 0 ? GN : RD }].concat(g.right.map(function (r) { return { n: r.n, v: m(r.v), y: r.y + r.h / 2, c: RD }; }));
    // 위에서부터 쌓고, 바닥(데드존)을 넘으면 아래에서부터 밀어 올린다
    var ry = rl.map(function (t) { var h = (t.sub ? 80 : 54) * FS, y0 = Math.max(t.y - h / 2, lastR + 4); lastR = y0 + h; return y0; });
    for (var k2 = rl.length - 1, lim2 = BOT + 6; k2 >= 0; k2--) { var hh2 = (rl[k2].sub ? 80 : 54) * FS; if (ry[k2] + hh2 > lim2) ry[k2] = lim2 - hh2; lim2 = ry[k2] - 4; }
    rl.forEach(function (t, k) {
      GID++;
      var y0 = ry[k];
      txt(X, t.n, rx, y0 + 18.6 * FS, 700, Math.round(19 * FS), t.c, 'left', mw); txt(X, t.v, rx, y0 + 46.6 * FS, 900, Math.round(26 * FS), t.c, 'left', mw);
      if (t.sub) txt(X, t.sub, rx, y0 + 73 * FS, 700, Math.round(16 * FS), SOFT, 'left', mw);
    });
    // 영업외 이익 이름표는 오른쪽 이름표까지 다 놓은 뒤에 — 그래야 그 글자들도 피한다
    if (exIn) { var wx = Math.max(tw('영업외 이익', 800, Math.round(22 * FS)), tw('+' + m(exIn), 900, Math.round(30 * FS))) / 2;   // 순이익 막대에 닿지 않게 왼쪽으로
      if ((window.__flowDir || 'down') === 'down') {     // 내려가는 배치: 늘 막대 위 (맨 위라 순이익 막대와 안 닿는다) — 글자는 오른쪽 항목들과 같은 크기
        var wx2 = Math.max(tw('영업외 이익', 700, Math.round(19 * FS)), tw('+' + m(exIn), 900, Math.round(26 * FS))) / 2, ex2 = Math.min(xm + nw / 2, x4 + nw - wx2);
        var eyb = g.yX - 14, eyt = eyb - 28 * FS - 19 * FS;
        var hitE = function (cx) { return boxes.some(function (bx) { return cx - wx2 - 8 < bx[1] && cx + wx2 + 8 > bx[0] && eyt - 6 < bx[3] && eyb + 6 > bx[2]; }); };   // 6~8px 띄움
        if (hitE(ex2)) { if (!hitE(x4 + nw - wx2)) ex2 = x4 + nw - wx2; else if (!hitE(R - wx2) && eyb + 8 < g.yN + Math.min(g.hN, 120) / 2 - (MG ? 80 : 54) * FS / 2) ex2 = R - wx2; else eyb = g.yX + Math.max(2, g.hEx) + 52 * FS; }   // 순이익 막대 끝 → 오른쪽 끝(순이익 글자보다 위)까지 밀어 본다   // 부딪히면 오른쪽(순이익 막대 끝)까지 밀고, 그래도 안 되면 막대 아래로
        if (window.__sankeyDbg) window.__sankeyDbg.ex = { mode: eyb > g.yX ? 'below' : 'above', yX: g.yX, yN: g.yN, h: g.hEx };
        var lnX = [['+' + m(exIn), 900, Math.round(26 * FS), GN, 0], ['영업외 이익', 700, Math.round(19 * FS), GN, -28 * FS]], cX = [];
        [0, -12, -26, -42].forEach(function (dy) { [ex2, x4 + nw - wx2, R - wx2, ex2 - wx2 * 0.5].forEach(function (xx) { cX.push([xx, eyb + dy, 'center']); }); });
        [0, 20].forEach(function (dy) { cX.push([ex2, g.yX + Math.max(2, g.hEx) + 52 * FS + dy, 'center']); });
        group(X, lnX, cX);
      }
      else if (x4 - 8 - (x3 + nw + 6) >= 2 * wx) above(Math.max(x3 + nw + 6 + wx, Math.min(xm + nw / 2, x4 - 8 - wx)), g.yX, '영업외 이익', '+' + m(exIn), '', GN);
      else if ((window.__flowDir || 'down') === 'down') {   // 내려가는 배치: 자리가 좁으면 막대 바로 아래 (순이익 막대에 닿지 않게 왼쪽으로)
        var bx = Math.min(xm + nw / 2, x4 - 8 - wx), by = g.yX + Math.max(2, g.hEx) + 24 * FS + 4;
        GID++; txt(X, '영업외 이익', bx, by, 800, Math.round(22 * FS), GN, 'center'); txt(X, '+' + m(exIn), bx, by + 32 * FS, 900, Math.round(30 * FS), GN, 'center');
      } else {   // 자리가 좁으면 막대 왼쪽에 (영업이익 이름표보다 위)
        var vb = g.yX + Math.max(g.hEx, 0) + 2 - 6;
        GID++; txt(X, '+' + m(exIn), xm - 8, vb, 900, Math.round(30 * FS), GN, 'right'); txt(X, '영업외 이익', xm - 8, vb - 32 * FS, 800, Math.round(22 * FS), GN, 'right');
      } }
    if (!o.__dry) window.__vcFoot(X, o.src);
  }
  base.sankey3 = sankey3;
})();
