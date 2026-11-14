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
  function hex(c) { c = c.replace('#', ''); return [0, 2, 4].map(function (k) { return parseInt(c.substr(k, 2), 16); }); }
  function shade(c, k) {                                  // 회사 색을 종이색 쪽으로 섞는다 (k=1 원래 색)
    var a = hex(c), b = hex(T.paper);
    return '#' + a.map(function (v, i) { return ('0' + Math.round(v * k + b[i] * (1 - k)).toString(16)).slice(-2); }).join('');
  }
  function lum(c) { var a = hex(c); return (0.299 * a[0] + 0.587 * a[1] + 0.114 * a[2]) / 255; }
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

    // 큰 도넛 하나: 최대주주 측은 사람별로 (회사 색을 진하게→옅게), 5% 주주 · 자기주식 · 기타
    var sg = segments(h, color), segs = [];
    // 1% 넘는 사람만 따로 (최대 3명), 나머지는 '그 외 특수관계인'
    var top = h.major.filter(function (p, i) { return i < 3 && (i === 0 || p.pct >= 1); });
    var restMaj = h.major.slice(top.length).reduce(function (s0, p) { return s0 + p.pct; }, 0);
    var boss = h.major.some(function (p) { return /본인/.test(p.rel); });
    top.forEach(function (p, i) {
      segs.push({ k: shortName(p.n), sub: !boss && i === 0 ? '최대주주' : relShort(p.rel), v: p.pct, c: shade(color, [1, 0.72, 0.5][i]), txt: i === 0 ? '#fff' : null });
    });
    if (restMaj >= 0.05) segs.push({ k: '그 외 특수관계인', v: restMaj, c: shade(color, 0.32) });
    sg.segs.forEach(function (x) { if (!x.main) segs.push(x); });

    var cx = CW / 2, cy = 650, ro = 330, ri = 205, a = -Math.PI / 2;
    segs.forEach(function (x) {
      var da = Math.max(0, x.v) / 100 * Math.PI * 2;
      if (da <= 0) return;
      X.beginPath(); X.arc(cx, cy, ro, a, a + da); X.arc(cx, cy, ri, a + da, a, true); X.closePath();
      X.fillStyle = x.c; X.fill();
      X.strokeStyle = T.paper; X.lineWidth = 5; X.stroke();          // 조각 사이 얇은 틈
      x.mid = a + da / 2; x.da = da;
      a += da;
    });
    // 조각 안 숫자 (충분히 큰 조각만)
    X.textAlign = 'center'; X.textBaseline = 'middle';
    segs.forEach(function (x) {
      if (!x.da || x.rest) return;
      var rr = (ro + ri) / 2, tx = cx + Math.cos(x.mid) * rr, ty = cy + Math.sin(x.mid) * rr;
      X.font = font(900, x.v >= 8 ? 34 : 28);
      if (X.measureText(pctTxt(x.v)).width + 18 > x.da * rr) return;   // 조각이 글자보다 좁으면 범례에만
      X.fillStyle = lum(x.c) < 0.6 ? '#fff' : T.ink;
      X.fillText(pctTxt(x.v), tx, ty);
    });
    X.textBaseline = 'alphabetic';
    X.fillStyle = T.inkSoft; X.font = font(700, 32); X.fillText('최대주주 측', cx, cy - 26);
    X.fillStyle = color; X.font = font(900, 96); X.fillText(pctTxt(sg.maj), cx, cy + 66);

    // 범례 두 줄씩
    var items = segs.filter(function (x) { return x.v > 0 && !x.rest; }).slice(0, 7)
      .concat(segs.filter(function (x) { return x.rest; }));
    var colW = (R - L - 40) / 2, rows = Math.ceil(items.length / 2), rowH = rows > 3 ? 54 : 60, ly = 1045;
    X.textBaseline = 'middle';
    items.forEach(function (x, i) {
      var col = i < rows ? 0 : 1, row = col ? i - rows : i;
      var x0 = L + col * (colW + 40), yy = ly + row * rowH;
      X.fillStyle = x.c; X.beginPath(); X.arc(x0 + 11, yy, 11, 0, 7); X.fill();
      X.textAlign = 'right'; X.font = font(800, 30); X.fillStyle = x.rest ? T.inkSoft : T.ink;
      var pt = pctTxt(x.v), pw = X.measureText(pt).width; X.fillText(pt, x0 + colW, yy);
      X.textAlign = 'left'; X.font = font(x.rest ? 700 : 800, 30); X.fillStyle = x.rest ? T.inkSoft : T.ink;
      var nm = fit(X, x.k, colW - 36 - pw - 16); X.fillText(nm, x0 + 36, yy);
    });
    X.textBaseline = 'alphabetic';

    // 바닥
    X.strokeStyle = T.rule; X.lineWidth = 2; X.beginPath(); X.moveTo(L, 1282); X.lineTo(R, 1282); X.stroke();
    var d = (h.asof || '').split('-');
    X.textAlign = 'left'; X.fillStyle = T.footer; X.font = font(700, 23);
    X.fillText('자료 : 금융감독원 DART · ' + (h.report || '').replace(/^20(\d\d) /, "'$1년 ") +
      (d.length === 3 ? ' (' + (+d[1]) + '월 ' + (+d[2]) + '일)' : ''), L, 1318);
    X.textAlign = 'right'; X.font = font(800, 24); X.fillText('@돈굴돈굴', R, 1318);
    X.restore();
    return { segs: segs };
  }

  window.__hd = { draw: draw, segments: segments, shortName: shortName };
})();
