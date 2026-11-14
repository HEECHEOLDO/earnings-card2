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
    X.font = font(900, 56); X.fillText(opt.title || '주주 구성 현황', L, y0 + 82);

    // 큰 도넛 하나 (연합뉴스 주주구성 그래픽처럼 조각 위에 이름·지분을 바로 쓴다)
    // 최대주주 측은 사람별로 (회사 색을 진하게→옅게), 그다음 5% 주주 · 자기주식 · 기타
    var sg = segments(h, color), segs = [];
    var top = h.major.filter(function (p, i) { return i < 4 && (i === 0 || p.pct >= 1); });
    var restMaj = h.major.slice(top.length).reduce(function (s0, p) { return s0 + p.pct; }, 0);
    top.forEach(function (p, i) { segs.push({ k: shortName(p.n), v: p.pct, c: shade(color, [1, 0.78, 0.6, 0.45][i]) }); });
    if (restMaj >= 0.05) segs.push({ k: '그 외 특수관계인', v: restMaj, c: shade(color, 0.3) });
    sg.segs.forEach(function (x) { if (!x.main) segs.push(x); });

    var cx = L + 300, cy = 740, ro = 300, ri = 135, a = -Math.PI / 2;   // 왼쪽에 두고 오른쪽을 이름표 자리로
    segs.forEach(function (x) {
      var da = Math.max(0, x.v) / 100 * Math.PI * 2;
      x.a0 = a; x.da = da; x.mid = a + da / 2; a += da;
      if (da <= 0) return;
      X.beginPath(); X.arc(cx, cy, ro, x.a0, x.a0 + da); X.arc(cx, cy, ri, x.a0 + da, x.a0, true); X.closePath();
      X.fillStyle = x.c; X.fill();
      X.strokeStyle = T.paper; X.lineWidth = 4; X.stroke();          // 조각 사이 얇은 틈
    });

    // 조각 안에 들어가면 안에 (이름 위 · 지분 아래), 아니면 바깥에 꺾은 선으로
    var outs = [];
    X.textAlign = 'center'; X.textBaseline = 'middle';
    segs.forEach(function (x) {
      if (!(x.da > 0)) return;
      var rr = x.rest ? (ro + ri) / 2 + 20 : (ro + ri) / 2 + 22, pt = pctTxt(x.v);
      var nfs = 28, pfs = x.v >= 10 ? 46 : 38;
      X.font = font(800, nfs); var nw = X.measureText(x.k).width;
      X.font = font(900, pfs); var pw = X.measureText(pt).width;
      var room = x.da * rr;                                        // 그 반지름에서 조각 폭
      if (room > Math.max(nw, pw) + 26 && x.da > 0.32) {
        var tx = cx + Math.cos(x.mid) * rr, ty = cy + Math.sin(x.mid) * rr;
        var ink = lum(x.c) < 0.62 ? '#fff' : (x.rest ? T.inkSoft : T.ink);
        X.fillStyle = ink; X.font = font(800, nfs); X.fillText(x.k, tx, ty - 24);
        X.font = font(900, pfs); X.fillText(pt, tx, ty + 18);
      } else outs.push(x);
    });
    // 바깥 이름표: 모두 오른쪽 한 줄로 (이름 위 · 지분 아래), 위아래로 겹치지 않게 민다
    var col = cx + ro + 60, GAP = 74;
    var Lb = outs.map(function (x) { return { x: x, y: cy + Math.sin(x.mid) * (ro + 20) }; })
      .sort(function (p, q) { return p.y - q.y; });
    for (var k = 1; k < Lb.length; k++) if (Lb[k].y - Lb[k - 1].y < GAP) Lb[k].y = Lb[k - 1].y + GAP;
    var over = Lb.length ? Lb[Lb.length - 1].y - 1225 : 0;
    if (over > 0) Lb.forEach(function (p) { p.y -= over; });
    var under = Lb.length ? 330 - Lb[0].y : 0;
    if (under > 0) Lb.forEach(function (p) { p.y += under; });
    Lb.forEach(function (p) {
      var x = p.x, ex = cx + Math.cos(x.mid) * (ro + 4), ey = cy + Math.sin(x.mid) * (ro + 4);
      X.strokeStyle = '#A9AEB5'; X.lineWidth = 2;
      X.beginPath(); X.moveTo(ex, ey); X.lineTo(col - 34, p.y); X.lineTo(col - 12, p.y); X.stroke();
      X.fillStyle = x.c; X.beginPath(); X.arc(col + 9, p.y - 16, 9, 0, 7); X.fill();
      X.textAlign = 'left'; X.textBaseline = 'middle';
      X.font = font(700, 26); X.fillStyle = T.inkSoft; X.fillText(fit(X, x.k, R + 40 - col - 28), col + 28, p.y - 16);
      X.font = font(900, 34); X.fillStyle = T.ink; X.fillText(pctTxt(x.v), col + 28, p.y + 20);
    });
    X.textBaseline = 'middle'; X.textAlign = 'center';
    X.fillStyle = T.inkSoft; X.font = font(700, 24); X.fillText('최대주주 측', cx, cy - 26);
    X.fillStyle = color; X.font = font(900, 50); X.fillText(pctTxt(sg.maj), cx, cy + 20);
    X.textBaseline = 'alphabetic';

    // 바닥
    X.strokeStyle = T.rule; X.lineWidth = 2; X.beginPath(); X.moveTo(L, 1282); X.lineTo(R, 1282); X.stroke();
    var d = (h.asof || '').split('-');
    X.textAlign = 'left'; X.fillStyle = T.footer; X.font = font(700, 23);
    X.fillText('자료 : ' + (h.report || '').replace(/^20(\d\d) /, "'$1년 ").replace(/보고서$/, ' 보고서'), L, 1318);
    X.textAlign = 'right'; X.font = font(800, 24); X.fillText('@돈굴돈굴', R, 1318);
    X.restore();
    return { segs: segs };
  }

  window.__hd = { draw: draw, segments: segments, shortName: shortName };
})();
