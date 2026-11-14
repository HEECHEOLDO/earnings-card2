/* 주주현황 카드 (holders.html) — 2026-11
   자료: data/holders/{종목코드}.json  (collect_holders.py — DART 정기보고서, 분기마다 자동 갱신)
   {"name","asof","report","issued","treasury","major":[{n,rel,sh,pct}],"five":[{n,pct,dt}],"minor":{holders,pct,asof}} */
(function () {
  'use strict';
  var T = { paper: '#fafaf8', ink: '#101216', inkSoft: '#6B7078', rule: '#E6E4DD', track: '#ECEAE3', chip: '#F1EFEA',
            footer: '#3A3E46', treasury: '#A3A8AF', rest: '#E2DFD6' };
  var FF = "'Noto Sans KR', 'Noto Sans CJK KR', sans-serif";
  function font(w, px) { return w + ' ' + px + 'px ' + FF; }
  var CW = 1080, CH = 1350, L = 100, R = 980;
  // 5% 주주 색 — 회사 색 옆에 놓여도 구분되는 차분한 색
  var FIVE_C = ['#E0A43A', '#5B8DEF', '#8C6BD8', '#3FAE8C', '#D9677B', '#7A8794'];
  // 영문·긴 이름 줄이기 (DART 5% 보고자 이름은 띄어쓰기 없이 온다)
  var SHORT = [[/^국민연금/, '국민연금'], [/^BlackRock/i, '블랙록'], [/^CapitalResearch/i, '캐피탈 리서치'],
               [/^TheVanguard|^Vanguard/i, '뱅가드'], [/^막시모/, '막시모'], [/^StateStreet/i, '스테이트 스트리트'],
               [/^NorgesBank/i, '노르웨이 국부펀드'], [/^GIC/i, '싱가포르투자청(GIC)']];

  function shortName(s) {
    s = (s || '').split('\n')[0].replace(/㈜|\(주\)|주식회사/g, '').trim();
    for (var i = 0; i < SHORT.length; i++) if (SHORT[i][0].test(s)) return SHORT[i][1];
    return s;
  }
  function relShort(r) {
    r = (r || '').replace(/\s/g, '');
    if (/본인/.test(r)) return '최대주주';
    if (/친인척|친족/.test(r)) return '친인척';
    if (/계열/.test(r)) return '계열회사';
    if (/임원/.test(r)) return '임원';
    if (/재단/.test(r)) return '재단';
    return '특수관계인';
  }
  function pctTxt(v) { return (v >= 10 ? v.toFixed(1) : v.toFixed(2).replace(/0$/, '')) + '%'; }
  function people(n) {
    if (n >= 1e4) { var m = n / 1e4; return (m >= 100 ? Math.round(m).toLocaleString() : m.toFixed(1).replace(/\.0$/, '')) + '만 명'; }
    return n.toLocaleString() + '명';
  }
  function shares(n) {
    if (n >= 1e8) return (n / 1e8).toFixed(n >= 1e9 ? 1 : 2).replace(/\.?0+$/, '') + '억 주';
    return Math.round(n / 1e4).toLocaleString() + '만 주';
  }
  function fit(X, s, w) {
    if (X.measureText(s).width <= w) return s;
    while (s.length > 1 && X.measureText(s + '…').width > w) s = s.slice(0, -1);
    return s + '…';
  }

  var GRAIN = null;
  function grain(X) {
    if (!GRAIN) {
      GRAIN = document.createElement('canvas'); GRAIN.width = CW; GRAIN.height = CH;
      var g = GRAIN.getContext('2d'); g.fillStyle = T.paper; g.fillRect(0, 0, CW, CH);
      var im = g.getImageData(0, 0, CW, CH), d = im.data, seed = 7;
      for (var i = 0; i < d.length; i += 4) {
        seed = (seed * 16807) % 2147483647;
        var k = ((seed / 2147483647) - 0.5) * 14;
        d[i] += k; d[i + 1] += k; d[i + 2] += k;
      }
      g.putImageData(im, 0, 0);
    }
    X.drawImage(GRAIN, 0, 0);
  }

  /* 도넛 조각: 최대주주 측 · 5% 이상 주주 · 자기주식 · 기타 */
  function segments(h, color) {
    var maj = h.major.reduce(function (s, p) { return s + p.pct; }, 0);
    var segs = [{ k: '최대주주 측', v: maj, c: color, main: true }];
    (h.five || []).slice(0, 4).forEach(function (f, i) { segs.push({ k: shortName(f.n), v: f.pct, c: FIVE_C[i] }); });
    var tr = h.issued && h.treasury != null ? h.treasury / h.issued * 100 : 0;
    if (tr >= 0.05) segs.push({ k: '자기주식', v: tr, c: T.treasury });
    var used = segs.reduce(function (s, x) { return s + x.v; }, 0);
    segs.push({ k: '기타 주주', v: Math.max(0, 100 - used), c: T.rest, rest: true });
    return { segs: segs, maj: maj };
  }

  function draw(X, h, opt) {
    var color = opt.color || '#2B59C3';
    X.save(); X.textAlign = 'left'; X.textBaseline = 'alphabetic';
    grain(X);

    // 머리 (주가 추이 카드와 같은 자리·크기)
    var y0 = 205, nx = L;
    if (opt.logo) {
      X.save(); X.beginPath(); X.arc(L + 36, y0 - 30, 36, 0, 7); X.clip();
      X.fillStyle = '#fff'; X.fillRect(L, y0 - 66, 72, 72);
      X.drawImage(opt.logo, L, y0 - 66, 72, 72); X.restore();
      nx = L + 90;
    }
    var fs = 92; X.font = font(900, fs);
    while (fs > 52 && X.measureText(opt.name).width > R - nx) { fs -= 4; X.font = font(900, fs); }
    X.fillStyle = T.ink; X.fillText(opt.name, nx, y0);
    X.font = font(900, 56); X.fillText(opt.title || '주주 구성', L, y0 + 82);

    // 도넛
    var sg = segments(h, color), cx = L + 215, cy = 575, ro = 200, ri = 128, a = -Math.PI / 2;
    sg.segs.forEach(function (s) {
      var da = Math.max(0, s.v) / 100 * Math.PI * 2;
      if (da <= 0) return;
      X.beginPath(); X.arc(cx, cy, ro, a, a + da); X.arc(cx, cy, ri, a + da, a, true); X.closePath();
      X.fillStyle = s.c; X.fill();
      X.strokeStyle = T.paper; X.lineWidth = 4; X.stroke();          // 조각 사이 얇은 틈
      a += da;
    });
    X.textAlign = 'center';
    X.fillStyle = T.inkSoft; X.font = font(700, 26); X.fillText('최대주주 측', cx, cy - 18);
    X.fillStyle = T.ink; X.font = font(900, 64); X.fillText(pctTxt(sg.maj), cx, cy + 48);

    // 범례 (도넛 오른쪽)
    var lx = cx + ro + 70, ly = cy - (sg.segs.length - 1) * 58 / 2;
    X.textBaseline = 'middle';
    sg.segs.forEach(function (s, i) {
      var yy = ly + i * 58;
      X.fillStyle = s.c; X.beginPath(); X.arc(lx + 10, yy, 10, 0, 7); X.fill();
      X.textAlign = 'left'; X.fillStyle = s.rest ? T.inkSoft : T.ink; X.font = font(s.main ? 800 : 700, 30);
      X.fillText(fit(X, s.k, R - lx - 150), lx + 34, yy);
      X.textAlign = 'right'; X.font = font(800, 30); X.fillStyle = s.main ? color : (s.rest ? T.inkSoft : T.ink);
      X.fillText(pctTxt(s.v), R, yy);
    });
    X.textBaseline = 'alphabetic';

    // 주요 주주 (사람·회사별)
    var boss = h.major.some(function (p) { return /본인/.test(p.rel); });   // '본인' 줄이 없으면 가장 큰 주주가 최대주주
    var list = h.major.map(function (p, i) { return { n: shortName(p.n), rel: !boss && i === 0 ? '최대주주' : relShort(p.rel), pct: p.pct, main: true }; })
      .concat((h.five || []).map(function (f) { return { n: shortName(f.n), rel: '5% 이상 주주', pct: f.pct }; }))
      .sort(function (p, q) { return q.pct - p.pct; }).slice(0, 5);
    var ty = 822;
    X.textAlign = 'left'; X.fillStyle = T.ink; X.font = font(800, 32); X.fillText('주요 주주', L, ty);
    X.strokeStyle = T.rule; X.lineWidth = 2; X.beginPath(); X.moveTo(L, ty + 22); X.lineTo(R, ty + 22); X.stroke();
    var mx = list.length ? list[0].pct : 1, bx = 560, bw = R - 120 - bx;
    list.forEach(function (p, i) {
      var yy = ty + 68 + i * 52;
      X.textAlign = 'left'; X.fillStyle = T.ink; X.font = font(800, 29);
      var nm = fit(X, p.n, 300); X.fillText(nm, L, yy);
      var nw = X.measureText(nm).width;
      X.fillStyle = T.inkSoft; X.font = font(600, 21);
      if (L + nw + 12 + X.measureText(p.rel).width < bx - 16) X.fillText(p.rel, L + nw + 12, yy - 2);
      X.fillStyle = T.track; X.fillRect(bx, yy - 19, bw, 18);
      X.fillStyle = p.main ? color : FIVE_C[(h.five || []).findIndex(function (f) { return shortName(f.n) === p.n; })] || '#7A8794';
      X.fillRect(bx, yy - 19, Math.max(4, bw * p.pct / mx), 18);
      X.textAlign = 'right'; X.fillStyle = T.ink; X.font = font(800, 29); X.fillText(pctTxt(p.pct), R, yy);
    });

    // 칩: 소액주주 · 자기주식 · 발행주식
    var chips = [];
    if (h.minor && h.minor.holders) chips.push(['소액주주', people(h.minor.holders)]);
    if (h.issued && h.treasury != null) chips.push(['자기주식', pctTxt(h.treasury / h.issued * 100)]);
    if (h.issued) chips.push(['발행주식', shares(h.issued)]);
    var cy0 = 1150, gap = 18, cw = (R - L - gap * (chips.length - 1)) / Math.max(1, chips.length);
    chips.forEach(function (c, i) {
      var x = L + i * (cw + gap);
      X.fillStyle = T.chip; X.beginPath(); X.roundRect ? X.roundRect(x, cy0, cw, 104, 14) : X.rect(x, cy0, cw, 104); X.fill();
      X.textAlign = 'left'; X.fillStyle = T.inkSoft; X.font = font(700, 24); X.fillText(c[0], x + 26, cy0 + 40);
      X.fillStyle = T.ink; X.font = font(900, 38); X.fillText(c[1], x + 26, cy0 + 86);
    });

    // 바닥
    X.strokeStyle = T.rule; X.lineWidth = 2; X.beginPath(); X.moveTo(L, 1282); X.lineTo(R, 1282); X.stroke();
    var d = (h.asof || '').split('-');
    X.textAlign = 'left'; X.fillStyle = T.footer; X.font = font(700, 23);
    X.fillText('자료 : 금융감독원 DART · ' + (h.report || '').replace(/^20(\d\d) /, "'$1년 ") +
      (d.length === 3 ? ' (' + (+d[1]) + '월 ' + (+d[2]) + '일)' : ''), L, 1318);
    X.textAlign = 'right'; X.font = font(800, 24); X.fillText('@돈굴돈굴', R, 1318);
    X.restore();
    return { segs: sg.segs, list: list };
  }

  window.__hd = { draw: draw, segments: segments, shortName: shortName };
})();
