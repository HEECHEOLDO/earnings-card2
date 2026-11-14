/* 인포그래픽 탭 — 자료 모으기 · 보로노이 계산 · 화면 (infographic.html)
   그리기는 infographic-draw.js (window.__vc). 모든 숫자는 열 때마다 최신 자료에서 다시 계산한다:
   data/mcap.json(국내 시총·업종·올해 수익률) · data/mcap_us.json(미국) · data/rank.json(연말 순위) · data/fx.json(환율) */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  function J(u) { return fetch(u, { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); }
  var IMG = {};
  function img(src) {
    if (IMG[src]) return IMG[src];
    IMG[src] = new Promise(function (res) { var i = new Image(); i.onload = function () { res(i); }; i.onerror = function () { res(null); }; i.src = src; });
    return IMG[src];
  }
  function jo(v) { v = v / 1e4; return v >= 10 ? Math.round(v).toLocaleString() + '조' : v.toFixed(1) + '조'; }   // 억원 → 조
  function usd(c) { var t = c / 1e4; return t >= 1 ? '$' + t.toFixed(1) + 'T' : '$' + Math.round(c / 10) + 'B'; }      // 억달러
  function md(d) { var p = (d || '').split('-'); return p.length === 3 ? (+p[1]) + '월 ' + (+p[2]) + '일' : ''; }

  /* ---------------------------------------------------------------- 가중 보로노이 (power diagram) */
  function clip(poly, a, b, c) {
    var out = [], n = poly.length;
    for (var i = 0; i < n; i++) {
      var p = poly[i], q = poly[(i + 1) % n], fp = a * p[0] + b * p[1] - c, fq = a * q[0] + b * q[1] - c;
      if (fp <= 0) out.push(p);
      if ((fp < 0 && fq > 0) || (fq < 0 && fp > 0)) { var t = fp / (fp - fq); out.push([p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])]); }
    }
    return out;
  }
  function area(p) { var s = 0; for (var i = 0; i < p.length; i++) { var a = p[i], b = p[(i + 1) % p.length]; s += a[0] * b[1] - b[0] * a[1]; } return Math.abs(s) / 2; }
  function cent(p) {
    var a = 0, x = 0, y = 0;
    for (var i = 0; i < p.length; i++) { var q = p[i], r = p[(i + 1) % p.length], f = q[0] * r[1] - r[0] * q[1]; a += f; x += (q[0] + r[0]) * f; y += (q[1] + r[1]) * f; }
    if (Math.abs(a) < 1e-9) return p[0];
    return [x / (3 * a), y / (3 * a)];
  }
  function inside(p, x, y) {
    var c = false;
    for (var i = 0, n = p.length; i < n; i++) { var a = p[i], b = p[(i + 1) % n]; if ((a[1] > y) !== (b[1] > y) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1] + 1e-12) + a[0]) c = !c; }
    return c;
  }
  function cells(bound, P, W) {
    return P.map(function (pi, i) {
      var poly = bound.slice();
      for (var j = 0; j < P.length && poly.length; j++) {
        if (i === j) continue;
        var pj = P[j];
        poly = clip(poly, 2 * (pj[0] - pi[0]), 2 * (pj[1] - pi[1]), pj[0] * pj[0] + pj[1] * pj[1] - pi[0] * pi[0] - pi[1] * pi[1] - W[j] + W[i]);
      }
      return poly;
    });
  }
  function rnd(seed) { var s = seed * 9973 + 1; return function () { s = (s * 16807) % 2147483647; return s / 2147483647; }; }
  function vtm(bound, values, iters, seed) {
    var n = values.length, tot = values.reduce(function (s, v) { return s + v; }, 0), A = area(bound);
    var tg = values.map(function (v) { return v / tot * A; });
    if (n === 1) return { cells: [bound], err: 0 };
    var xs = bound.map(function (p) { return p[0]; }), ys = bound.map(function (p) { return p[1]; });
    var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs), y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys), R = rnd(seed), P = [];
    while (P.length < n) { var x = x0 + (x1 - x0) * R(), y = y0 + (y1 - y0) * R(); if (inside(bound, x, y)) P.push([x, y]); }
    var W = P.map(function () { return 0; }), C;
    for (var it = 0; it < iters; it++) {
      C = cells(bound, P, W);
      var ar = C.map(function (c) { return c.length >= 3 ? area(c) : 0; });
      P = C.map(function (c, k) { return c.length >= 3 ? cent(c) : P[k]; });
      for (var k = 0; k < n; k++) { var r = Math.sqrt(Math.max(W[k], 0) + 1e-6) * Math.sqrt(tg[k] / Math.max(ar[k], 1e-6)); W[k] = r * r; }
      for (k = 0; k < n; k++) {
        var dm = 1e18;
        for (var j = 0; j < n; j++) if (j !== k) { var dx = P[k][0] - P[j][0], dy = P[k][1] - P[j][1]; dm = Math.min(dm, dx * dx + dy * dy); }
        W[k] = Math.min(W[k], dm * 0.95);
      }
      var mn = Math.min.apply(null, W); W = W.map(function (w) { return w - mn; });
    }
    C = cells(bound, P, W);
    var err = 0; C.forEach(function (c, k) { err = Math.max(err, Math.abs(area(c) - tg[k]) / tg[k]); });
    return { cells: C, err: err };
  }
  function best(bound, values, iters, tries) {
    var b = null;
    for (var s = 0; s < tries; s++) { var r = vtm(bound, values, iters, s); if (!b || r.err < b.err) b = r; }
    return b.cells;
  }
  function circle(cx, cy, r, n) { var o = []; for (var k = 0; k < n; k++) { var a = 2 * Math.PI * k / n - Math.PI / 2; o.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); } return o; }

  /* ---------------------------------------------------------------- 자료 → 카드 */
  var SECTOR_US = { 'Technology': '기술', 'Consumer Discretionary': '소비재(경기)', 'Finance': '금융', 'Health Care': '헬스케어', 'Telecommunications': '통신',
    'Consumer Staples': '필수소비재', 'Energy': '에너지', 'Industrials': '산업재', 'Utilities': '유틸리티', 'Real Estate': '부동산', 'Basic Materials': '소재', 'Miscellaneous': '기타' };
  var SC_US = { '기술': '#2B6CD9', '소비재(경기)': '#E0A43A', '헬스케어': '#3FAE8C', '금융': '#8C6BD8', '산업재': '#D9677B', '에너지': '#7A5B3A', '기타': '#7A8794',
    '필수소비재': '#5BB0C9', '통신': '#C0392B', '유틸리티': '#9DBA3A', '부동산': '#B07AA1', '소재': '#A0785A' };
  var PAL = ['#D6362C', '#5B8DEF', '#E0A43A', '#8C6BD8', '#3FAE8C', '#D9677B', '#7A5B3A', '#5BB0C9', '#9DBA3A', '#B07AA1'];
  var HI = ['#1428A0', '#E3262B', '#A50034', '#03C75A', '#E8B200', '#F47725', '#5B8DEF', '#8C6BD8'];
  // 1995년 코스피 TOP 10 의 지금 (합병·분할·이름 바뀜 — 순위 자료로는 이어지지 않아 손으로 적은 것)
  var FATE95 = { '015760': ['015760', '한국전력'], '005930': ['005930', '삼성전자'], '005490': ['005490', 'POSCO홀딩스'], '017670': ['017670', 'SK텔레콤'],
    '000200': [null, '대우그룹 해체로 쪼개짐'], '002610': ['066570', 'LG전자'], '015940': [null, 'LG유플러스에 합병'], '000720': ['000720', '현대건설'],
    '015580': ['055550', '신한지주'], '000010': [null, '신한은행에 합병'] };

  var D = {};
  function loadAll() {
    return Promise.all([J('./data/mcap.json'), J('./data/mcap_us.json'), J('./data/rank.json'), J('./data/fx.json')]).then(function (r) {
      D.kr = r[0]; D.us = r[1]; D.rank = r[2]; D.fx = (r[3] && r[3].usdkrw) || 1380;
      D.st = (D.kr && D.kr.stocks) || {};
      D.inds = ((D.kr && D.kr.groups && D.kr.groups.industry) || []).slice().sort(function (a, b) { return b.sum - a.sum; });
      D.total = D.inds.reduce(function (s, g) { return s + g.sum; }, 0);
      D.sec = {}; D.inds.forEach(function (g) { g.codes.forEach(function (c) { if (!D.sec[c]) D.sec[c] = (g.short || g.name).trim(); }); });
      D.asof = (D.kr && D.kr.asof) || '';
    });
  }
  function ko(code, n) { return (window.US_KO && window.US_KO[code]) || n; }

  var CARDS = [
    { id: 'treemap', name: '한국 증시 지도', icon: '▦', build: function () {
      var st = D.st, N = 24, groups = D.inds.slice(0, N).map(function (g) {
        var cs = g.codes.filter(function (c) { return st[c] && st[c].c; }).sort(function (a, b) { return st[b].c - st[a].c; });
        var k = g.sum > 500000 ? 6 : 4, kids = cs.slice(0, k).map(function (c) { return { code: c, n: st[c].n, v: st[c].c, y: st[c].y == null ? 0 : st[c].y, nodata: st[c].y == null }; });
        var rest = cs.slice(k).reduce(function (s, c) { return s + st[c].c; }, 0);
        if (rest > 0) kids.push({ n: '그 외', v: rest, y: 0, other: true });
        return { n: (g.short || g.name).trim(), v: g.sum, capTxt: jo(g.sum), kids: kids };
      });
      var shown = D.inds.slice(0, N).reduce(function (s, g) { return s + g.sum; }, 0), top = groups[0], share = Math.round(top.v / D.total * 100);
      return Promise.all(groups.map(function (g) { return Promise.all(g.kids.map(function (k) { return k.code ? img('./logo/kr/' + k.code + '.png').then(function (i) { k.logo = i; }) : null; })); })).then(function () {
        return { fn: 'treemap', o: { kicker: '한국 증시 지도', h1: '코스피·코스닥, ' + top.n + (share >= 45 ? '가 절반' : '가 ' + share + '%'),
          h2: '전체 ' + jo(D.total) + ' 중 ' + top.n + ' ' + share + '% · 칸 크기는 시총, 색은 올해 수익률', groups: groups,
          src: '네이버 금융 업종 분류(시총 상위 ' + N + '개 업종, 전체의 ' + Math.round(shown / D.total * 100) + '%) · ' + md(D.asof) + ' 종가' } };
      });
    } },
    { id: 'ranked', name: '올해 많이 오른 종목', icon: '☰', build: function () {
      var st = D.st, rows = Object.keys(st).filter(function (c) { return st[c].c >= 10000 && st[c].y != null; })
        .sort(function (a, b) { return st[b].y - st[a].y; }).slice(0, 15);
      var secs = [], col = {};
      rows = rows.map(function (c) { var s = D.sec[c] || '기타'; if (!(s in col)) { col[s] = PAL[secs.length % PAL.length]; secs.push(s); } return { code: c, n: st[c].n, v: st[c].y, sector: s, capTxt: jo(st[c].c), c: col[s] }; });
      return Promise.all(rows.map(function (r) { return img('./logo/kr/' + r.code + '.png').then(function (i) { r.logo = i; }); })).then(function () {
        return { fn: 'ranked', o: { kicker: 'RANKED', h1: '올해 가장 많이 오른 종목', h2: '시가총액 1조 원 이상 · ' + D.asof.slice(0, 4) + '년 연초 대비', rows: rows,
          legend: secs.map(function (s) { return [s, col[s]]; }), src: md(D.asof) + ' 종가 기준' } };
      });
    } },
    { id: 'bump', name: '10년 순위 변천', icon: '〰', build: function () {
      var cols = D.rank.cols, y1 = +(Object.keys(cols).filter(function (k) { return k !== 'now'; }).sort().pop()), keys = [];
      for (var y = y1 - 9; y <= y1; y++) keys.push(String(y));
      // '지금' 칸: 시가총액 탭 자료(보통주만)가 더 새것이면 그걸로
      var nowList = (D.kr.kospi || []).filter(function (x) { return x.code.slice(-1) === '0'; }).map(function (x) { return [x.code, x.name, x.cap]; });
      var get = function (k) { return k === 'now' ? nowList : cols[k].kospi; };
      keys.push('now');
      var ser = {};
      keys.forEach(function (k, i) { get(k).slice(0, 10).forEach(function (r, j) { (ser[r[0]] = ser[r[0]] || { code: r[0], n: r[1], ranks: keys.map(function () { return null; }) }).ranks[i] = j + 1; }); });
      var nowTop = get('now').slice(0, 10).map(function (r) { return r[0]; });
      var S = Object.keys(ser).map(function (c) { return ser[c]; }).filter(function (s) { return s.ranks.filter(Boolean).length >= 2 || nowTop.indexOf(s.code) >= 0; });
      // 강조: 지금 TOP 6 (선이 너무 많으면 읽히지 않는다)
      var hi = S.filter(function (s) { return s.ranks[keys.length - 1] && s.ranks[keys.length - 1] <= 6; })
        .sort(function (a, b) { return a.ranks[keys.length - 1] - b.ranks[keys.length - 1]; });
      hi.forEach(function (s, i) { s.hi = true; s.c = HI[i]; });
      S.forEach(function (s) { s.n = s.n.replace(/^POSCO$/, 'POSCO홀딩스'); });
      // 주석: 지금 처음 TOP 10 에 든 회사
      var notes = [], last = keys.length - 1;
      S.forEach(function (s) { if (s.ranks[last] && s.ranks.slice(0, last).every(function (r) { return !r; })) notes.push({ i: last, rk: s.ranks[last], dy: -26, text: s.n + ' 첫 TOP 10', c: s.c || '#6B7078', align: 'right' }); });
      return Promise.all(S.map(function (s) { return img('./logo/kr/' + s.code + '.png').then(function (i) { s.logo = i; }); })).then(function () {
        return { fn: 'bump', o: { kicker: '10년의 순위 싸움', h1: '코스피 TOP 10, 이렇게 바뀌었다', h2: '해마다 마지막 거래일 시가총액 순위',
          cols: keys.map(function (k) { return { label: k === 'now' ? "'" + D.asof.slice(2, 4) + '.' + D.asof.slice(5, 7) : "'" + k.slice(2) }; }), series: S, notes: notes.slice(0, 2),
          src: "한국거래소 연말 시가총액 · 마지막 칸은 " + md(D.asof) + ' 종가' } };
      });
    } },
    { id: 'dumbbell', name: '연초 대비 지금', icon: '⇢', build: function () {
      var st = D.st, rows = Object.keys(st).filter(function (c) { return st[c].c && st[c].y != null; }).sort(function (a, b) { return st[b].c - st[a].c; }).slice(0, 15)
        .map(function (c) { return { code: c, n: st[c].n, v1: st[c].c / 1e4, v0: st[c].c / 1e4 / (1 + st[c].y / 100), y: st[c].y }; });
      var mx = Math.max.apply(null, rows.map(function (r) { return Math.max(r.v0, r.v1); })) * 1.08;
      return Promise.all(rows.map(function (r) { return img('./logo/kr/' + r.code + '.png').then(function (i) { r.logo = i; }); })).then(function () {
        return { fn: 'dumbbell', o: { kicker: '올해의 성적표', h1: '시총 TOP 15, 연초 대비 지금', h2: '점 두 개 사이가 올해 늘거나 줄어든 시가총액', rows: rows, max: mx,
          src: md(D.asof) + ' 종가 · 연초 값은 올해 수익률로 역산' } };
      });
    } },
    { id: 'voronoi', name: '미국 증시 지도', icon: '⬡', build: function () {
      var st = D.us.stocks, top = Object.keys(st).filter(function (k) { return st[k].c; }).sort(function (a, b) { return st[b].c - st[a].c; }).slice(0, 50);
      var g = {}, order = [];
      top.forEach(function (k) { var s = SECTOR_US[st[k].s] || st[k].s || '기타'; if (!g[s]) { g[s] = []; order.push(s); } g[s].push({ code: k, n: st[k].n, ko: ko(k, st[k].n), v: st[k].c, cap: usd(st[k].c) }); });
      var groups = order.map(function (s) { return { g: s, v: g[s].reduce(function (t, x) { return t + x.v; }, 0), kids: g[s] }; });
      var tot = groups.reduce(function (s, x) { return s + x.v; }, 0);
      var bound = circle(540, 760, 440, 96), G = best(bound, groups.map(function (x) { return x.v; }), 300, 3);
      groups.forEach(function (x, i) {
        x.poly = G[i];
        if (x.poly.length < 3) { x.kids = []; return; }
        var K = x.kids.length > 1 ? best(x.poly, x.kids.map(function (k) { return k.v; }), 220, 2) : [x.poly];
        x.kids.forEach(function (k, j) { k.poly = K[j]; });
      });
      var tech = groups.filter(function (x) { return x.g === '기술'; })[0], ts = tech ? Math.round(tech.v / tot * 100) : 0;
      return Promise.all([].concat.apply([], groups.map(function (x) { return x.kids.map(function (k) { return img('./logo/us/' + k.code + '.png').then(function (i) { k.logo = i; }); }); }))).then(function () {
        return { fn: 'voronoi', o: { kicker: '미국 증시 지도', h1: '미국 시총 TOP 50, ' + (ts >= 50 ? '절반 넘게 기술주' : '기술주가 ' + ts + '%'), h2: '조각 넓이 = 시가총액 · 색 = 업종',
          cells: groups, colors: SC_US, legend: groups.map(function (x) { return [x.g, '$' + (x.v / 1e4).toFixed(1) + 'T']; }),
          src: '나스닥 종목 검색표 업종 · ' + md(D.us.asof) + ' 종가' } };
      });
    } },
    { id: 'radial', name: '한 바퀴 수익률', icon: '✺', build: function () {
      var st = D.st, rows = Object.keys(st).filter(function (c) { return st[c].c && st[c].y != null; }).sort(function (a, b) { return st[b].c - st[a].c; }).slice(0, 20)
        .map(function (c) { return { n: st[c].n, v: st[c].y, c: '#D6362C' }; });
      var up = rows.filter(function (r) { return r.v > 0; }).length;
      return Promise.resolve({ fn: 'radial', o: { kicker: '한 바퀴로 보는 올해', h1: '시총 TOP 20, 올해 수익률', h2: '막대 길이 = 연초 대비 수익률 (파랑은 마이너스)', rows: rows, max: 120,
        centerTop: 'TOP 20 중', centerBig: up + '곳 상승', src: md(D.asof) + ' 종가 (올해 수익률이 없는 금융주 등은 빠짐)' } });
    } },
    { id: 'thennow', name: '30년 전과 지금', icon: '⇄', build: function () {
      var cols = D.rank.cols, first = Object.keys(cols).sort()[0];
      var nowList = (D.kr.kospi || []).filter(function (x) { return x.code.slice(-1) === '0'; });
      var nowRank = {}; nowList.forEach(function (x, i) { nowRank[x.code] = i + 1; });
      var right = nowList.slice(0, 10).map(function (x) { return { key: x.code, code: x.code, n: x.name, cap: jo(x.cap) }; });
      var left = cols[first].kospi.slice(0, 10).map(function (r) {
        var f = FATE95[r[0]], succ = f ? f[0] : r[0], nm = f ? f[1] : r[1], rk = succ && nowRank[succ];
        return { key: succ || r[0], n: r[1], cap: jo(r[2]), fate: succ ? (nm + ' · ' + (rk ? '지금 ' + rk + '위' : '지금 시총 순위 밖')) : nm };
      });
      var kept = left.filter(function (l) { return right.some(function (r) { return r.key === l.key; }); });
      return Promise.all(right.map(function (r) { return img('./logo/kr/' + r.code + '.png').then(function (i) { r.logo = i; }); })).then(function () {
        return { fn: 'thenNow', o: { kicker: (+D.asof.slice(0, 4) - +first) + '년 전과 지금', h1: first + '년 코스피 TOP 10, 지금은?',
          h2: kept.length === 1 ? (+D.asof.slice(0, 4) - +first) + '년을 버틴 건 ' + kept[0].n + ' 하나' : '지금도 TOP 10 인 곳은 ' + kept.length + '곳',
          left: left, right: right, leftLabel: first + '년', rightLabel: D.asof.slice(0, 4) + '년', note: '',
          src: '한국거래소 연말 시가총액 · ' + D.asof.slice(0, 4) + '년은 ' + md(D.asof) + ' 종가' } };
      });
    } },
    { id: 'compare', name: '크기 비교', icon: '◯', build: function () {
      var us = D.us.stocks, topUS = Object.keys(us).filter(function (k) { return us[k].c; }).sort(function (a, b) { return us[b].c - us[a].c; })[0];
      var big = us[topUS].c * 1e8 * D.fx / 1e12, kr = D.total / 1e4, sam = D.st['005930'].c / 1e4, hy = D.st['000660'].c / 1e4;
      var nm = ko(topUS, us[topUS].n), n = Object.keys(D.st).length, r1000 = Math.floor(n / 100) * 100;
      var J2 = function (v) { return Math.round(v).toLocaleString() + '조'; };
      return Promise.all([img('./logo/us/' + topUS + '.png'), img('./logo/kr/005930.png'), img('./logo/kr/000660.png')]).then(function (L) {
        var items = [{ n: nm, cap: J2(big), v: big, c: '#4A5A78', logo: L[0] }, { n: '한국 증시 전체', cap: J2(kr), v: kr, c: '#C0392B', times: nm + '의 ' + Math.round(kr / big * 100) + '%' },
          { n: '삼성전자', cap: J2(sam), v: sam, c: '#1428A0', logo: L[1], times: nm + '의 ' + Math.round(sam / big * 100) + '%' }, { n: 'SK하이닉스', cap: J2(hy), v: hy, c: '#E3262B', logo: L[2], times: nm + '의 ' + Math.round(hy / big * 100) + '%' }];
        if (kr > big) items = [items[1], items[0], items[2], items[3]];
        return { fn: 'compare', o: { kicker: '크기 비교', h1: kr < big ? nm + ' 하나가 한국 증시 전체보다 크다' : '한국 증시 전체가 ' + nm + '보다 크다',
          h2: '원 넓이 = 시가총액 · 환율 ' + Math.round(D.fx).toLocaleString() + '원', items: items,
          note: kr < big ? '코스피·코스닥 ' + r1000.toLocaleString() + '여 종목을 다 합쳐도 ' + nm + '의 ' + Math.round(kr / big * 100) + '%' : '',
          src: md(D.asof) + ' 종가 · 원화 환산' } };
      });
    } }
  ];

  /* ---------------------------------------------------------------- 화면 */
  function init() {
    var cv = $('card'); if (!cv) return;
    var X = cv.getContext('2d'), cur = null, last = null, cache = {};
    var bar = $('kinds');
    CARDS.forEach(function (c) {
      var b = document.createElement('button'); b.className = 'preset'; b.dataset.k = c.id; b.setAttribute('aria-pressed', 'false');
      b.innerHTML = '<span aria-hidden="true">' + c.icon + '</span> ' + c.name; bar.appendChild(b);
      b.addEventListener('click', function () { pick(c.id); });
    });
    function draw() { if (!last) return; X.setTransform(1, 0, 0, 1, 0, 0); window.__vc[last.fn](X, last.o); }
    function pick(id) {
      cur = id;
      Array.prototype.forEach.call(bar.children, function (b) { b.setAttribute('aria-pressed', String(b.dataset.k === id)); });
      try { history.replaceState(null, '', '?k=' + id); } catch (e) { /* 미리보기 */ }
      var c = CARDS.filter(function (x) { return x.id === id; })[0];
      $('c-hint').textContent = '그리는 중…';
      (cache[id] || (cache[id] = c.build())).then(function (r) {
        if (cur !== id) return;
        last = r; draw(); $('c-hint').textContent = c.name + ' · ' + md(D.asof) + ' 기준 자료로 방금 다시 계산했어요.';
      }).catch(function (e) { $('c-hint').textContent = '이 카드를 그리지 못했어요 (' + (e && e.message || e) + ').'; });
    }
    $('c-dl').addEventListener('click', function () {
      if (!last) return;
      var big = document.createElement('canvas'); big.width = 1080 * 3; big.height = 1350 * 3;
      var g = big.getContext('2d'); g.scale(3, 3); window.__vc[last.fn](g, last.o);
      big.toBlob(function (blob) {
        if (!blob) { alert('그림을 만들지 못했습니다. 새로고침 후 다시 눌러 주세요.'); return; }
        var a = document.createElement('a'); a.href = URL.createObjectURL(blob);
        a.download = '돈굴돈굴_' + (CARDS.filter(function (x) { return x.id === cur; })[0].name) + '_' + D.asof + '.png';
        document.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 10000);
      }, 'image/png');
    });
    $('btn-mode').addEventListener('click', function () { var r = document.documentElement; r.setAttribute('data-mode', r.getAttribute('data-mode') === 'dark' ? 'light' : 'dark'); draw(); });
    $('c-hint').textContent = '자료 불러오는 중…';
    loadAll().then(function () { return document.fonts && document.fonts.ready; }).then(function () {
      $('src-pill').textContent = '인포그래픽 ' + CARDS.length + '종 · ' + md(D.asof) + ' 기준';
      var k0 = new URLSearchParams(location.search).get('k');
      pick(CARDS.some(function (c) { return c.id === k0; }) ? k0 : CARDS[0].id);
    });
  }
  window.__ig = { cards: CARDS, data: D, load: loadAll };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
