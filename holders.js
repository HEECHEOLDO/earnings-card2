/* 주주현황 카드 (holders.html) — 2026-11
   자료: data/holders/{종목코드}.json  (collect_holders.py — DART 정기보고서, 분기마다 자동 갱신)
   {"name","asof","report","issued","treasury","major":[{n,rel,sh,pct}],"five":[{n,pct,dt}],"minor":{holders,pct,asof}} */
(function () {
  'use strict';
  var T = { paper: '#fafaf8', ink: '#101216', inkSoft: '#6B7078', rule: '#E6E4DD', track: '#ECEAE3', chip: '#F1EFEA',
            footer: '#3A3E46', treasury: '#A3A8AF', rest: '#E2DFD6' };
  var LIGHT = Object.assign({ dark: false }, T), DARK = { dark: true, paper: '#17191D', ink: '#F3F2EE', inkSoft: '#A2A7AF', rule: '#2E3137', track: '#2A2D33', chip: '#212429', footer: '#C9CCD1', treasury: '#646A73', rest: '#34373E' };
  function theme(dark) { Object.assign(T, dark ? DARK : LIGHT); }   // 카드 바탕: 밝게 / 어둡게
  var FF = "'Noto Sans KR', 'Noto Sans CJK KR', sans-serif";
  function font(w, px) { return w + ' ' + px + 'px ' + FF; }
  var CW = 1080, CH = 1350, L = 100, R = 980;
  // 5% 주주 색 — 회사 색 옆에 놓여도 구분되는 차분한 색
  var FIVE_C = ['#E0A43A', '#5B8DEF', '#8C6BD8', '#3FAE8C', '#D9677B', '#7A8794'];
  // 영문·긴 이름 줄이기 (DART 5% 보고자 이름은 띄어쓰기 없이 온다)
  var SHORT = [[/^국민연금/, '국민연금'], [/^BlackRock/i, '블랙록'], [/^CapitalResearch/i, '캐피탈 리서치'],
               [/^TheVanguard|^Vanguard/i, '뱅가드'], [/^막시모/, '막시모'], [/^StateStreet/i, '스테이트 스트리트'],
               [/^NorgesBank/i, '노르웨이 국부펀드'], [/^GIC\b/i, '싱가포르투자청'], [/^JP ?Morgan|^J\.P\. ?MORGAN/i, 'JP모건'],
               [/^Manulife/i, '매뉴라이프'], [/^Allianz/i, '알리안츠'], [/^Fidelity|^피델리티/i, '피델리티'], [/^Yuanta/i, '유안타'],
               [/^Orbis/i, '오비스'], [/^Silchester/i, '실체스터'], [/^VanEck/i, '반에크'], [/^Federated ?Hermes/i, '페더레이티드 허미스'],
               [/^Dalton/i, '달튼'], [/^Aramco/i, '아람코'], [/^Hanwha Energy/i, '한화에너지'], [/^Hanwha Impact/i, '한화임팩트'],
               [/^Phillip Capital/i, '필립캐피탈'], [/^Templeton/i, '템플턴'], [/^Morgan ?Stanley/i, '모건스탠리'],
               [/^Goldman/i, '골드만삭스'], [/^Citi/i, '씨티'], [/^UBS\b/i, 'UBS'], [/^Nomura/i, '노무라']];
  // 이름 뒤에 붙는 회사 형태 말 (뜻은 그대로라 빼도 된다)
  var LEGAL = /[\s,.]*(Co\.?,?\s*Ltd\.?|Company\s+Limited|Limited|Ltd\.?|Corporation|Corp\.?|Incorporated|Inc\.?|L\.?L\.?C\.?|L\.?L\.?P\.?|L\.?P\.?|PLC|P\.?T\.?E\.?|Pte\.?|B\.?V\.?|GmbH|S\.?A\.?|AG|AS|N\.?V\.?|Private|Company|Co\.?)\s*$/i;

  function shortName(s) {
    s = (s || '').split('\n')[0]
      .replace(/\(주\d*\)$/, '').replace(/㈜|\(주\)|주식회사|\(유\)|유한회사|\(사\)|재단법인|사단법인/g, '').trim();
    for (var i = 0; i < SHORT.length; i++) if (SHORT[i][0].test(s)) return SHORT[i][1];
    // 띄어쓰기 없이 붙은 영문 이름 나누기 (CapitalResearchandManagementCompany → Capital Researchand …)
    if (/^[A-Za-z0-9,.&()'\- ]+$/.test(s) && !/\s/.test(s) && s.length > 12) s = s.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/([A-Z]{2,})([A-Z][a-z])/g, '$1 $2').replace(/,/g, ', ');
    // 회사 형태 말을 뒤에서부터 걷어낸다 (Starlink Investment L.P. → Starlink Investment)
    for (var k = 0; k < 4; k++) { var t = s.replace(LEGAL, '').trim(); if (t === s || t.length < 2) break; s = t; }
    s = s.replace(/[\s,.]+$/, '').replace(/^\(\s*\)/, '').trim();
    // 대문자만 쓴 영문은 첫 글자만 크게 (SON ROBERT INHO → Son Robert Inho, 너비도 준다)
    if (/^[A-Z0-9 .,&'\-()]+$/.test(s) && /[A-Z]{4}/.test(s)) s = s.toLowerCase().replace(/(^|[\s\-(])([a-z])/g, function (m, a, b) { return a + b.toUpperCase(); });
    // 한글로 적은 외국 회사 형태 말 (…리미티드·…,인크·…,엘피) · 법인 앞말 (사회복지법인 ○○재단 → ○○재단)
    s = s.replace(/^유\)\s*/, '').replace(/^(사회복지법인|학교법인|의료법인|재단법인|사단법인)\s+/, '')
         .replace(/[\s,]*(리미티드|인크|엘피|엘엘씨|엘엘피|코퍼레이션|컴퍼니|피엘씨|게엠베하)$/, '').trim();
    // 국내 펀드 이름 줄이기 (…기관전용사모투자·…사모투자 → PEF, …투자목적회사 → SPC)
    s = s.replace(/(기관전용)?사모투자(합자회사|전문회사)?$/, ' PEF').replace(/투자목적회사$/, ' SPC')
    s = s.replace(/\s*기업재무안정\s*사모투자\s*합자회사$|\s*사모투자\s*합자회사$|\s*사모투자전문회사$/, ' PEF')
         .replace(/\s*신기술(사업)?투자조합\s*(제\s*)?(\d+)\s*호$/, ' 신기술조합 $3호').replace(/\s*신기술조합\s*제\s*(\d+)\s*호$/, ' 신기술조합 $1호');
    return s.replace(/\s{2,}/g, ' ').trim();
  }
  // 정해진 너비에 이름 넣기: 글자를 조금 줄여 보고, 그래도 길면 뒤 낱말부터 빼고, 마지막에만 '…'
  function fitName(X, s, w, weight, sizes) {
    for (var i = 0; i < sizes.length; i++) {
      X.font = font(weight, sizes[i]);
      if (X.measureText(s).width <= w) return { t: s, f: sizes[i] };
    }
    var f = sizes[sizes.length - 1]; X.font = font(weight, f);
    var words = s.split(' ');
    while (words.length > 1) {
      words.pop();
      var t = words.join(' ').replace(/[\s,\-&]+$/, '');
      if (X.measureText(t).width <= w) return { t: t, f: f };
    }
    return { t: fit(X, s, w), f: f };
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
  // 바깥 이름표용: 한 줄(26→20px) → 두 줄(22px, 띄어쓰기에서 나누고 없으면 글자 가운데) → 그래도 길면 뒤를 줄임
  function fitName2(X, s, w) {
    var one = [26, 24, 22];
    for (var i = 0; i < one.length; i++) { X.font = font(700, one[i]); if (X.measureText(s).width <= w) return { lines: [s], f: one[i] }; }
    var f = 22; X.font = font(700, f);
    var best = null, words = s.split(' ');
    for (var c = 1; c < words.length; c++) {                     // 띄어쓰기에서 나누기: 두 줄 다 들어가고 길이가 고른 곳
      var a = words.slice(0, c).join(' '), b = words.slice(c).join(' ');
      var wa = X.measureText(a).width, wb = X.measureText(b).width;
      if (wa <= w && wb <= w && (!best || Math.abs(wa - wb) < best.d)) best = { lines: [a, b], d: Math.abs(wa - wb) };
    }
    if (best) return { lines: best.lines, f: f };
    if (words.length > 2) {                                      // 낱말이 많은 영문: 뒤 낱말을 빼 가며 두 줄에 맞춘다 (낱말 가운데서 끊지 않게)
      for (var n = words.length - 1; n >= 2; n--) {
        var ws = words.slice(0, n);
        for (var c3 = 1; c3 < ws.length; c3++) {
          var a3 = ws.slice(0, c3).join(' '), b3 = ws.slice(c3).join(' ').replace(/[\s,\-&]+$/, '');
          if (X.measureText(a3).width <= w && X.measureText(b3).width <= w) return { lines: [a3, b3], f: f };
        }
      }
    }
    for (var cut = Math.ceil(s.length / 2), t = 0; t < 6; t++) {    // 띄어쓰기 없는 긴 한글: 가운데쯤에서 나누기
      var c2 = cut + (t % 2 ? -1 : 1) * Math.ceil(t / 2), a2 = s.slice(0, c2), b2 = s.slice(c2);
      if (X.measureText(a2).width <= w && X.measureText(b2).width <= w) return { lines: [a2, b2], f: f };
    }
    var r = fitName(X, s, w * 2 - 20, 700, [20]);               // 두 줄로도 안 되면: 긴 한 줄을 줄인 뒤 다시 나눈다
    var h1 = Math.ceil(r.t.length / 2);
    X.font = font(700, 20);
    if (X.measureText(r.t.slice(0, h1)).width <= w && X.measureText(r.t.slice(h1)).width <= w) return { lines: [r.t.slice(0, h1), r.t.slice(h1)], f: 20 };
    return { lines: [fit(X, s, w)], f: 20 };
  }
  function fit(X, s, w) {
    if (X.measureText(s).width <= w) return s;
    while (s.length > 1 && X.measureText(s + '…').width > w) s = s.slice(0, -1);
    return s + '…';
  }

  // 어두운 바탕에서 남색·검정 같은 진한 회사 색은 안 보이니 밝힌다
  function forDark(c) {
    var h = c.replace('#', ''), a = [0, 2, 4].map(function (k) { return parseInt(h.substr(k, 2), 16) / 255; });
    if (!T.dark || a.some(isNaN)) return c;
    var lu = 0.299 * a[0] + 0.587 * a[1] + 0.114 * a[2];
    if (lu >= 0.3) return c;                                   // 빨강·초록·노랑 같은 밝은 색은 그대로
    var mx = Math.max.apply(null, a), mn = Math.min.apply(null, a), l = (mx + mn) / 2, d = mx - mn, hh = 0, sat = 0;
    if (d) {
      sat = d / (1 - Math.abs(2 * l - 1));
      hh = mx === a[0] ? ((a[1] - a[2]) / d) % 6 : mx === a[1] ? (a[2] - a[0]) / d + 2 : (a[0] - a[1]) / d + 4;
      hh *= 60; if (hh < 0) hh += 360;
    }
    l = 0.64; sat = Math.min(1, Math.max(sat, d ? 0.6 : 0));   // 색은 그대로, 밝기만 올린다 (남색 → 선명한 파랑)
    var C = (1 - Math.abs(2 * l - 1)) * sat, x = C * (1 - Math.abs((hh / 60) % 2 - 1)), m = l - C / 2;
    var rgb = hh < 60 ? [C, x, 0] : hh < 120 ? [x, C, 0] : hh < 180 ? [0, C, x] : hh < 240 ? [0, x, C] : hh < 300 ? [x, 0, C] : [C, 0, x];
    return '#' + rgb.map(function (v) { return ('0' + Math.round((v + m) * 255).toString(16)).slice(-2); }).join('');
  }
  // 바탕 질감: 밝은 종이 / 어두운 판 (아주 옅은 빛 번짐 + 고운 입자 + 드문 반짝임)
  var GRAINS = {};
  function grain(X) {
    var key = T.paper;
    if (!GRAINS[key]) {
      var cv = document.createElement('canvas'); cv.width = CW; cv.height = CH;
      cv.__noTheme = true;                          // 질감은 늘 밝은 종이로 만들고, 다크 모드면 card-theme.js 가 쓸 때 바꾼다
      var g = cv.getContext('2d'); g.fillStyle = T.paper; g.fillRect(0, 0, CW, CH);
      var dark = T.dark;
      if (dark) {                                   // 왼쪽 위에서 아주 옅게 빛이 번지는 느낌
        var rg = g.createRadialGradient(CW * 0.28, CH * 0.12, 40, CW * 0.45, CH * 0.35, CH * 0.95);
        rg.addColorStop(0, 'rgba(255,255,255,0.075)'); rg.addColorStop(1, 'rgba(255,255,255,0)');
        g.fillStyle = rg; g.fillRect(0, 0, CW, CH);
        var vg = g.createRadialGradient(CW / 2, CH / 2, CH * 0.45, CW / 2, CH / 2, CH * 0.85);
        vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,0.28)');
        g.fillStyle = vg; g.fillRect(0, 0, CW, CH);
      }
      var im = g.getImageData(0, 0, CW, CH), d = im.data, seed = 7, amp = dark ? 16 : 14;
      for (var i = 0; i < d.length; i += 4) {
        seed = (seed * 16807) % 2147483647;
        var r = seed / 2147483647, k = (r - 0.5) * amp;
        if (dark && r > 0.9993) k += 38;            // 드문 밝은 입자 (돌판·종이 섬유 느낌)
        d[i] += k; d[i + 1] += k; d[i + 2] += k;
      }
      g.putImageData(im, 0, 0);
      GRAINS[key] = cv;
    }
    X.drawImage(GRAINS[key], 0, 0);
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
    var color;
    X.save(); X.textAlign = 'left'; X.textBaseline = 'alphabetic';
    theme(!!opt.dark); grain(X); color = forDark(opt.color || '#2B59C3');

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
    function own(k) {                                           // 회사 이름으로 시작하는 주주 (케이피에프 사내근로복지기금 → 사내근로복지기금)
      var nm = (h.name || '').trim();
      return nm && k.indexOf(nm + ' ') === 0 && k.length > nm.length + 3 ? k.slice(nm.length + 1) : k;
    }
    var top = h.major.filter(function (p, i) { return i < 4 && (i === 0 || p.pct >= 1); });
    var restMaj = h.major.slice(top.length).reduce(function (s0, p) { return s0 + p.pct; }, 0);
    top.forEach(function (p, i) { segs.push({ k: own(shortName(p.n)), v: p.pct, c: shade(color, [1, 0.78, 0.6, 0.45][i]) }); });
    if (restMaj >= 0.05) segs.push({ k: '그 외 특수관계인', v: restMaj, c: shade(color, 0.3) });
    sg.segs.forEach(function (x) { if (!x.main) segs.push(x); });

    var cx = L + 300, cy = 740, ro = 300, ri = 135;                 // 왼쪽에 두고 오른쪽을 이름표 자리로

    // 글자 상자(두 줄)의 네 귀퉁이와 변 가운데가 모두 그 조각 안(테두리에서 10px 안쪽)에 들어가야 안에 쓴다
    function inside(x, bx, by, w, hh) {
      var pts = [[bx - w / 2, by - hh / 2], [bx + w / 2, by - hh / 2], [bx - w / 2, by + hh / 2], [bx + w / 2, by + hh / 2],
                 [bx, by - hh / 2], [bx, by + hh / 2], [bx - w / 2, by], [bx + w / 2, by]];
      return pts.every(function (q) {
        var dx = q[0] - cx, dy = q[1] - cy, r = Math.sqrt(dx * dx + dy * dy);
        if (r < ri + 10 || r > ro - 10) return false;
        var ang = Math.atan2(dy, dx), m = 10 / r;
        while (ang < x.a0) ang += Math.PI * 2;
        while (ang > x.a0 + Math.PI * 2) ang -= Math.PI * 2;
        return ang >= x.a0 + m && ang <= x.a0 + x.da - m;
      });
    }
    // 조각 안 글자 자리 찾기: 안 들어가면 글자를 조금씩 줄이고, 고리 두께 안에서 가운데→바깥→안쪽으로 옮겨 본다
    var MW = {};
    function mw(f, t) { var k = f + '|' + t; if (MW[k] === undefined) { X.font = f; MW[k] = X.measureText(t).width; } return MW[k]; }
    function fit(x) {
      if (!(x.da > 0)) return null;
      var pt = pctTxt(x.v), sizes = [[28, x.v >= 10 ? 46 : 38], [25, 36], [22, 30]], radii = [0.5, 0.56, 0.44, 0.62, 0.38];
      for (var si = 0; si < sizes.length; si++) {
        var nfs = sizes[si][0], pfs = sizes[si][1];
        var w = Math.max(mw(font(800, nfs), x.k), mw(font(900, pfs), pt)), hh = nfs * 0.9 + pfs * 0.85 + 8;
        for (var k2 = 0; k2 < radii.length; k2++) {
          var rr = ri + (ro - ri) * radii[k2], tx = cx + Math.cos(x.mid) * rr, ty = cy + Math.sin(x.mid) * rr;
          if (inside(x, tx, ty, w, hh)) return { nfs: nfs, pfs: pfs, tx: tx, ty: ty, hh: hh, pt: pt };
        }
      }
      return null;
    }
    function place(start) {
      var a = start;
      segs.forEach(function (x) { var da = Math.max(0, x.v) / 100 * Math.PI * 2; x.a0 = a; x.da = da; x.mid = a + da / 2; a += da; });
    }
    // 도는 각도 고르기: 조각 밖 이름표가 왼쪽(도넛 뒤편)에 생기지 않게, 그다음 밖 이름표가 적게.
    // 처음엔 '기타 주주'가 아닌 조각들의 가운데를 3시 방향에 둔다 (작은 조각이 오른쪽 이름표 칸 쪽에 모인다)
    var named = segs.filter(function (x) { return !x.rest; }).reduce(function (s0, x) { return s0 + Math.max(0, x.v); }, 0);
    var base = -named / 100 * Math.PI, best = base, bestScore = 1e9;
    for (var step = 0; step < 72; step++) {
      var off = (step % 2 ? 1 : -1) * Math.ceil(step / 2) * Math.PI / 36;    // 0, +5°, -5°, +10° … 처음 자리에서 가까운 것부터
      place(base + off);
      var sc = 0;
      segs.forEach(function (x) { if (x.da > 0 && !fit(x)) sc += Math.cos(x.mid) < 0.15 ? 100 : 1; });
      if (sc < bestScore) { bestScore = sc; best = base + off; }
      if (sc === 0) break;
    }
    place(best);
    segs.forEach(function (x) {
      if (!(x.da > 0)) return;
      X.beginPath(); X.arc(cx, cy, ro, x.a0, x.a0 + x.da); X.arc(cx, cy, ri, x.a0 + x.da, x.a0, true); X.closePath();
      X.fillStyle = x.c; X.fill();
      X.strokeStyle = T.paper; X.lineWidth = 4; X.stroke();          // 조각 사이 얇은 틈
    });

    // 조각 안에 들어가면 안에 (이름 위 · 지분 아래), 아니면 바깥에 꺾은 선으로
    var outs = [];
    X.textAlign = 'center'; X.textBaseline = 'middle';
    segs.forEach(function (x) {
      if (!(x.da > 0)) return;
      var f = fit(x);
      if (!f) { outs.push(x); return; }
      var ink = x.rest ? T.inkSoft : (lum(x.c) < 0.62 ? '#fff' : '#111214');
      X.fillStyle = ink; X.font = font(800, f.nfs); X.fillText(x.k, f.tx, f.ty - f.hh / 2 + f.nfs * 0.45);
      X.font = font(900, f.pfs); X.fillText(f.pt, f.tx, f.ty + f.hh / 2 - f.pfs * 0.42);
    });
    // 바깥 이름표: 모두 오른쪽 한 줄로 (이름 위 · 지분 아래), 위아래로 겹치지 않게 민다
    var col = cx + ro + 60, NW = R + 40 - col - 28;
    var shown = [];
    // 이름이 한 줄에 안 들어가면 두 줄로 (그래도 길 때만 뒤 낱말 빼기·'…') — 이름표 높이가 달라지니 간격도 그에 맞춘다
    var Lb = outs.map(function (x) {
      var nm = fitName2(X, x.k, NW);
      return { x: x, nm: nm, hgt: nm.lines.length * (nm.f + 4) + 40, y: cy + Math.sin(x.mid) * (ro + 20) };
    }).sort(function (p, q) { return p.y - q.y; });
    for (var k = 1; k < Lb.length; k++) {
      var need = (Lb[k - 1].hgt + Lb[k].hgt) / 2 + 6;
      if (Lb[k].y - Lb[k - 1].y < need) Lb[k].y = Lb[k - 1].y + need;
    }
    var over = Lb.length ? Lb[Lb.length - 1].y + Lb[Lb.length - 1].hgt / 2 - 1250 : 0;   // 바닥 줄(1282) 위까지
    if (over > 0) Lb.forEach(function (p) { p.y -= over; });
    var under = Lb.length ? 318 - (Lb[0].y - Lb[0].hgt / 2) : 0;                          // 제목 아래부터
    if (under > 0) Lb.forEach(function (p) { p.y += under; });
    Lb.forEach(function (p) {
      var x = p.x, ex = cx + Math.cos(x.mid) * (ro + 4), ey = cy + Math.sin(x.mid) * (ro + 4);
      X.strokeStyle = T.dark ? '#5C6169' : '#A9AEB5'; X.lineWidth = 2;
      if (Math.cos(x.mid) < 0.15) {                                  // 왼쪽 조각: 도넛 바깥 둘레를 따라 오른쪽으로 돌아 나온다 (도넛을 가로지르지 않게)
        var m0 = Math.atan2(Math.sin(x.mid), Math.cos(x.mid)), down = m0 >= 0, rA = ro + 16;
        var tgt = down ? 1.15 : -1.15;                                // 아래쪽이면 5시, 위쪽이면 1시 방향까지
        X.beginPath(); X.moveTo(ex, ey); X.lineTo(cx + Math.cos(m0) * rA, cy + Math.sin(m0) * rA);
        X.arc(cx, cy, rA, m0, tgt, down);                            // 아래: 시계 반대로(각도 줄며) · 위: 시계 방향
        X.stroke();
        ex = cx + Math.cos(tgt) * rA; ey = cy + Math.sin(tgt) * rA;
      }
      X.strokeStyle = T.dark ? '#5C6169' : '#A9AEB5'; X.lineWidth = 2;
      X.beginPath(); X.moveTo(ex, ey); X.lineTo(col - 34, p.y); X.lineTo(col - 12, p.y); X.stroke();
      var nm = p.nm, lh = nm.f + 4, top0 = p.y - p.hgt / 2 + lh / 2;
      X.fillStyle = x.c; X.beginPath(); X.arc(col + 9, top0, 9, 0, 7); X.fill();
      X.textAlign = 'left'; X.textBaseline = 'middle';
      shown.push([x.k, nm.lines.join(' ')]);
      X.font = font(700, nm.f); X.fillStyle = T.inkSoft;
      nm.lines.forEach(function (ln, li) { X.fillText(ln, col + 28, top0 + li * lh); });
      X.font = font(900, 34); X.fillStyle = T.ink; X.fillText(pctTxt(x.v), col + 28, p.y + p.hgt / 2 - 18);
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
    return { segs: segs, shown: shown, top: Lb.length ? Lb[0].y - Lb[0].hgt / 2 : null, bot: Lb.length ? Lb[Lb.length - 1].y + Lb[Lb.length - 1].hgt / 2 : null, outs: outs.length, left: outs.filter(function (x) { return Math.cos(x.mid) < 0.15; }).length };
  }

  /* ------------------------------------------------------------ 화면 (holders.html) */
  var $ = function (id) { return document.getElementById(id); };
  var LOGO = {};
  function logoImg(code, cb) {
    var src = './logo/kr/' + code + '.png';
    if (LOGO[src] !== undefined) { cb(LOGO[src]); return; }
    var im = new Image();
    im.onload = function () { LOGO[src] = im; cb(im); };
    im.onerror = function () { LOGO[src] = null; cb(null); };
    im.src = src;
  }
  function logoColor(im) {                    // 주가 추이 탭과 같은 방법: 로고에서 가장 눈에 띄는 색
    if (!im || !im.naturalWidth) return null;
    var n = 48, cv = document.createElement('canvas'); cv.width = cv.height = n;
    var g = cv.getContext('2d'); g.drawImage(im, 0, 0, n, n);
    var px; try { px = g.getImageData(0, 0, n, n).data; } catch (e) { return null; }
    var bins = {}, dark = {};
    for (var i = 0; i < px.length; i += 4) {
      var r = px[i], gg = px[i + 1], b = px[i + 2], al = px[i + 3];
      if (al < 200) continue;
      var mx = Math.max(r, gg, b), mn = Math.min(r, gg, b), sat = mx ? (mx - mn) / mx : 0;
      if (mn > 225) continue;
      var key = (r >> 4) + ',' + (gg >> 4) + ',' + (b >> 4);
      var lu = (0.299 * r + 0.587 * gg + 0.114 * b) / 255;
      if (sat > 0.25 && mx > 50) bins[key] = (bins[key] || 0) + sat * sat * Math.max(0.05, 1.15 - lu);
      else dark[key] = (dark[key] || 0) + 1;
    }
    function top(o) { var k = null, v = 0; for (var q in o) if (o[q] > v) { v = o[q]; k = q; } return k; }
    var k = top(bins) || top(dark);
    if (!k) return null;
    var c = k.split(',').map(function (x) { return Math.min(255, (+x << 4) + 8); });
    if (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] > 200) return null;
    return '#' + c.map(function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
  }

  function initPage() {
    var cv = $('card'); if (!cv) return;
    var X = cv.getContext('2d');
    var state = { item: null, data: null, logo: null, color: '#2B59C3', colorUser: false, name: '', title: '주주 구성 현황' };
    var LIST = [], BY = {};

    function render() {
      if (!state.item) return;
      if (!state.data) {
        grain(X); X.fillStyle = T.inkSoft; X.font = font(700, 34); X.textAlign = 'center';
        X.fillText('주주 자료가 아직 없어요', CW / 2, CH / 2); X.textAlign = 'left';
        $('c-hint').textContent = '정기보고서를 아직 읽지 못한 종목이에요. 주주현황은 매주 월·목에 채워집니다.';
        return;
      }
      draw(X, state.data, { name: state.name || state.item.name, title: state.title, color: state.color, logo: state.logo });
      var h = state.data;
      $('c-hint').textContent = h.report.replace(/^20(\d\d) /, "'$1년 ") + ' 기준 (' + h.asof.replace(/-/g, '.') + ') · 최대주주 측 ' +
        h.major.length + '명' + ((h.five || []).length ? ' · 5% 이상 주주 ' + h.five.length + '곳' : '');
    }
    function pick(it) {
      state.item = it; state.data = null; state.logo = null;
      state.name = it.name; $('c-name').value = it.name; qIn.value = it.name;
      var p1 = fetch('./data/holders/' + it.code + '.json', { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; })
        .catch(function () { return null; }).then(function (d) { state.data = d; });
      var p2 = new Promise(function (res) { logoImg(it.code, function (im) { state.logo = im; res(); }); });
      Promise.all([p1, p2]).then(function () {
        if (!state.colorUser) { state.color = logoColor(state.logo) || '#2B59C3'; $('c-color').value = state.color; }
        $('qmsg').textContent = it.name + ' · ' + it.code;
        try { history.replaceState(null, '', '?code=' + it.code); } catch (e) { /* 미리보기 */ }
        render();
      });
    }

    // 검색 (실적 탭과 같은 드롭다운)
    var sugItems = [], sugActive = -1, qIn = $('q'), sugBox = $('suggest');
    function search(q) {
      q = (q || '').trim().toLowerCase();
      if (state.item && q === state.item.name.toLowerCase()) q = '';
      if (!q) return { q: '', items: LIST };
      var a = [], b = [], c = [];
      LIST.forEach(function (x) {
        var nm = x.name.toLowerCase(), k = x.code;
        if (nm === q || k === q) a.push(x);
        else if (nm.indexOf(q) === 0 || k.indexOf(q) === 0) b.push(x);
        else if (nm.indexOf(q) >= 0 || k.indexOf(q) >= 0) c.push(x);
      });
      return { q: q, items: a.concat(b, c) };
    }
    function esc(t) { return String(t).replace(/[&<>"]/g, function (m) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]; }); }
    function closeSuggest() { sugBox.style.display = 'none'; sugActive = -1; }
    function openSuggest() {
      var r = search(qIn.value);
      sugItems = r.items.slice(0, 300);
      var html = '<div class="head">' + (r.q ? r.items.length.toLocaleString() + '개 일치'
        : '국내 ' + LIST.length.toLocaleString() + '종목 · 이름이나 코드를 입력해보세요') + '</div>';
      html += sugItems.length ? sugItems.map(function (x, i) {
        return '<li role="option" data-i="' + i + '"><span>' + esc(x.name) + '</span><span class="code">' + esc(x.code) + '</span></li>';
      }).join('') : '<li class="empty">일치하는 종목이 없습니다</li>';
      sugBox.innerHTML = html; sugBox.style.display = 'block'; sugBox.scrollTop = 0; sugActive = -1;
    }
    function choose(it) { if (!it) return; closeSuggest(); qIn.blur(); pick(it); }
    qIn.addEventListener('focus', openSuggest);
    qIn.addEventListener('input', openSuggest);
    sugBox.addEventListener('mousedown', function (e) {
      var li = e.target.closest('li[data-i]'); if (!li) return;
      e.preventDefault(); choose(sugItems[+li.dataset.i]);
    });
    qIn.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); $('go').click(); return; }
      if (sugBox.style.display !== 'block') return;
      var lis = sugBox.querySelectorAll('li[data-i]');
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); if (!lis.length) return;
        sugActive += e.key === 'ArrowDown' ? 1 : -1;
        if (sugActive < 0) sugActive = lis.length - 1; if (sugActive >= lis.length) sugActive = 0;
        for (var i = 0; i < lis.length; i++) lis[i].setAttribute('aria-selected', String(i === sugActive));
        lis[sugActive].scrollIntoView({ block: 'nearest' });
      } else if (e.key === 'Escape') closeSuggest();
    });
    document.addEventListener('click', function (e) { if (!e.target.closest('.search-wrap')) closeSuggest(); });
    $('go').addEventListener('click', function () {
      var it = sugBox.style.display === 'block' && sugActive >= 0 ? sugItems[sugActive] : null;
      if (!it) { var r = search(qIn.value); it = r.items[0]; }
      if (it) choose(it); else $('qmsg').textContent = '찾는 종목이 없어요. 이름이나 종목코드로 찾아 보세요.';
    });

    $('c-name').addEventListener('input', function () { state.name = this.value; render(); });
    $('c-title').value = state.title;
    $('c-title').addEventListener('input', function () { state.title = this.value; render(); });
    $('c-color').addEventListener('input', function () { state.color = this.value; state.colorUser = true; render(); });
    $('c-auto').addEventListener('click', function () { state.colorUser = false; state.color = logoColor(state.logo) || '#2B59C3'; $('c-color').value = state.color; render(); });
    $('c-dl').addEventListener('click', function () {
      if (!state.data) return;
      var big = document.createElement('canvas'); big.width = CW * 3; big.height = CH * 3;
      var g = big.getContext('2d'); g.scale(3, 3);
      draw(g, state.data, { name: state.name || state.item.name, title: state.title, color: state.color, logo: state.logo });
      big.toBlob(function (blob) {
        if (!blob) { alert('그림을 만들지 못했습니다. 새로고침 후 다시 눌러 주세요.'); return; }
        var el = document.createElement('a'); el.href = URL.createObjectURL(blob);
        el.download = (state.name || state.item.name) + '_주주구성.png';
        document.body.appendChild(el); el.click(); el.remove(); setTimeout(function () { URL.revokeObjectURL(el.href); }, 10000);
      }, 'image/png');
    });
    $('btn-mode').addEventListener('click', function () {
      var r = document.documentElement; r.setAttribute('data-mode', r.getAttribute('data-mode') === 'dark' ? 'light' : 'dark'); render();
    });

    fetch('./data/holders/index.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }).catch(function () { return {}; })
      .then(function (j) {
        var items = (j && j.items) || {};
        Object.keys(items).forEach(function (code) {
          var it = { code: code, name: items[code][0] || code, asof: items[code][1] };
          LIST.push(it); BY[code] = it;
        });
        LIST.sort(function (p, q) { return p.name.localeCompare(q.name, 'ko'); });
        $('src-pill').textContent = '정기보고서 기준 · ' + LIST.length.toLocaleString() + '종목';
        var c0 = new URLSearchParams(location.search).get('code');
        var first = BY[c0] || BY['005930'] || LIST[0];
        if (first) (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(function () { pick(first); });
      });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initPage); else initPage();

  window.__hd = { draw: draw, segments: segments, shortName: shortName };
})();
