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


  var MKT = [['all', '전체'], ['kospi', '코스피'], ['kosdaq', '코스닥']], MKN = { all: '코스피·코스닥', kospi: '코스피', kosdaq: '코스닥' };
  function josa(w, a, b) { var c = (w || '').charCodeAt(w.length - 1); if (c >= 0xAC00 && c <= 0xD7A3) return (c - 0xAC00) % 28 ? a : b; return /[013678LMNR]$/i.test(w) ? a : b; }
  function logos(groups) { return Promise.all(groups.map(function (g) { return Promise.all(g.kids.map(function (k) { return k.code ? img('./logo/' + (k.us ? 'us/' : 'kr/') + k.code + '.png').then(function (i) { k.logo = i; }) : null; })); })); }
  function logo(r, us) { return img('./logo/' + (us ? 'us/' : 'kr/') + r.code + '.png').then(function (i) { r.logo = i; return r; }); }
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

  var MEMO = {};
  function JJ(u) { return MEMO[u] || (MEMO[u] = J(u)); }
  var _scr = null;
  function SCREEN() {
    return _scr || (_scr = JJ('./data/screen.json').then(function (s) {
      var F = s.fields, o = {}; s.rows.forEach(function (r) { var x = {}; F.forEach(function (f, i) { x[f] = r[i]; }); o[x.code] = x; }); return o;
    }));
  }
  // 미국 시총 상위 100 의 올해 수익률 — 종목별 일별 종가(data/chart/us)에서 작년 마지막 종가 대비로 계산
  var _usy = null;
  function USY() {
    return _usy || (_usy = (function () {
      var st = D.us.stocks, y0 = +D.asof.slice(0, 4) * 10000;
      var top = Object.keys(st).filter(function (k) { return st[k].c; }).sort(function (a, b) { return st[b].c - st[a].c; }).slice(0, 100);
      return Promise.all(top.map(function (t) { return J('./data/chart/us/' + t + '.json'); })).then(function (js) {
        return top.map(function (t, i) {
          var d = (js[i] && js[i].d) || [], b = d.filter(function (p) { return p[0] < y0; }).slice(-1)[0], e = d[d.length - 1];
          return { t: t, n: ko(t, st[t].n), c: st[t].c, sec: SECTOR_US[st[t].s] || st[t].s || '기타', y: b && e ? (e[1] / b[1] - 1) * 100 : null };
        });
      });
    })());
  }
  function SANKEY_OPTS() {
    var st = D.st, kr = Object.keys(st).filter(function (c) { return c.slice(-1) === '0' && st[c].c; }).sort(function (a, b) { return st[b].c - st[a].c; }).slice(0, 10)
      .map(function (c) { return ['kr:' + c, st[c].n]; });
    var us = D.us.stocks, u = Object.keys(us).filter(function (k) { return us[k].c; }).sort(function (a, b) { return us[b].c - us[a].c; }).slice(0, 8)
      .map(function (k) { return ['us:' + k, ko(k, us[k].n)]; });
    return kr.concat(u);
  }

  function pct1(v) { return (v > 0 ? '+' : '') + v.toFixed(1) + '%'; }
  var IDXOPT = [['KOSPI', '코스피'], ['KOSDAQ', '코스닥'], ['SPX', 'S&P 500'], ['NDX', '나스닥 100'], ['SOX', '필라델피아 반도체'], ['N225', '닛케이 225']];
  var IDXN = {}; IDXOPT.forEach(function (x) { IDXN[x[0]] = x[1]; });
  // 지수: 주별(약 10년) + 일별(최근 1년)을 합친 종가
  function IDXS(code) {
    return JJ('./data/chart/idx/' + code + '.json').then(function (j) {
      var m = {}; (j.w || []).forEach(function (p) { m[p[0]] = p[1]; }); (j.d || []).forEach(function (p) { m[p[0]] = p[1]; });
      return Object.keys(m).map(Number).sort(function (a, b) { return a - b; }).map(function (k) { return [k, m[k]]; });
    });
  }
  function IDXY(code) {
    var y0 = +D.asof.slice(0, 4) * 10000;
    return IDXS(code).then(function (p) { var b = p.filter(function (x) { return x[0] < y0; }).slice(-1)[0], e = p[p.length - 1]; return b ? (e[1] / b[1] - 1) * 100 : 0; });
  }
  function ko(code, n) { return (window.US_KO && window.US_KO[code]) || n; }

  var CARDS = [
    { id: 'treemap', name: '한국 증시 지도', icon: '▦', opts: MKT, build: function (mk) {
      var st = D.st, N = 24, ok = function (c) { return st[c] && st[c].c && (mk === 'all' || st[c].m === mk); };
      var all = D.inds.map(function (g) {
        var cs = g.codes.filter(ok).sort(function (a, b) { return st[b].c - st[a].c; });
        return { g: g, cs: cs, sum: cs.reduce(function (t, c) { return t + st[c].c; }, 0) };
      }).filter(function (x) { return x.sum > 0; }).sort(function (a, b) { return b.sum - a.sum; });
      var total = all.reduce(function (t, x) { return t + x.sum; }, 0);
      var groups = all.slice(0, N).map(function (x) {
        var cs = x.cs, k = 0, acc = 0; while (k < cs.length && (k < 4 || (acc < x.sum * 0.7 && k < (x.sum > total * 0.1 ? 14 : 8)))) { acc += st[cs[k]].c; k++; } var kids = cs.slice(0, k).map(function (c) { return { code: c, n: st[c].n, v: st[c].c, y: st[c].y == null ? 0 : st[c].y, nodata: st[c].y == null }; });
        var rest = cs.slice(k).reduce(function (t, c) { return t + st[c].c; }, 0);
        if (rest > 0) kids.push({ n: '그 외 ' + (cs.length - k) + '곳', v: rest, y: 0, other: true });
        return { n: (x.g.short || x.g.name).trim(), v: x.sum, capTxt: jo(x.sum), kids: kids };
      });
      var top = groups[0], share = Math.round(top.v / total * 100);
      return logos(groups).then(function () {
        return { fn: 'treemap', o: { kicker: '한국 증시 지도', h1: MKN[mk] + ', ' + top.n + josa(top.n, '이', '가') + (share >= 45 ? ' 절반' : ' ' + share + '%'), groups: groups } };
      });
    } },
    { id: 'ranked', name: '올해 많이 오른 종목', icon: '☰', opts: MKT, build: function (mk) {
      var st = D.st, rows = Object.keys(st).filter(function (c) { return st[c].c >= 10000 && st[c].y != null && (mk === 'all' || st[c].m === mk); })
        .sort(function (a, b) { return st[b].y - st[a].y; }).slice(0, 15);
      var secs = [], col = {};
      rows = rows.map(function (c) { var s = D.sec[c] || '기타'; if (!(s in col)) { col[s] = PAL[secs.length % PAL.length]; secs.push(s); } return { code: c, n: st[c].n, v: st[c].y, sector: s, capTxt: jo(st[c].c), c: col[s] }; });
      return Promise.all(rows.map(function (r) { return img('./logo/kr/' + r.code + '.png').then(function (i) { r.logo = i; }); })).then(function () {
        return { fn: 'ranked', o: { kicker: 'RANKED · ' + MKN[mk], h1: '올해 가장 많이 오른 종목', rows: rows, legend: secs.map(function (s) { return [s, col[s]]; }) } };
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
    } },
    /* ---------------- 2차: 실적 · 지수 · 수익률 · 주주 · 포트폴리오 · 미국 · 맞수 ---------------- */
    { id: 'sankey', name: '돈의 흐름', icon: '⤳', opts: function () { return SANKEY_OPTS(); }, build: function (key) {
      var us = key.slice(0, 3) === 'us:', code = key.slice(3);
      return JJ(us ? './data/us/' + code + '.json' : './data/' + code + '.json').then(function (d) {
        if (!d || !d.quarterly || !d.quarterly.length) throw new Error('실적 자료 없음');
        var q = d.quarterly.filter(function (x) { return x.rev > 0 && x.op != null && x.ni != null; }).slice(-1)[0];
        var nm = us ? ko(code, (D.us.stocks[code] || {}).n || code) : d.name;
        var money = us ? function (v) { var b = v / 1000, a = Math.abs(b); return (b < 0 ? '-' : '') + (a >= 1000 ? '$' + (a / 1000).toFixed(2) + 'T' : '$' + (a >= 100 ? Math.round(a) : a.toFixed(1)) + 'B'); }
          : function (v) { var a = Math.abs(v); return (v < 0 ? '-' : '') + (a >= 1e4 ? (a / 1e4).toFixed(a >= 1e5 ? 0 : 1) + '조' : Math.round(a).toLocaleString() + '억'); };
        var fy = us && d.fye && d.fye !== 12;
        var period = (fy ? '회계 ' : '') + "'" + String(q.y).slice(2) + '년 ' + q.q + '분기';
        var o = { kicker: '돈의 흐름 · ' + period, h1: q.op > 0 ? nm + ', 100원 팔아 ' + Math.round(q.op / q.rev * 100) + '원 남겼다' : nm + ', 이번 분기는 영업손실',
          rev: q.rev, op: q.op, ni: q.ni, money: money, pct: function (v) { return Math.round(v / q.rev * 100) + '%'; }, period: period };
        return logo({ code: code }, us).then(function (r) { o.logo = r.logo; return { fn: 'sankey', o: o, src: period + ' 실적 기준' }; });
      });
    } },
    { id: 'surprise', name: '실적 지도', icon: '▤', build: function () {
      return SCREEN().then(function (S) {
        var st = D.st, per = {}, N = 20;
        var groups = D.inds.slice(0, N).map(function (g) {
          var cs = g.codes.filter(function (c) { return st[c] && st[c].c; }).sort(function (a, b) { return st[b].c - st[a].c; });
          var k = g.sum > D.total * 0.1 ? 6 : 4, kids = cs.slice(0, k).map(function (c) {
            var r = S[c], it = { code: c, n: st[c].n, v: st[c].c };
            if (!r || (r.qOpYoy == null && !r.qTurn)) { it.nodata = true; it.y = 0; return it; }
            per[r.qPeriod] = (per[r.qPeriod] || 0) + 1;
            if (r.qTurn === 1) { it.y = 300; it.lab = '흑자전환'; } else if (r.qTurn === -1) { it.y = -300; it.lab = '적자전환'; }
            else { it.y = r.qOpYoy; it.lab = (r.qOpYoy >= 0 ? '+' : '') + (Math.abs(r.qOpYoy) > 999 ? (r.qOpYoy > 0 ? '999%↑' : '999%↓') : Math.round(r.qOpYoy) + '%'); }
            return it;
          });
          var rest = cs.slice(k).reduce(function (t, c) { return t + st[c].c; }, 0);
          if (rest > 0) kids.push({ n: '그 외', v: rest, y: 0, other: true });
          return { n: (g.short || g.name).trim(), v: g.sum, capTxt: jo(g.sum), kids: kids };
        });
        var all = [].concat.apply([], groups.map(function (g) { return g.kids.filter(function (k) { return !k.other && !k.nodata; }); }));
        var up = all.filter(function (k) { return k.y > 0; }).length, pk = Object.keys(per).sort(function (a, b) { return per[b] - per[a]; })[0] || '';
        return logos(groups).then(function () {
          return { fn: 'treemap', o: { kicker: '최근 분기 실적 지도', h1: '대형주 ' + all.length + '곳 중 ' + up + '곳, 이익 늘었다', groups: groups, k: 1.6,
            legendTitle: '영업이익 1년 전 대비', stops: [-100, -50, 0, 50, 100, 200] }, src: "'" + pk.slice(2, 4) + '년 ' + pk.slice(4) + '분기 실적 기준 (일부 최근 발표분 포함)' };
        });
      });
    } },
    { id: 'margin', name: '영업이익률 TOP', icon: '%', opts: MKT, build: function (mk) {
      return SCREEN().then(function (S) {
        var st = D.st, secs = [], col = {};
        var rows = Object.keys(S).filter(function (c) { var r = S[c]; return st[c] && st[c].c >= 10000 && (mk === 'all' || st[c].m === mk) && r.qRev >= 1000 && r.qMargin != null && r.qMargin <= 90; })
          .sort(function (a, b) { return S[b].qMargin - S[a].qMargin; }).slice(0, 15).map(function (c) {
            var r = S[c], s = D.sec[c] || '기타'; if (!(s in col)) { col[s] = PAL[secs.length % PAL.length]; secs.push(s); }
            return { code: c, n: st[c].n, v: r.qMargin, lab: Math.round(r.qMargin) + '원', sub: s + ' · 분기 매출 ' + jo(r.qRev), c: col[s] };
          });
        return Promise.all(rows.map(function (r) { return logo(r); })).then(function () {
          var pk = String(S[rows[0].code].qPeriod || '');
          return { fn: 'bars', o: { kicker: '영업이익률 TOP 15 · ' + MKN[mk], h1: '100원 팔아 가장 많이 남긴 회사', rows: rows, legend: secs.slice(0, 6).map(function (s) { return [s, col[s]]; }) },
            src: "'" + pk.slice(2, 4) + '년 ' + pk.slice(4) + '분기 실적 기준 · 시총 1조·분기 매출 1,000억 이상' };
        });
      });
    } },
    { id: 'world', name: '세계 증시 성적표', icon: '◍', build: function () {
      var IX = [['KOSPI', '코스피', 'KR'], ['KOSDAQ', '코스닥', 'KR'], ['SPX', 'S&P 500', 'US'], ['IXIC', '나스닥 종합', 'US'], ['NDX', '나스닥 100', 'US'], ['DJI', '다우존스', 'US'],
        ['SOX', '필라델피아 반도체', 'US'], ['RUT', '러셀 2000', 'US'], ['N225', '닛케이 225', 'JP'], ['HSI', '항셍', 'HK'], ['SSEC', '상하이 종합', 'CN'], ['KOSPI200', '코스피 200', 'KR']];
      var y0 = +D.asof.slice(0, 4) * 10000;
      return Promise.all(IX.map(function (x) { return JJ('./data/chart/idx/' + x[0] + '.json'); })).then(function (js) {
        var last = '';
        var rows = IX.map(function (x, i) {
          var d = (js[i] && js[i].d) || [], b = d.filter(function (p) { return p[0] < y0; }).slice(-1)[0], e = d[d.length - 1];
          if (!b || !e) return null; if (String(e[0]) > last) last = String(e[0]);
          var v = (e[1] / b[1] - 1) * 100;
          return { code: x[2], n: x[1], v: v, lab: (v >= 0 ? '+' : '') + v.toFixed(1) + '%', sub: e[1].toLocaleString(undefined, { maximumFractionDigits: 1 }) + 'pt', cc: x[2] };
        }).filter(Boolean).sort(function (a, b) { return b.v - a.v; });
        return Promise.all(rows.map(function (r) { return img('./logo/idx/' + r.cc + '.png').then(function (i) { r.logo = i; }); })).then(function () {
          return { fn: 'bars', o: { kicker: '세계 증시 성적표', h1: '올해 세계 증시 1등은 ' + rows[0].n, rows: rows }, asof: last.slice(0, 4) + '-' + last.slice(4, 6) + '-' + last.slice(6) };
        });
      });
    } },
    { id: 'quilt', name: '자산별 수익률 퀼트', icon: '▩', build: function () {
      return JJ('./data/returns.json').then(function (R) {
        var it = R.items, cy = +D.asof.slice(0, 4), yrs = [];
        for (var y = cy - 10; y <= cy; y++) yrs.push(String(y));
        var A = [['SPY', 'S&P 500', '#2B6CD9', '#fff'], ['QQQ', '나스닥 100', '#8C6BD8', '#fff'], ['069500', '코스피 200', '#D6362C', '#fff'], ['SOXX', '미국 반도체', '#E0A43A', '#111214'],
          ['IWM', '미국 소형주', '#5BB0C9', '#111214'], ['VEA', '선진국', '#3FAE8C', '#fff'], ['GLD', '금', '#F2C94C', '#111214'], ['TLT', '미국 장기채', '#7A8794', '#fff'], ['VNQ', '리츠', '#D9677B', '#fff']];
        var assets = A.filter(function (a) { return it[a[0]]; }).map(function (a) { return { n: a[1], c: a[2], ink: a[3], years: yrs.map(function (y) { var v = it[a[0]].years[y]; return v == null ? null : v; }) }; });
        var lead = {}; yrs.forEach(function (y, i) { var b = assets.slice().sort(function (p, q) { return (q.years[i] == null ? -1e9 : q.years[i]) - (p.years[i] == null ? -1e9 : p.years[i]); })[0]; lead[b.n] = 1; });
        var asof = (it.SPY && it.SPY.asof) || D.asof;
        return { fn: 'quilt', o: { kicker: '자산별 연간 수익률', h1: yrs.length + '년 동안 1등은 ' + Object.keys(lead).length + '번 주인이 바뀌었다',
          cols: yrs.map(function (y, i) { return i === yrs.length - 1 ? "'" + y.slice(2) + '(올해)' : "'" + y.slice(2); }), assets: assets }, asof: asof };
      });
    } },
    { id: 'growth', name: '10년 전 100만 원', icon: '↗', build: function () {
      return JJ('./data/returns.json').then(function (R) {
        var it = R.items, cy = +D.asof.slice(0, 4), yrs = [];
        for (var y = cy - 10; y <= cy; y++) yrs.push(String(y));
        var A = [['000660', 'SK하이닉스', '#E3262B', 'kr'], ['005930', '삼성전자', '#1428A0', 'kr'], ['QQQ', '나스닥 100', '#8C6BD8', 'idx/US'], ['SPY', 'S&P 500', '#2B6CD9', 'idx/US'],
          ['GLD', '금', '#E0A43A', 'us'], ['069500', '코스피 200', '#3FAE8C', 'idx/KR']];
        var series = A.filter(function (a) { return it[a[0]] && yrs.every(function (y) { return it[a[0]].years[y] != null; }); }).map(function (a) {
          var v = 1e6, vals = [v]; yrs.forEach(function (y) { v *= 1 + it[a[0]].years[y] / 100; vals.push(v); });
          return { n: a[1], c: a[2], vals: vals, lg: a[3] === 'kr' ? './logo/kr/' + a[0] + '.png' : a[3] === 'us' ? './logo/us/' + a[0] + '.png' : './logo/' + a[3] + '.png' };
        });
        var won = function (v) { return v >= 1e8 ? (v / 1e8).toFixed(v >= 1e9 ? 0 : 1) + '억' : Math.round(v / 1e4).toLocaleString() + '만'; };
        var best = series.slice().sort(function (a, b) { return b.vals[b.vals.length - 1] - a.vals[a.vals.length - 1]; })[0];
        return Promise.all(series.map(function (s) { return img(s.lg).then(function (i) { s.logo = i; }); })).then(function () {
          return { fn: 'growth', o: { kicker: yrs[0] + '년 초에 100만 원을 넣었다면', h1: best.n + '였다면 ' + won(best.vals[best.vals.length - 1]) + ' 원',
            cols: ["'" + yrs[0].slice(2) + '초'].concat(yrs.map(function (y, i) { return i === yrs.length - 1 ? '지금' : "'" + y.slice(2) + '말'; })), series: series, money: won }, asof: (it.SPY && it.SPY.asof) || D.asof, tail: '종가 기준 · 배당 재투자' };
        });
      });
    } },
    { id: 'holders', name: '대주주 지분', icon: '◧', build: function () {
      var st = D.st, codes = Object.keys(st).filter(function (c) { return c.slice(-1) === '0' && st[c].c; }).sort(function (a, b) { return st[b].c - st[a].c; }).slice(0, 30);
      return Promise.all(codes.map(function (c) { return JJ('./data/holders/' + c + '.json'); })).then(function (hs) {
        var rows = [], asof = '';
        hs.forEach(function (h, i) {
          if (!h || rows.length >= 20 || !h.issued) return;
          var m = (h.major || []).reduce(function (t, x) { return t + (x.pct || 0); }, 0), f = (h.five || []).reduce(function (t, x) { return t + (x.pct || 0); }, 0), tr = (h.treasury || 0) / h.issued * 100;
          var sum = m + f + tr; if (sum > 100) { var k = 100 / sum; m *= k; f *= k; tr *= k; }
          if (h.asof > asof) asof = h.asof;
          rows.push({ code: codes[i], n: st[codes[i]].n, parts: [m, f, tr, Math.max(0, 100 - m - f - tr)] });
        });
        var avg = rows.reduce(function (t, r) { return t + r.parts[0]; }, 0) / rows.length;
        return Promise.all(rows.map(function (r) { return logo(r); })).then(function () {
          return { fn: 'stack100', o: { kicker: '누가 주인인가', h1: '시총 TOP ' + rows.length + ', 최대주주 지분 평균 ' + Math.round(avg) + '%', rows: rows,
            keys: [['최대주주 측', '#C0392B', '#fff'], ['5% 이상 주주', '#E0A43A', '#111214'], ['자기주식', '#7A8794', '#fff'], ['그 외', '#E3E0D8', '#3A3E46']] }, asof: asof, tail: '정기보고서 기준' };
        });
      });
    } },
    { id: 'waffle', name: '투자 대가 포트폴리오', icon: '▥', opts: [['berkshire', '워런 버핏'], ['nps', '국민연금'], ['ark', '캐시 우드'], ['gates', '빌 게이츠'], ['pershing', '빌 애크먼'], ['softbank', '소프트뱅크'], ['norges', '노르웨이 국부펀드'], ['bridgewater', '레이 달리오']], build: function (key) {
      return JJ('./data/13f.json').then(function (F) {
        var f = F && F.funds && F.funds[key]; if (!f) throw new Error('자료 없음');
        var C = ['#C0392B', '#2B6CD9', '#E0A43A', '#3FAE8C', '#8C6BD8', '#D9677B', '#5BB0C9', '#7A5B3A', '#9DBA3A'];
        var items = f.holdings.slice().sort(function (a, b) { return b.weight - a.weight; }).slice(0, 9).map(function (h, i) { return { n: h.name, w: h.weight, c: C[i], lg: h.logo }; });
        var top = items.reduce(function (t, x) { return t + x.w; }, 0);
        return Promise.all(items.map(function (x) { return x.lg ? img('./logo/' + (x.lg.indexOf('/') > 0 ? x.lg : 'us/' + x.lg) + '.png').then(function (i) { x.logo = i; }) : null; })).then(function () {
          return { fn: 'waffle', o: { kicker: '투자 대가 포트폴리오 · 미국 주식', h1: f.title + ', ' + items[0].n + josa(items[0].n, '이', '가') + ' ' + Math.round(items[0].w) + '%', items: items,
            note: '상위 ' + items.length + '종목이 ' + Math.round(top) + '% · 전체 ' + f.count.toLocaleString() + '종목' }, asof: f.period, tail: '13F 보고 기준' };
        });
      });
    } },
    { id: 'usmap', name: '미국 수익률 지도', icon: '▧', build: function () {
      return USY().then(function (Y) {
        var g = {}, order = [];
        Y.slice(0, 60).forEach(function (x) { var s = x.sec; if (!g[s]) { g[s] = []; order.push(s); } g[s].push({ code: x.t, us: true, n: x.n, v: x.c, y: x.y == null ? 0 : x.y, nodata: x.y == null }); });
        var groups = order.map(function (s) { var v = g[s].reduce(function (t, k) { return t + k.v; }, 0); return { n: s, v: v, capTxt: '$' + (v / 1e4).toFixed(1) + 'T', kids: g[s] }; });
        var up = Y.slice(0, 60).filter(function (x) { return x.y > 0; }).length;
        return logos(groups).then(function () {
          return { fn: 'treemap', o: { kicker: '미국 증시 지도 · 올해 수익률', h1: '미국 시총 TOP 60, ' + up + '곳 올랐다', groups: groups }, asof: D.us.asof };
        });
      });
    } },
    { id: 'usranked', name: '미국 많이 오른 종목', icon: '☰', build: function () {
      return USY().then(function (Y) {
        var secs = [], col = {};
        var rows = Y.filter(function (x) { return x.y != null; }).sort(function (a, b) { return b.y - a.y; }).slice(0, 15).map(function (x) {
          if (!(x.sec in col)) { col[x.sec] = SC_US[x.sec] || PAL[secs.length % PAL.length]; secs.push(x.sec); }
          return { code: x.t, n: x.n, v: x.y, lab: (x.y >= 0 ? '+' : '') + Math.round(x.y) + '%', sub: x.sec + ' · 시총 ' + usd(x.c), c: col[x.sec] };
        });
        return Promise.all(rows.map(function (r) { return logo(r, true); })).then(function () {
          return { fn: 'bars', o: { kicker: 'RANKED · 미국 시총 상위 ' + Y.length, h1: '미국 올해 상승률 TOP 15', rows: rows, legend: secs.slice(0, 6).map(function (s) { return [s, col[s]]; }) }, asof: D.us.asof };
        });
      });
    } },
    { id: 'rivals', name: '한미 맞수 비교', icon: '⚖', build: function () {
      var P = [['AI 반도체', 'NVDA', '000660'], ['스마트폰', 'AAPL', '005930'], ['자동차', 'TSLA', '005380'], ['검색·포털', 'GOOGL', '035420'], ['메신저·SNS', 'META', '035720'], ['은행', 'JPM', '105560']];
      var J2 = function (v) { return v >= 100 ? Math.round(v).toLocaleString() + '조' : v.toFixed(1) + '조'; };
      var pairs = P.filter(function (p) { return D.us.stocks[p[1]] && D.st[p[2]]; }).map(function (p) {
        var a = D.us.stocks[p[1]].c * D.fx / 1e4, b = D.st[p[2]].c / 1e4;
        return { cat: p[0], a: { code: p[1], n: ko(p[1], D.us.stocks[p[1]].n), v: a, cap: J2(a), c: '#4A5A78' }, b: { code: p[2], n: D.st[p[2]].n, v: b, cap: J2(b), c: '#C0392B' } };
      });
      var mx = Math.max.apply(null, pairs.map(function (p) { return Math.max(p.a.v / p.b.v, p.b.v / p.a.v); }));
      return Promise.all([].concat.apply([], pairs.map(function (p) { return [logo(p.a, true), logo(p.b)]; }))).then(function () {
        return { fn: 'rivals', o: { kicker: '한미 맞수 비교 · 원 넓이 = 시가총액', h1: '같은 업종, 크기는 최대 ' + Math.round(mx) + '배 차이', pairs: pairs }, tail: '종가 기준 · 환율 ' + Math.round(D.fx).toLocaleString() + '원' };
      });
    } },
    /* ---------------- 3차: 분포 · 기여도 · 이익 비중 · 달력 · 월별 · 하락폭 · 산점도 · 배당 · 순위 변화 · 이익 TOP ---------------- */
    { id: 'breadth', name: '지수 vs 내 종목', icon: '▅', opts: MKT, build: function (mk) {
      var st = D.st, ys = Object.keys(st).filter(function (c) { return st[c].y != null && (mk === 'all' || st[c].m === mk); }).map(function (c) { return st[c].y; }).sort(function (a, b) { return a - b; });
      return IDXY(mk === 'kosdaq' ? 'KOSDAQ' : 'KOSPI').then(function (iy) {
        var bins = [], lo = -80, step = 20;
        for (var b = lo; b < 220; b += step) bins.push({ lo: b, hi: b + step, n: 0, tick: (b > 0 ? '+' : '') + b + '%' });
        bins[bins.length - 1].tickEnd = '+220%↑';
        ys.forEach(function (v) { var i = Math.floor((Math.max(lo, Math.min(219.9, v)) - lo) / step); bins[i].n++; });
        var up = ys.filter(function (v) { return v > 0; }).length, beat = ys.filter(function (v) { return v > iy; }).length, med = ys[Math.floor(ys.length / 2)];
        var nm = mk === 'kosdaq' ? '코스닥' : '코스피';
        return { fn: 'hist', o: { kicker: MKN[mk] + ' ' + ys.length.toLocaleString() + '종목 올해 수익률', h1: nm + ' ' + pct1(iy) + ', 종목 중간값은 ' + pct1(med),
          stats: [[up.toLocaleString() + '곳', '올랐다', '#D6362C'], [(ys.length - up).toLocaleString() + '곳', '내렸다', '#2B6CD9'], [Math.round(beat / ys.length * 100) + '%', nm + ' 지수보다 더 오른 종목']],
          bins: bins, mark: { v: iy, label: nm + ' 지수 ' + pct1(iy) }, axis: '연초 대비 수익률 (칸 하나 = 20%p)' } };
      });
    } },
    { id: 'contrib', name: '누가 시총을 올렸나', icon: '⊕', build: function () {
      var st = D.st, g = Object.keys(st).filter(function (c) { return st[c].y != null && st[c].c; }).map(function (c) { var c1 = st[c].c, c0 = c1 / (1 + st[c].y / 100); return { code: c, n: st[c].n, d: c1 - c0 }; });
      var tot = g.reduce(function (t, x) { return t + x.d; }, 0); g.sort(function (a, b) { return b.d - a.d; });
      var top = g.slice(0, 12), rest = tot - top.reduce(function (t, x) { return t + x.d; }, 0), two = (top[0].d + top[1].d) / tot * 100;
      var rows = top.map(function (x) { return { code: x.code, n: x.n, v: x.d, lab: (x.d >= 0 ? '+' : '') + jo(x.d), sub: '늘어난 시총의 ' + Math.round(x.d / tot * 100) + '%', c: x.d >= 0 ? '#D6362C' : '#2B6CD9' }; });
      rows.push({ n: '그 외 ' + (g.length - 12).toLocaleString() + '종목', v: rest, lab: (rest >= 0 ? '+' : '') + jo(rest), sub: '늘어난 시총의 ' + Math.round(rest / tot * 100) + '%', c: '#9A9890' });
      return Promise.all(rows.map(function (r) { return r.code ? logo(r) : null; })).then(function () {
        return { fn: 'bars', o: { kicker: '올해 늘어난 시가총액 ' + jo(tot), h1: two > 100 ? top[0].n + '·' + top[1].n + ', 둘이 늘린 게 전체보다 많다' : top[0].n + '·' + top[1].n + ', 둘이 ' + Math.round(two) + '%를 올렸다', rows: rows } };
      });
    } },
    { id: 'profitshare', name: '시총 비중 vs 이익 비중', icon: '⇋', build: function () {
      return SCREEN().then(function (S) {
        var st = D.st, rows = D.inds.slice(0, 14).map(function (g) {
          var op = g.codes.reduce(function (t, c) { return t + (S[c] && S[c].op > 0 ? S[c].op : 0); }, 0);
          return { n: (g.short || g.name).trim(), cap: g.sum, op: op };
        });
        var allOp = Object.keys(S).reduce(function (t, c) { return t + (S[c].op > 0 && st[c] ? S[c].op : 0); }, 0);
        rows.forEach(function (r) { r.a = r.cap / D.total * 100; r.b = r.op / allOp * 100; });
        var t = rows[0];
        return { fn: 'butterfly', o: { kicker: '덩치와 실속', h1: t.n + ', 시총은 ' + Math.round(t.a) + '% 이익은 ' + Math.round(t.b) + '%', rows: rows,
          left: '시가총액 비중', right: "영업이익 비중('" + String(+D.asof.slice(0, 4) - 1).slice(2) + '년)', ca: '#4A5A78', cb: '#2E9E6B',
          note: '이익보다 시총 비중이 크면 → 앞으로 더 벌 거라고 보는 업종' }, tail: '종가 · 직전 연도 실적 기준' };
      });
    } },
    { id: 'calendar', name: '1년 등락 달력', icon: '▦', opts: IDXOPT, build: function (code) {
      return JJ('./data/chart/idx/' + code + '.json').then(function (j) {
        var d = j.d, days = [];
        for (var i = 1; i < d.length; i++) days.push([d[i][0], (d[i][1] / d[i - 1][1] - 1) * 100]);
        days = days.slice(-260);
        var up = days.filter(function (x) { return x[1] > 0; }).length, best = days.reduce(function (a, x) { return x[1] > a[1] ? x : a; }), worst = days.reduce(function (a, x) { return x[1] < a[1] ? x : a; });
        var dd = function (x) { var s = String(x[0]); return (+s.slice(4, 6)) + '/' + (+s.slice(6)); };
        var last = String(d[d.length - 1][0]);
        return { fn: 'calendar', o: { kicker: IDXN[code] + ' 하루하루', h1: '1년 중 오른 날 ' + up + '일, 내린 날 ' + (days.length - up) + '일', days: days,
          note: '최고 ' + dd(best) + ' ' + pct1(best[1]) + ' · 최악 ' + dd(worst) + ' ' + pct1(worst[1]) }, asof: last.slice(0, 4) + '-' + last.slice(4, 6) + '-' + last.slice(6) };
      });
    } },
    { id: 'monthly', name: '월별 수익률 표', icon: '▤', opts: IDXOPT, build: function (code) {
      return IDXS(code).then(function (pts) {
        var me = {}; pts.forEach(function (p) { me[String(p[0]).slice(0, 6)] = p; });
        var ks = Object.keys(me).sort(), rows = {}, total = {}, years = [];
        for (var i = 1; i < ks.length; i++) {
          var y = +ks[i].slice(0, 4), m = +ks[i].slice(4) - 1, v = (me[ks[i]][1] / me[ks[i - 1]][1] - 1) * 100;
          if (!rows[y]) { rows[y] = [null, null, null, null, null, null, null, null, null, null, null, null]; years.push(y); }
          rows[y][m] = v;
        }
        years = years.filter(function (y) { return rows[y].filter(function (v) { return v != null; }).length >= 3; }).slice(-10);
        years.forEach(function (y) { var e = ks.filter(function (k) { return +k.slice(0, 4) === y; }).pop(), b = ks.filter(function (k) { return +k.slice(0, 4) === y - 1; }).pop(); total[y] = b ? (me[e][1] / me[b][1] - 1) * 100 : null; });
        var avg = []; for (var m2 = 0; m2 < 12; m2++) { var vs = years.map(function (y) { return rows[y][m2]; }).filter(function (v) { return v != null; }); avg.push(vs.reduce(function (s, v) { return s + v; }, 0) / (vs.length || 1)); }
        var bm = avg.indexOf(Math.max.apply(null, avg)), wm = avg.indexOf(Math.min.apply(null, avg)), last = String(pts[pts.length - 1][0]);
        return { fn: 'heatgrid', o: { kicker: IDXN[code] + ' 월별 수익률', h1: years.length + '년 평균, ' + (bm + 1) + '월이 가장 좋았다', years: years, rows: rows, total: total,
          note: '가장 약했던 달은 ' + (wm + 1) + '월 (평균 ' + pct1(avg[wm]) + ')' }, asof: last.slice(0, 4) + '-' + last.slice(4, 6) + '-' + last.slice(6) };
      });
    } },
    { id: 'drawdown', name: '고점 대비 하락폭', icon: '⌄', build: function () {
      var C = [['KOSPI', '코스피', '#D6362C'], ['SPX', 'S&P 500', '#2B6CD9'], ['KOSDAQ', '코스닥', '#E0A43A']];
      return Promise.all(C.map(function (c) { return IDXS(c[0]); })).then(function (all) {
        var t0 = Math.max.apply(null, all.map(function (p) { return p[0][0]; })), t1 = Math.max.apply(null, all.map(function (p) { return p[p.length - 1][0]; }));
        var num = function (n) { var s = String(n); return new Date(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6)).getTime(); }, a = num(t0), b = num(t1);
        var series = C.map(function (c, k) {
          var mx = 0, pts = [];
          all[k].forEach(function (p) { if (p[1] > mx) mx = p[1]; if (p[0] >= t0) { var s = String(p[0]); pts.push([(num(p[0]) - a) / (b - a), (p[1] / mx - 1) * 100, "'" + s.slice(2, 4) + '.' + (+s.slice(4, 6))]); } });
          return { n: c[1], c: c[2], pts: pts };
        });
        var ticks = []; for (var y = +String(t0).slice(0, 4) + 1; y <= +String(t1).slice(0, 4); y++) { var tt = (new Date(y, 0, 1).getTime() - a) / (b - a); if (tt > 0.02 && tt < 0.98) ticks.push([tt, "'" + String(y).slice(2)]); }
        var k0 = series[0], cur = k0.pts[k0.pts.length - 1][1], worst = k0.pts.reduce(function (m, p) { return p[1] < m ? p[1] : m; }, 0);
        var last = String(t1);
        return { fn: 'underwater', o: { kicker: '고점에서 얼마나 빠졌나', h1: '코스피 ' + Math.round((b - a) / 3.156e10) + '년, 최대 ' + Math.round(worst) + '%까지 빠졌다', series: series, ticks: ticks,
          note: '지금 코스피는 고점 대비 ' + (cur > -0.5 ? '사상 최고 근처' : Math.round(cur) + '%') }, asof: last.slice(0, 4) + '-' + last.slice(4, 6) + '-' + last.slice(6) };
      });
    } },
    { id: 'scatter', name: '이익과 주가', icon: '⁘', build: function () {
      return SCREEN().then(function (S) {
        var st = D.st, pts = Object.keys(st).filter(function (c) { var r = S[c]; return c.slice(-1) === '0' && st[c].y != null && r && r.qOpYoy != null && !r.qTurn; })
          .sort(function (a, b) { return st[b].c - st[a].c; }).slice(0, 40).map(function (c) {
            var x = S[c].qOpYoy, y = st[c].y; return { code: c, n: st[c].n, x: x, y: y, v: st[c].c, c: x >= 0 && y >= 0 ? '#D6362C' : x < 0 && y < 0 ? '#2B6CD9' : '#9A9890' };
          });
        var same = pts.filter(function (p) { return (p.x >= 0) === (p.y >= 0); }).length;
        return Promise.all(pts.map(function (p) { return logo(p); })).then(function () {
          return { fn: 'scatter', o: { kicker: '시총 상위 ' + pts.length + '곳 · 원 크기 = 시총', h1: '이익이 늘면 주가도 올랐을까? ' + same + '곳은 같은 방향', pts: pts,
            xr: [-100, 300], yr: [-60, 250], xt: [-100, -50, 0, 50, 100, 200, 300], yt: [-50, 0, 50, 100, 150, 200, 250], xl: '최근 분기 영업이익 (1년 전 대비)', yl: '올해 주가 수익률',
            q1: '이익↑ 주가↑', q3: '이익↓ 주가↓', labels: 16 }, tail: '종가 · 최근 분기 실적 기준' };
        });
      });
    } },
    { id: 'dividend', name: '배당수익률 TOP', icon: '¤', opts: MKT, build: function (mk) {
      return SCREEN().then(function (S) {
        var st = D.st, rows = Object.keys(S).filter(function (c) { var r = S[c]; return st[c] && st[c].c >= 5000 && (mk === 'all' || st[c].m === mk) && r.yield != null && r.yield < 12 && r.divYears >= 3; })
          .sort(function (a, b) { return S[b].yield - S[a].yield; }).slice(0, 15).map(function (c) {
            var r = S[c]; return { code: c, n: st[c].n, v: r.yield, lab: r.yield.toFixed(1) + '%', sub: (D.sec[c] || '') + ' · 배당 ' + r.divYears + '년째' + (r.divGrowYears >= 3 ? ' · ' + r.divGrowYears + '년 연속 증가' : ''), c: r.divGrowYears >= 3 ? '#2E9E6B' : '#7FB89B' };
          });
        return Promise.all(rows.map(function (r) { return logo(r); })).then(function () {
          return { fn: 'bars', o: { kicker: '배당수익률 TOP 15 · ' + MKN[mk], h1: '1,000만 원 넣으면 1년 배당 ' + Math.round(rows[0].v * 10) + '만 원', rows: rows,
            legend: [['3년 이상 연속 배당 증가', '#2E9E6B'], ['그 외', '#7FB89B']] }, tail: '종가 · 직전 연도 주당 배당금 기준 (시총 5,000억 이상, 3년 이상 배당)' };
        });
      });
    } },
    { id: 'slope', name: '작년 말 vs 지금 순위', icon: '⟋', build: function () {
      var y = String(+D.asof.slice(0, 4) - 1), A = (D.rank.cols[y] || {}).kospi || [], B = (D.kr.kospi || []).filter(function (x) { return x.code.slice(-1) === '0'; }), N = 15;
      var ra = {}, rb = {}, nm = {}; A.forEach(function (r, i) { ra[r[0]] = i + 1; nm[r[0]] = r[1]; }); B.forEach(function (r, i) { rb[r.code] = i + 1; nm[r.code] = r.name; });
      var codes = Object.keys(nm).filter(function (c) { return (ra[c] && ra[c] <= N) || (rb[c] && rb[c] <= N); });
      var rows = codes.map(function (c) { var a = ra[c] || null, b = rb[c] || null, d = a && b ? a - b : null; return { code: c, n: nm[c], a: a, b: b, hi: d != null && Math.abs(d) >= 3, c: d == null ? (b && b <= N ? '#D6362C' : '#9A9890') : d > 0 ? '#D6362C' : d < 0 ? '#2B6CD9' : '#9A9890' }; });
      var moved = rows.filter(function (r) { return r.a !== r.b; }).length;
      return Promise.all(rows.map(function (r) { return logo(r); })).then(function () {
        return { fn: 'slope', o: { kicker: '코스피 시총 순위 TOP ' + N, h1: "'" + y.slice(2) + '년 말과 지금, ' + moved + '곳 순위가 바뀌었다', rows: rows, n: N, la: "'" + y.slice(2) + '년 말', lb: '지금' } };
      });
    } },
    { id: 'profit', name: '돈 잘 버는 회사', icon: '₩', build: function () {
      return SCREEN().then(function (S) {
        var st = D.st, secs = [], col = {}, rows = Object.keys(S).filter(function (c) { return S[c].op != null && st[c]; }).sort(function (a, b) { return S[b].op - S[a].op; }).slice(0, 15).map(function (c) {
          var r = S[c], s = D.sec[c] || '기타'; if (!(s in col)) { col[s] = PAL[secs.length % PAL.length]; secs.push(s); }
          return { code: c, n: st[c].n, v: r.op, lab: jo(r.op), sub: s + ' · 영업이익률 ' + Math.round(r.margin) + '%', c: col[s] };
        });
        var y = String(+D.asof.slice(0, 4) - 1);
        return Promise.all(rows.map(function (r) { return logo(r); })).then(function () {
          return { fn: 'bars', o: { kicker: "'" + y.slice(2) + '년 영업이익 TOP 15', h1: '한국에서 돈 제일 잘 버는 회사는 ' + rows[0].n, rows: rows, legend: secs.slice(0, 6).map(function (s) { return [s, col[s]]; }) },
            src: "'" + y.slice(2) + '년 연간 실적 기준 (DART)' };
        });
      });
    } }

  ];

  /* ---------------------------------------------------------------- 화면 */
  function init() {
    var cv = $('card'); if (!cv) return;
    var X = cv.getContext('2d'), cur = null, last = null, cache = {};
    var bar = $('kinds');
    var GRP = [['한국 증시', ['treemap', 'ranked', 'breadth', 'contrib', 'dumbbell', 'radial', 'compare']], ['순위·역사', ['bump', 'slope', 'thennow', 'drawdown', 'monthly', 'calendar']],
      ['실적·배당', ['sankey', 'surprise', 'margin', 'profit', 'profitshare', 'scatter', 'dividend']], ['미국·세계', ['voronoi', 'usmap', 'usranked', 'world', 'rivals']],
      ['투자·주주', ['quilt', 'growth', 'waffle', 'holders']]], gbox = {};
    GRP.forEach(function (g) { var d = document.createElement('div'); d.className = 'kgrp'; d.innerHTML = '<span>' + g[0] + '</span>'; bar.appendChild(d); g[1].forEach(function (id) { gbox[id] = d; }); });
    CARDS.forEach(function (c) {
      var b = document.createElement('button'); b.className = 'preset'; b.dataset.k = c.id; b.setAttribute('aria-pressed', 'false');
      b.innerHTML = '<span aria-hidden="true">' + c.icon + '</span> ' + c.name; (gbox[c.id] || bar.lastChild).appendChild(b);
      b.addEventListener('click', function () { pick(c.id); });
    });
    function draw() { if (!last) return; X.setTransform(1, 0, 0, 1, 0, 0); window.__vc[last.fn](X, last.o); }
    var sel = {};
    function optsOf(c) { return typeof c.opts === 'function' ? c.opts() : c.opts; }
    function drawOpts(c) {
      var box = $('opts'), list = optsOf(c); box.innerHTML = ''; box.hidden = !list;
      if (!list) return;
      list.forEach(function (o) {
        var b = document.createElement('button'); b.className = 'chip'; b.textContent = o[1]; b.setAttribute('aria-pressed', String(sel[c.id] === o[0]));
        b.addEventListener('click', function () { sel[c.id] = o[0]; pick(c.id); }); box.appendChild(b);
      });
    }
    function pick(id) {
      cur = id;
      Array.prototype.forEach.call(bar.querySelectorAll('button'), function (b) { b.setAttribute('aria-pressed', String(b.dataset.k === id)); });
      var c = CARDS.filter(function (x) { return x.id === id; })[0], list = optsOf(c);
      if (list && !list.some(function (o) { return o[0] === sel[id]; })) sel[id] = list[0][0];
      drawOpts(c);
      var key = id + (list ? '|' + sel[id] : '');
      try { history.replaceState(null, '', '?k=' + id + (list ? '&o=' + encodeURIComponent(sel[id]) : '')); } catch (e) { /* 미리보기 */ }
      $('c-hint').textContent = '그리는 중…';
      (cache[key] || (cache[key] = c.build(list ? sel[id] : undefined))).then(function (r) {
        if (cur !== id || (list && key !== id + '|' + sel[id])) return;
        // 카드 아래 한 줄은 날짜만, 제목 아래 회색 설명 줄은 넣지 않는다
        var a = r.asof || (id === 'voronoi' ? D.us.asof : D.asof) || '', p = a.split('-');
        r.o.h2 = ''; r.o.src = r.src || (p.length === 3 ? "'" + p[0].slice(2) + '년 ' + (+p[1]) + '월 ' + (+p[2]) + '일 ' + (r.tail || '종가 기준') : '');
        last = r; last.name = c.name + (list ? '_' + list.filter(function (o) { return o[0] === sel[id]; })[0][1] : '');
        if (!r.auto) r.auto = { k: r.o.kicker, h: r.o.h1 };
        // 직접 고친 제목은 같은 카드·같은 선택지로 돌아와도 남는다
        var ed = edits[key]; r.o.kicker = ed ? ed.k : r.auto.k; r.o.h1 = ed ? ed.h : r.auto.h; last.key = key;
        $('c-kicker').value = r.o.kicker; $('c-title').value = r.o.h1;
        draw(); $('c-hint').textContent = c.name + ' · 최신 자료로 방금 다시 계산했어요. 윗줄·제목은 직접 고칠 수 있어요.';
      }).catch(function (e) { delete cache[key]; $('c-hint').textContent = '이 카드를 그리지 못했어요 (' + (e && e.message || e) + ').'; });
    }
    var edits = {};
    function onEdit() { if (!last) return; last.o.kicker = $('c-kicker').value; last.o.h1 = $('c-title').value; edits[last.key] = { k: last.o.kicker, h: last.o.h1 }; draw(); }
    $('c-kicker').addEventListener('input', onEdit); $('c-title').addEventListener('input', onEdit);
    $('c-reset').addEventListener('click', function () { if (!last) return; delete edits[last.key]; last.o.kicker = last.auto.k; last.o.h1 = last.auto.h; $('c-kicker').value = last.o.kicker; $('c-title').value = last.o.h1; draw(); });
    $('c-dl').addEventListener('click', function () {
      if (!last) return;
      var big = document.createElement('canvas'); big.width = 1080 * 3; big.height = 1350 * 3;
      var g = big.getContext('2d'); g.scale(3, 3); window.__vc[last.fn](g, last.o);
      big.toBlob(function (blob) {
        if (!blob) { alert('그림을 만들지 못했습니다. 새로고침 후 다시 눌러 주세요.'); return; }
        var a = document.createElement('a'); a.href = URL.createObjectURL(blob);
        a.download = '돈굴돈굴_' + last.name + '_' + D.asof + '.png';
        document.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 10000);
      }, 'image/png');
    });
    $('btn-mode').addEventListener('click', function () { var r = document.documentElement; r.setAttribute('data-mode', r.getAttribute('data-mode') === 'dark' ? 'light' : 'dark'); draw(); });
    $('c-hint').textContent = '자료 불러오는 중…';
    loadAll().then(function () { return document.fonts && document.fonts.ready; }).then(function () {
      $('src-pill').textContent = '인포그래픽 ' + CARDS.length + '종 · ' + md(D.asof) + ' 기준';
      var qs = new URLSearchParams(location.search), k0 = qs.get('k'); if (qs.get('o')) sel[k0] = qs.get('o');
      pick(CARDS.some(function (c) { return c.id === k0; }) ? k0 : CARDS[0].id);
    });
  }
  window.__ig = { cards: CARDS, data: D, load: loadAll };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
