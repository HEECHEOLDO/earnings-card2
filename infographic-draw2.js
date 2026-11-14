/* 인포그래픽 2차 — 부호 있는 막대 · 돈의 흐름(생키) · 100% 막대 · 수익률 퀼트 · 성장 곡선 · 와플 · 맞수 비교
   window.__vc 에 덧붙인다 (infographic-draw.js 다음에 읽는다). 색은 밝은 모드 기준으로 쓰고, 어두운 모드는 card-theme.js 가 바꾼다. */
(function () {
  var CW = 1080, CH = 1350, L = 70, R = 1010;
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
    while (px > 44 && X.measureText(o.h1).width > R - L) { px -= 2; X.font = font(900, px); }
    X.fillText(o.h1, L, 186);
    if (o.h2) { X.fillStyle = T.soft; X.font = font(600, 30); X.fillText(o.h2, L, 236); }
  }
  function foot(X, src) {
    X.strokeStyle = T.rule; X.lineWidth = 2; X.beginPath(); X.moveTo(L, 1286); X.lineTo(R, 1286); X.stroke();
    X.fillStyle = '#3A3E46'; X.textAlign = 'left'; X.textBaseline = 'alphabetic'; X.font = font(700, 22); X.fillText(src, L, 1320);
    X.textAlign = 'right'; X.font = font(800, 24); X.fillText('@돈굴돈굴', R, 1320);
  }
  function fit(X, s, w) { if (X.measureText(s).width <= w) return s; while (s.length > 1 && X.measureText(s + '…').width > w) s = s.slice(0, -1); return s + '…'; }

  /* 1) 부호 있는 막대 — 행: {n, sub, v, lab, logo, c} · 음수가 있으면 가운데 0 축 */
  function bars(X, o) {
    head(X, o);
    var rows = o.rows, n = rows.length, top = o.top || 280, avail = (o.bottom || 1240) - top, rowH = Math.min(n <= 8 ? 120 : 78, avail / n);
    var neg = rows.some(function (r) { return r.v < 0; }), pos = rows.some(function (r) { return r.v > 0; });
    var mx = Math.max.apply(null, rows.map(function (r) { return Math.abs(r.v); })) || 1;
    var x0 = L + 340, bw = R - 120 - x0, zero = neg && pos ? x0 + bw * 0.35 : neg ? R - 120 : x0;
    var span = neg && pos ? bw * 0.65 : bw, nspan = neg && pos ? bw * 0.35 - 10 : bw;
    if (neg && pos) { var mp = Math.max.apply(null, rows.map(function (r) { return r.v; })), mn = -Math.min.apply(null, rows.map(function (r) { return r.v; })); var f = mp / (mp + mn); zero = x0 + 90 + (bw - 90) * (1 - f) * 0.85; span = R - 120 - zero; nspan = zero - x0 - 90; mx = Math.max(mp, 1e-9); var mxn = Math.max(mn, 1e-9); }
    rows.forEach(function (r, i) {
      var y = top + i * rowH, cy = y + rowH / 2, big = rowH >= 66;
      X.fillStyle = T.soft; X.font = font(800, 22); X.textAlign = 'right'; X.textBaseline = 'middle'; X.fillText(i + 1, L + 26, cy);
      logoAt(X, r.logo, L + 62, cy, big ? 24 : 21);
      X.textAlign = 'left'; X.fillStyle = T.ink; X.font = font(800, big ? 27 : 25);
      X.fillText(fit(X, r.n, x0 - L - 110), L + 96, r.sub ? cy - 10 : cy);
      if (r.sub) { X.fillStyle = T.soft; X.font = font(600, 18); X.fillText(fit(X, r.sub, x0 - L - 110 + (neg ? 0 : 0)), L + 96, cy + 17); }
      var w = r.v >= 0 ? span * r.v / mx : nspan * (-r.v) / (mxn || mx), bh = Math.min(36, rowH * 0.56);
      X.fillStyle = r.c || (r.v >= 0 ? T.up : T.down);
      if (r.v >= 0) rr(X, zero, cy - bh / 2, Math.max(w, 3), bh, 6); else rr(X, zero - w, cy - bh / 2, Math.max(w, 3), bh, 6);
      X.fill();
      X.fillStyle = T.ink; X.font = font(900, big ? 27 : 25);
      if (r.v >= 0) { X.textAlign = 'left'; X.fillText(r.lab, zero + w + 10, cy + 1); }
      else { X.textAlign = 'right'; X.fillText(r.lab, zero - w - 10, cy + 1); }
      X.strokeStyle = T.rule; X.lineWidth = 1; X.beginPath(); X.moveTo(L, y + rowH); X.lineTo(R, y + rowH); X.stroke();
    });
    if (neg && pos) { X.strokeStyle = T.soft; X.lineWidth = 2; X.beginPath(); X.moveTo(zero, top - 6); X.lineTo(zero, top + n * rowH + 6); X.stroke(); }
    X.textBaseline = 'alphabetic';
    if (o.legend) {
      var lx = L, ly = top + n * rowH + 44;
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
    X.fillStyle = col; X.beginPath(); X.moveTo(xa, ya0); X.bezierCurveTo(m, ya0, m, yb0, xb, yb0); X.lineTo(xb, yb1); X.bezierCurveTo(m, yb1, m, ya1, xa, ya1); X.closePath(); X.fill();
  }
  function sankey(X, o) {
    head(X, o);
    var GREEN = '#2E9E6B', RED = '#D9677B', GR = '#5D636D', GS = 'rgba(46,158,107,0.30)', RS = 'rgba(217,103,123,0.28)', NS = 'rgba(93,99,109,0.22)';
    var rev = o.rev, op = Math.max(o.op, 0), ni = o.ni, cost = rev - op, extra = Math.max(ni - op, 0), tax = Math.max(op - Math.max(ni, 0), 0), nip = Math.max(ni, 0);
    var top = 330, H = 760, s = H / Math.max(rev, op + extra) * 0.86, gap = 46, nw = 30;
    var xA = L + 150, xB = 520, xC = 830;
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
    lab(xB + nw + 14, yOp + Math.max(hOp, 0) / 2 - 20 - (hOp < 90 ? 30 : 0), 'left', o.op >= 0 ? '영업이익' : '영업손실', o.money(o.op), '매출의 ' + o.pct(o.op), GREEN);
    lab(xB + nw + 14, yCost + Math.min(hCost / 2, 150) - 20, 'left', '영업비용', o.money(cost), '원가·판관비', RED);
    if (nip > 0) lab(xC + nw + 14, yNi + Math.min(hNi / 2, 120) - 20 - (hNi < 90 ? 20 : 0), 'left', '순이익', o.money(ni), '매출의 ' + o.pct(ni), GREEN);
    else lab(xC + nw + 14, yNi + 20, 'left', '순손실', o.money(ni), '', T.down);
    if (hTax > 0.5) lab(xC + nw + 14, yTax + Math.min(hTax / 2, 60) - 10 + (hTax < 60 ? 10 : 0), 'left', '세금·영업외', o.money(-tax), '', T.soft);
    if (extra > 0) { X.textAlign = 'right'; X.fillStyle = GREEN; X.font = font(800, 20); X.fillText('영업외 이익 +' + o.money(extra), xB - 10, yEx + hEx / 2 + 7); }
    // 100원으로 다시 말하기
    var y100 = 1200;
    X.textAlign = 'left'; X.fillStyle = T.ink; X.font = font(800, 28);
    X.fillText('100원어치 팔면 → 영업이익 ' + Math.round(o.op / rev * 100) + '원 → 순이익 ' + Math.round(ni / rev * 100) + '원', L, y100);
    foot(X, o.src);
  }

  /* 3) 100% 쌓은 막대 — 행: {n, logo, parts:[v...]} · o.keys:[[이름, 색, 글자색]] */
  function stack100(X, o) {
    head(X, o);
    var rows = o.rows, top = 300, rowH = Math.min(46, 880 / rows.length), x0 = L + 250, w = R - x0;
    // 범례
    var lx = L, ly = 262;
    o.keys.forEach(function (k) { X.fillStyle = k[1]; rr(X, lx, ly - 18, 22, 22, 4); X.fill(); X.fillStyle = T.ink; X.font = font(700, 22); X.textAlign = 'left'; X.fillText(k[0], lx + 30, ly); lx += X.measureText(k[0]).width + 62; });
    rows.forEach(function (r, i) {
      var cy = top + i * rowH + rowH / 2, x = x0, bh = rowH - 10;
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
    var nc = o.cols.length, na = o.assets.length, top = 300, cw = (R - L) / nc, ch = Math.min(96, 900 / na);
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
    X.fillText('▲ 그해 1등', L, top + na * ch + 34); X.textAlign = 'right'; X.fillText('칸 위에서 아래로 수익률 순서', R, top + na * ch + 34);
    foot(X, o.src);
  }

  /* 5) 성장 곡선 — o.cols:[라벨], o.series:[{n, c, vals:[원]}], 로그 눈금 */
  function growth(X, o) {
    head(X, o);
    var top = 300, bot = 1160, x0 = L + 60, x1 = R - 210, all = [];
    o.series.forEach(function (s) { s.vals.forEach(function (v) { if (v) all.push(v); }); });
    var lo = Math.min.apply(null, all) * 0.9, hi = Math.max.apply(null, all) * 1.1, LL = Math.log(lo), LH = Math.log(hi);
    var xp = function (i) { return x0 + (x1 - x0) * i / (o.cols.length - 1); }, yp = function (v) { return bot - (bot - top) * (Math.log(v) - LL) / (LH - LL); };
    var ticks = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000].map(function (m) { return m * 1e4; }).filter(function (v) { return v >= lo && v <= hi; });
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
    var gx = L, gy = 300, cell = 58, g = 6, cells = [], used = 0;
    o.items.forEach(function (it, i) { var k = Math.round(it.w); if (used + k > 100) k = 100 - used; for (var j = 0; j < k; j++) cells.push(it.c); used += k; });
    while (cells.length < 100) cells.push(T.gray);
    for (var i = 0; i < 100; i++) { var cx = gx + (i % 10) * (cell + g), cy = gy + Math.floor(i / 10) * (cell + g); X.fillStyle = cells[i]; rr(X, cx, cy, cell, cell, 8); X.fill(); }
    var lx = gx + 10 * (cell + g) + 40, ly = gy + 8, rowH = Math.min(62, 620 / (o.items.length + 1));
    o.items.concat([{ n: '그 외', w: Math.max(0, 100 - o.items.reduce(function (s, x) { return s + x.w; }, 0)), c: T.gray }]).forEach(function (it, i) {
      var cy = ly + i * rowH + rowH / 2;
      X.fillStyle = it.c; rr(X, lx, cy - 13, 26, 26, 6); X.fill();
      if (it.logo) logoAt(X, it.logo, lx + 52, cy, 17);
      X.fillStyle = T.ink; X.font = font(800, 22); X.textAlign = 'left'; X.textBaseline = 'middle';
      X.fillText(fit(X, it.n, R - lx - 160), lx + (it.logo ? 78 : 40), cy);
      X.textAlign = 'right'; X.font = font(900, 24); X.fillText(it.w.toFixed(1) + '%', R, cy);
    });
    X.textBaseline = 'alphabetic';
    var by = gy + 10 * (cell + g) + 46;
    X.textAlign = 'left'; X.fillStyle = T.ink; X.font = font(800, 28); X.fillText(o.note || '', L, by);
    X.fillStyle = T.soft; X.font = font(700, 22); X.fillText('한 칸 = 포트폴리오의 1%', L, by + 40);
    foot(X, o.src);
  }

  /* 7) 맞수 비교 — o.pairs:[{cat, a:{n,cap,v,logo,c}, b:{...}}] 원 넓이 = 시총 */
  function rivals(X, o) {
    head(X, o);
    var top = 270, rowH = Math.min(165, 960 / o.pairs.length), mx = 0;
    o.pairs.forEach(function (p) { mx = Math.max(mx, p.a.v, p.b.v); });
    var rmax = rowH * 0.36, rad = function (v) { return Math.max(5, rmax * Math.sqrt(v / mx)); };
    var xa = 330, xb = 590;
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
