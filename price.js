/* 주가 추이 카드 (price.html) — 2026-11
   국내: data/chart/kr/{코드}.json  (collect_anchor.py 가 평일마다 만든다)
   해외: data/chart/us/{티커}.json  이 있으면 그것, 없으면 data/monthly_us.json 의 월말 종가 + 최근 종가(nc)
   파일 모양: {"u":"KRW"|"USD", "d":[[YYYYMMDD,종가]...] 최근 약 400일 일별, "w":[[YYYYMMDD,종가]...] 약 11년 주별} */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var T = { paper: '#fafaf8', ink: '#101216', inkSoft: '#6B7078', rule: '#E6E4DD', grid: '#EAE8E1', axis: '#C9C6BC',
            tick: '#9AA0A8', footer: '#3A3E46', up: '#D6362C', down: '#2B6CD9' };
  var LIGHT = Object.assign({ dark: false }, T), DARK = { dark: true, paper: '#17191D', ink: '#F3F2EE', inkSoft: '#A2A7AF', rule: '#2E3137', grid: '#2A2D33', axis: '#4A4E56', tick: '#80868F', footer: '#C9CCD1', up: '#FF5A4E', down: '#4C8DFF' };
  function theme(dark) { Object.assign(T, dark ? DARK : LIGHT); }   // 카드 바탕: 밝게 / 어둡게
  var FF = "'Noto Sans KR', 'Noto Sans CJK KR', sans-serif";
  function font(w, px) { return w + ' ' + px + 'px ' + FF; }
  var CW = 1080, CH = 1350, L = 100, R = 980;
  var SPANS = { ytd: { label: '올해' }, '1m': { m: 1 }, '3m': { m: 3 }, '6m': { m: 6 }, '1y': { y: 1 },
                '3y': { y: 3 }, '5y': { y: 5 }, '10y': { y: 10 } };

  var state = { item: null, span: '1y', data: null, color: null, colorUser: false, name: '', title: '', titleUser: false, nameUser: false };
  var LIST = [], BY = {}, MON = null;
  // 주요 시장 지수 — data/chart/idx/{코드}.json (collect_chart_idx.py). 이름·코드는 그쪽 INDICES 와 맞춘다
  // 셋째 칸: 로고 자리에 넣을 국기 (logo/idx/{나라}.png)
  var INDICES = [['KOSPI', '코스피', 'KR'], ['KOSDAQ', '코스닥', 'KR'], ['KOSPI200', '코스피 200', 'KR'], ['SPX', 'S&P 500', 'US'],
    ['IXIC', '나스닥 종합', 'US'], ['NDX', '나스닥 100', 'US'], ['DJI', '다우존스', 'US'], ['SOX', '필라델피아 반도체', 'US'],
    ['RUT', '러셀 2000', 'US'], ['N225', '닛케이 225', 'JP'], ['HSI', '항셍', 'HK'], ['SSEC', '상하이 종합', 'CN']];
  var LOGO = {};

  /* ------------------------------------------------------------ 자료 */
  function ymd(n) { n = String(n); return { y: +n.slice(0, 4), m: +n.slice(4, 6), d: +n.slice(6, 8), n: +n }; }
  function toN(dt) { return dt.getFullYear() * 10000 + (dt.getMonth() + 1) * 100 + dt.getDate(); }

  function loadUS(code) {
    return fetch('./data/chart/us/' + code + '.json', { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; }).then(function (j) {
        if (j && j.d && j.d.length) return j;
        // 일별 파일이 아직 없으면 월말 종가 + 최근 종가로 (점이 성글다)
        return (MON ? Promise.resolve(MON) : fetch('./data/monthly_us.json', { cache: 'no-cache' }).then(function (r) { return r.json(); })
          .then(function (m) { MON = m; return m; })).then(function (m) {
            var it = (m.items || {})[code];
            if (!it || !it.v) return null;
            var y0 = +it.s.slice(0, 4), m0 = +it.s.slice(5, 7) - 1, w = [];
            it.v.forEach(function (v, i) {
              if (!v) return;
              var mm = m0 + i, y = y0 + Math.floor(mm / 12), mo = mm % 12 + 1;
              var last = new Date(y, mo, 0);                         // 그 달 마지막 날 (주말이어도 표시용)
              w.push([toN(last), v]);
            });
            var nc = it.nc, d = [];
            if (nc && nc[2] && nc[1] > 0) {
              var n = +nc[2].replace(/-/g, '');
              w = w.filter(function (p) { return Math.floor(p[0] / 100) < Math.floor(n / 100); });   // 진행 중인 달 빼고
              d = w.slice(-14).concat([[n, nc[1]]]);
            } else d = w.slice(-14);
            return { u: 'USD', d: d, w: w, coarse: true };
          });
      });
  }
  function load(item) {
    if (item.ix) return fetch('./data/chart/idx/' + item.code + '.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    if (item.kr) return fetch('./data/chart/kr/' + item.code + '.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    return loadUS(item.code);
  }

  // 고른 기간의 점들 [{n, v}] — 시작점은 '기간 시작일 이전 마지막 종가'
  function series(data, span) {
    if (!data) return null;
    var d = (data.d || []).filter(function (p) { return p[1] > 0; });
    var w = (data.w || []).filter(function (p) { return p[1] > 0; });
    if (!d.length && !w.length) return null;
    var lastP = d.length ? d[d.length - 1] : w[w.length - 1];
    if (w.length && w[w.length - 1][0] > lastP[0]) lastP = w[w.length - 1];
    var end = ymd(lastP[0]), sp = SPANS[span], start;
    if (span === 'ytd') start = (end.y - 1) * 10000 + 1231;
    else {
      var dt = new Date(end.y, end.m - 1, end.d);
      if (sp.m) dt.setMonth(dt.getMonth() - sp.m); else dt.setFullYear(dt.getFullYear() - sp.y);
      start = toN(dt);
    }
    var daily = span === 'ytd' || !!sp.m || sp.y <= 1, src;
    if (daily) {
      // 1년 이하: 일별. 일별이 기간 시작까지 안 닿으면 그 앞은 주별로 잇는다
      var cut = d.length ? d[0][0] : 99999999;
      src = (d.length && d[0][0] <= start) ? d : w.filter(function (p) { return p[0] < cut; }).concat(d);
    } else {
      // 3년 이상: 주별, 끝에는 가장 최근 종가
      src = w.slice();
      if (!src.length || src[src.length - 1][0] < lastP[0]) src.push(lastP);
    }
    var base = null, out = [];
    src.forEach(function (p) { if (p[0] <= start) base = p; else out.push(p); });
    if (base) out.unshift(base);
    var listed = !base;                            // 기간 시작 때 아직 상장 전 (처음부터 그린다)
    var pts = out.map(function (p) { var o = ymd(p[0]); o.v = p[1]; return o; });
    if (pts.length < 2) return null;
    return { pts: pts, listed: listed, coarse: !!data.coarse };
  }

  /* ------------------------------------------------------------ 글자 */
  // kr: true(원) · false(달러) · 'ix'(지수 — 단위 없이 포인트)
  function money(v, kr) {
    if (kr === 'ix') return v.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });   // 지수는 소수점 한 자리
    if (kr) return Math.round(v).toLocaleString('ko-KR') + '원';
    return '$' + (v >= 1000 ? Math.round(v).toLocaleString('en-US') : v >= 1 ? v.toFixed(2) : v.toFixed(3));
  }
  function tickTxt(v, kr, st) {
    if (kr === 'ix') return v.toLocaleString('en-US', { maximumFractionDigits: st >= 1 ? 0 : 2 });
    if (kr) return Math.round(v).toLocaleString('ko-KR');
    var dec = st >= 1 ? 0 : st >= 0.1 ? 1 : 2;
    return '$' + (v >= 1000 ? Math.round(v).toLocaleString('en-US') : v.toFixed(dec));
  }
  function dlab(p) { return p.y + '.' + (p.m < 10 ? '0' : '') + p.m + '.' + (p.d < 10 ? '0' : '') + p.d; }
  function pct(x) { var a = Math.abs(x); return (a >= 1000 ? Math.round(a).toLocaleString('en-US') : a.toFixed(1)) + '%'; }
  function autoTitle(s) {
    if (!s) return '';
    var what = state.item && state.item.ix ? ' 지수 추이' : ' 주가 추이';
    if (state.span === 'ytd') return s.pts[s.pts.length - 1].y + '년' + what;
    var sp = SPANS[state.span];
    return '최근 ' + (sp.m ? sp.m + '개월' : sp.y + '년') + what;
  }

  /* ------------------------------------------------------------ 로고·색 */
  function logoPath(it) { if (it.ix) return './logo/idx/' + it.cc + '.png'; return it.kr ? './logo/kr/' + it.code + '.png' : './logo/us/' + it.code + '.png'; }
  function logoImg(it, cb) {
    var src = logoPath(it);
    if (LOGO[src] !== undefined) { cb(LOGO[src]); return; }
    var im = new Image();
    im.onload = function () { LOGO[src] = im; cb(im); };
    im.onerror = function () { LOGO[src] = null; cb(null); };
    im.src = src;
  }
  function logoColor(im) {
    if (!im || !im.naturalWidth) return null;
    var n = 48, cv = document.createElement('canvas'); cv.width = cv.height = n;
    var g = cv.getContext('2d'); g.drawImage(im, 0, 0, n, n);
    var px; try { px = g.getImageData(0, 0, n, n).data; } catch (e) { return null; }
    var bins = {}, dark = {};
    for (var i = 0; i < px.length; i += 4) {
      var r = px[i], gg = px[i + 1], b = px[i + 2], a = px[i + 3];
      if (a < 200) continue;
      var mx = Math.max(r, gg, b), mn = Math.min(r, gg, b), sat = mx ? (mx - mn) / mx : 0;
      if (mn > 225) continue;
      var key = (r >> 4) + ',' + (gg >> 4) + ',' + (b >> 4);
      var lu = (0.299 * r + 0.587 * gg + 0.114 * b) / 255;
      if (sat > 0.25 && mx > 50) bins[key] = (bins[key] || 0) + sat * sat * Math.max(0.05, 1.15 - lu);
      else dark[key] = (dark[key] || 0) + 1;
    }
    var pickBin = function (o) { var k = Object.keys(o).sort(function (x, y) { return o[y] - o[x]; })[0]; return k ? k.split(',').map(function (v) { return +v * 16 + 8; }) : null; };
    var tot = function (o) { return Object.keys(o).reduce(function (s0, k) { return s0 + o[k]; }, 0); };
    var rgb = tot(bins) >= 4 ? pickBin(bins) : pickBin(dark);
    if (!rgb) return null;
    var lum = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255;
    if (lum > 0.62) rgb = rgb.map(function (v) { return Math.round(v * 0.62 / lum); });   // 너무 옅으면 종이 위에서 안 보인다
    return '#' + rgb.map(function (v) { return ('0' + Math.max(0, Math.min(255, v)).toString(16)).slice(-2); }).join('');
  }

  /* ------------------------------------------------------------ 그리기 */
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

  function draw(X, s, opt) {
    var kr = opt.kr, color, pts = s.pts, n = pts.length, last = n - 1;
    X.save();
    X.textAlign = 'left'; X.textBaseline = 'alphabetic';
    theme(!!opt.dark); grain(X); color = forDark(opt.color || '#2B59C3');

    // 머리: 로고 + 이름 + 제목
    var y0 = 205, nx = L;
    if (opt.logo) {
      X.save(); X.beginPath(); X.arc(L + 36, y0 - 30, 36, 0, 7); X.clip();
      X.fillStyle = '#fff'; X.fillRect(L, y0 - 66, 72, 72);
      X.drawImage(opt.logo, L, y0 - 66, 72, 72); X.restore();
      nx = L + 90;
    }
    var nameFs = 92;
    X.font = font(900, nameFs);
    while (nameFs > 52 && X.measureText(opt.name).width > R - nx) { nameFs -= 4; X.font = font(900, nameFs); }
    X.fillStyle = T.ink; X.fillText(opt.name, nx, y0);
    var tFs = 56; X.font = font(900, tFs);
    while (tFs > 34 && X.measureText(opt.title).width > R - L) { tFs -= 2; X.font = font(900, tFs); }
    X.fillText(opt.title, L, y0 + 82);

    // 눈금
    var top = y0 + 160, bot = 1120, pl = L + 70, pr = R - 175;
    var vs = pts.map(function (p) { return p.v; });
    var mn = Math.min.apply(null, vs), mx = Math.max.apply(null, vs);
    var span0 = mx - mn; if (!(span0 > 0)) span0 = Math.max(Math.abs(mx) * 0.1, 1e-6);
    var raw = span0 / 4, step = Math.pow(10, Math.floor(Math.log10(raw)));
    var st = [1, 2, 2.5, 5, 10].map(function (k) { return k * step; }).filter(function (k) { return span0 / k <= 5; })[0] || step * 10;
    var lo = Math.floor(mn / st) * st, hi = Math.ceil(mx / st) * st;
    if (hi === lo) { hi += st; lo = Math.max(0, lo - st); }
    if (mn - lo < 0.12 * (hi - lo) && lo - st >= 0) lo -= st;
    if (hi - mx < 0.08 * (hi - lo)) hi += st;
    // 왼쪽 눈금 글자가 길면 그래프를 오른쪽으로 민다
    X.font = font(600, 22);
    var tw = 0; for (var t0 = lo; t0 <= hi + st * 1e-6; t0 += st) tw = Math.max(tw, X.measureText(tickTxt(t0, kr, st)).width);
    pl = Math.max(pl, L + tw + 14);
    function xA(i) { return n === 1 ? (pl + pr) / 2 : pl + (pr - pl) * i / (n - 1); }
    function yA(v) { return bot - (v - lo) / (hi - lo) * (bot - top); }

    X.strokeStyle = T.grid; X.lineWidth = 1.5; X.fillStyle = T.tick; X.textAlign = 'right';
    var tickBoxes = [];
    for (var t = lo; t <= hi + st * 1e-6; t += st) {
      var gy = yA(t), tt = tickTxt(t, kr, st), tw2 = X.measureText(tt).width;
      X.beginPath(); X.moveTo(pl, gy); X.lineTo(pr + 40, gy); X.stroke();
      X.fillText(tt, pl - 12, gy + 7);
      tickBoxes.push([pl - 12 - tw2, gy - 12, tw2, 22]);         // 숫자 표시가 눈금 글자 위에 얹히지 않게
    }
    X.textAlign = 'left';

    // 선과 면
    var grad = X.createLinearGradient(0, top, 0, bot); grad.addColorStop(0, color + '33'); grad.addColorStop(1, color + '00');
    X.beginPath(); X.moveTo(xA(0), bot);
    pts.forEach(function (p, i) { X.lineTo(xA(i), yA(p.v)); });
    X.lineTo(xA(last), bot); X.closePath(); X.fillStyle = grad; X.fill();
    X.beginPath(); pts.forEach(function (p, i) { if (i) X.lineTo(xA(i), yA(p.v)); else X.moveTo(xA(i), yA(p.v)); });
    X.strokeStyle = color; X.lineWidth = n > 300 ? 4 : 5; X.lineJoin = 'round'; X.lineCap = 'round'; X.stroke();
    X.strokeStyle = T.axis; X.lineWidth = 3; X.beginPath(); X.moveTo(pl, bot); X.lineTo(pr + 40, bot); X.stroke();

    // 표시점: 시작·최고·최저·마지막
    var iHi = vs.indexOf(mx), iLo = vs.lastIndexOf(mn);
    var placed = tickBoxes.slice(), dates = [];
    function segHit(x1, y1, x2, y2, b) {
      var L2 = b[0] - 6, R2 = b[0] + b[2] + 6, T2 = b[1] - 6, B2 = b[1] + b[3] + 6;
      if (Math.max(x1, x2) < L2 || Math.min(x1, x2) > R2 || Math.max(y1, y2) < T2 || Math.min(y1, y2) > B2) return false;
      var a0 = 0, a1 = 1, dx = x2 - x1, dy = y2 - y1, P = [-dx, dx, -dy, dy], Q = [x1 - L2, R2 - x1, y1 - T2, B2 - y1];
      for (var k = 0; k < 4; k++) {
        if (P[k] === 0) { if (Q[k] < 0) return false; continue; }
        var tt = Q[k] / P[k];
        if (P[k] < 0) { if (tt > a1) return false; if (tt > a0) a0 = tt; } else { if (tt < a0) return false; if (tt < a1) a1 = tt; }
      }
      return true;
    }
    var keyPts = [0, iHi, iLo, last];
    function freeBox(b, own) {
      if (b[0] < L || b[0] + b[2] > R || b[1] < top - 40 || b[1] + b[3] > bot - 4) return false;
      if (placed.some(function (q) { return b[0] < q[0] + q[2] + 6 && b[0] + b[2] + 6 > q[0] && b[1] < q[1] + q[3] + 4 && b[1] + b[3] + 4 > q[1]; })) return false;
      function dist(i) { var px = xA(i), py = yA(pts[i].v); var dx = Math.max(b[0] - px, 0, px - b[0] - b[2]), dy = Math.max(b[1] - py, 0, py - b[1] - b[3]); return Math.sqrt(dx * dx + dy * dy); }
      var dOwn = dist(own), ox = xA(own), oy = yA(pts[own].v);
      // 다른 표시점에 더 가까우면 그 점의 숫자처럼 보인다 (아주 붙어 있는 점끼리는 어차피 같은 자리라 따지지 않는다)
      if (keyPts.some(function (i) {
        if (i === own) return false;
        var ddx = xA(i) - ox, ddy = yA(pts[i].v) - oy;
        if (ddx * ddx + ddy * ddy < 45 * 45) return false;
        return dist(i) < dOwn + 10;
      })) return false;
      // 선분 검사는 상자 근처만 (일별 점이 많아도 빠르게)
      var i0 = Math.max(1, Math.floor((b[0] - 10 - pl) / (pr - pl) * (n - 1))), i1 = Math.min(last, Math.ceil((b[0] + b[2] + 10 - pl) / (pr - pl) * (n - 1)) + 1);
      for (var k = i0; k <= i1; k++) if (segHit(xA(k - 1), yA(pts[k - 1].v), xA(k), yA(pts[k].v), b)) return false;
      return true;
    }
    function dateAt(i) {
      var x = xA(i), txt = dlab(pts[i]);
      X.font = font(600, 22); var w = X.measureText(txt).width;
      var lx = Math.max(L, Math.min(R - w, x - w / 2));
      if (dates.some(function (q) { return lx < q[0] + q[1] + 14 && lx + w + 14 > q[0]; })) return;
      dates.push([lx, w]);
      X.fillStyle = T.inkSoft; X.fillText(txt, lx, bot + 36);
    }
    function mark(i, txt, above, sub) {
      var x = xA(i), y = yA(pts[i].v);
      X.setLineDash([5, 7]); X.strokeStyle = T.axis; X.lineWidth = 2; X.beginPath(); X.moveTo(x, y + 10); X.lineTo(x, bot); X.stroke(); X.setLineDash([]);
      X.fillStyle = T.paper; X.beginPath(); X.arc(x, y, 10, 0, 7); X.fill(); X.strokeStyle = color; X.lineWidth = 5; X.stroke();
      X.font = font(600, 22); var ws = X.measureText(sub + ' ').width;
      X.font = font(800, 30); var w = ws + X.measureText(txt).width, h = 34;
      var ys = [], cands = [];
      // 고른 쪽(위/아래)으로 그래프 끝까지 조금씩 떨어뜨려 보고, 안 되면 반대쪽
      for (var lv = 0; lv < 14; lv++) ys.push(above ? y - 20 - h - lv * h * 0.8 : y + 20 + lv * h * 0.8);
      for (var lv2 = 0; lv2 < 14; lv2++) ys.push(above ? y + 20 + lv2 * h * 0.8 : y - 20 - h - lv2 * h * 0.8);
      var xs = [x - w / 2, x + 14, x - 14 - w, x + 50, x - 50 - w];
      if (i === 0) xs.push(pl - 4);                // 시작점: 그래프 왼쪽 끝에 맞춘 자리
      ys.forEach(function (yy) { xs.forEach(function (xx) { cands.push([xx, yy, w, h]); }); });
      var b = null, stack = false;
      for (var c = 0; c < cands.length; c++) if (freeBox(cands[c], i)) { b = cands[c]; break; }
      if (!b) {
        // 한 줄로 놓을 자리가 없으면 두 줄('시작' 위, 숫자 아래)로 좁혀 다시 찾는다
        var wv = w - ws, w2 = Math.max(ws, wv), h2 = 58, c2 = [];
        var ys2 = [];
        for (var l3 = 0; l3 < 12; l3++) { ys2.push(y - 18 - h2 - l3 * 20); ys2.push(y + 18 + l3 * 20); }
        ys2.forEach(function (yy) { [x - w2 / 2, x + 14, x - 14 - w2].forEach(function (xx) { c2.push([xx, yy, w2, h2]); }); });
        for (var k2 = 0; k2 < c2.length; k2++) if (freeBox(c2[k2], i)) { b = c2[k2]; stack = true; break; }
      }
      if (b && stack) {
        placed.push(b);
        X.font = font(600, 22); X.fillStyle = T.inkSoft; X.fillText(sub, b[0], b[1] + 20);
        X.font = font(800, 30); X.fillStyle = color; X.fillText(txt, b[0], b[1] + 52);
      } else if (b) {
        placed.push(b);
        var ny = Math.max(b[1], Math.min(b[1] + b[3], y));
        if (Math.abs(ny - y) > 40) {
          X.strokeStyle = color; X.globalAlpha = 0.5; X.lineWidth = 1.5; X.beginPath();
          X.moveTo(x, y + (ny > y ? 12 : -12)); X.lineTo(x, ny > y ? b[1] - 4 : b[1] + b[3] + 2); X.stroke(); X.globalAlpha = 1;
        }
        X.font = font(600, 22); X.fillStyle = T.inkSoft; X.fillText(sub + ' ', b[0], b[1] + h - 6);
        X.font = font(800, 30); X.fillStyle = color; X.fillText(txt, b[0] + ws, b[1] + h - 4);
      }
      dateAt(i);
      return !!b;
    }
    // 마지막 점 (가장 최근 종가) — 크게
    var lx = xA(last), ly = yA(pts[last].v);
    X.fillStyle = color; X.beginPath(); X.arc(lx, ly, 13, 0, 7); X.fill(); X.strokeStyle = T.paper; X.lineWidth = 5; X.stroke();
    var endTxt = money(pts[last].v, kr), efs = 36;
    var eShift = Math.min(0, bot - 10 - (ly + 52));       // 끝이 바닥 가까이면 글자를 올려 날짜 줄과 안 겹치게
    eShift = Math.max(eShift, top - 30 - (ly - 26));
    X.font = font(900, efs);
    while (efs > 26 && lx + 22 + X.measureText(endTxt).width > CW - 24) { efs -= 2; X.font = font(900, efs); }
    X.fillStyle = T.ink; X.fillText(endTxt, lx + 22, ly + 12 + eShift);
    var chg = (pts[last].v / pts[0].v - 1) * 100, up = chg >= 0;
    X.font = font(700, 23); X.fillStyle = Math.abs(chg) < 0.05 ? T.inkSoft : up ? T.up : T.down;
    X.fillText((Math.abs(chg) < 0.05 ? '− ' : up ? '▲ ' : '▼ ') + pct(chg), lx + 22, ly + 46 + eShift);
    placed.push([lx + 16, ly - 26 + eShift, Math.max(X.measureText(endTxt).width, 120) + 12, 82]);
    X.font = font(600, 22); var lw = X.measureText(dlab(pts[last])).width;
    var llx = Math.min(R - lw, lx - lw / 2); dates.push([llx, lw]);
    X.fillStyle = T.inkSoft; X.fillText(dlab(pts[last]), llx, bot + 36);

    var shown = { start: false, hi: false, lo: false };
    shown.start = mark(0, money(pts[0].v, kr), pts[0].v >= (mx + mn) / 2, opt.ytd ? '연초' : s.listed ? '상장' : '시작');
    // 끝점 바로 옆(40px 안)의 최고·최저는 끝값과 겹쳐 보이므로 따로 적지 않는다
    var nearEnd = function (i) { return Math.abs(xA(i) - lx) < 40 && Math.abs(yA(pts[i].v) - ly) < 60; };
    if (iHi !== last && iHi !== 0 && !nearEnd(iHi)) shown.hi = mark(iHi, money(mx, kr), true, '최고');
    if (iLo !== last && iLo !== 0 && iLo !== iHi && !nearEnd(iLo)) shown.lo = mark(iLo, money(mn, kr), false, '최저');

    X.fillStyle = T.rule; X.fillRect(L, 1180, R - L, 2);
    X.font = font(700, 26); X.fillStyle = T.footer; X.textAlign = 'right'; X.fillText('@돈굴돈굴', R, 1224); X.textAlign = 'left';
    X.restore();
    return { shown: shown, iHi: nearEnd(iHi) ? last : iHi, iLo: nearEnd(iLo) ? last : iLo, last: last, n: n };
  }

  /* ------------------------------------------------------------ 화면 */
  var cv = $('card'), X = cv.getContext('2d');
  function render() {
    var it = state.item;
    if (!it) return;
    var s = series(state.data, state.span);
    if (!s) {
      grain(X);
      X.fillStyle = T.inkSoft; X.font = font(700, 34); X.textAlign = 'center';
      X.fillText(state.data ? '이 기간에는 주가가 없어요' : '주가 자료가 아직 없어요', CW / 2, CH / 2); X.textAlign = 'left';
      $('c-hint').textContent = state.data ? '상장한 지 얼마 안 됐거나 거래가 멈춘 종목일 수 있어요. 다른 기간을 골라 보세요.'
                                           : '이 종목은 아직 주가를 모으지 못했어요.';
      return;
    }
    if (!state.titleUser) { state.title = autoTitle(s); $('c-title').value = state.title; }
    draw(X, s, { kr: it.ix ? 'ix' : it.kr, color: state.color, name: state.name || it.name, title: state.title, logo: state.logo, ytd: state.span === 'ytd' });
    var a = s.pts[0], b = s.pts[s.pts.length - 1];
    $('c-hint').textContent = dlab(a) + ' ~ ' + dlab(b) + ' · ' + s.pts.length + '개 점' +
      (s.coarse ? ' · 이 종목은 아직 일별 주가가 없어 월말 종가로 그렸어요' : '') +
      (s.listed ? ' · 기간 중간에 상장해 상장일부터 그렸어요' : '');
  }
  function pick(it) {
    state.item = it; state.data = null; state.logo = null; state.titleUser = false; state.nameUser = false;
    state.name = it.name; $('c-name').value = it.name; $('q').value = it.name;
    if (!state.colorUser) state.color = '#2B59C3';
    var p1 = load(it).then(function (d) { state.data = d; });
    var p2 = new Promise(function (res) { logoImg(it, function (im) { state.logo = im; res(); }); });
    Promise.all([p1, p2]).then(function () {
      if (!state.colorUser) { state.color = (it.ix ? null : logoColor(state.logo)) || '#2B59C3'; $('c-color').value = state.color; }   // 국기 색은 선 색으로 안 쓴다
      $('qmsg').textContent = it.name + ' · ' + (it.ix ? '시장 지수' : it.kr ? it.code + ' · 국내' : it.code + ' · 해외');
      render();
    });
  }
  function find(q) {
    q = (q || '').trim(); if (!q) return null;
    var lq = q.toLowerCase();
    var hit = LIST.filter(function (x) { return x.name === q || x.code.toLowerCase() === lq; })[0];
    if (hit) return hit;
    var m = /\(([^)]+)\)\s*$/.exec(q);
    if (m && BY[m[1].toUpperCase()]) return BY[m[1].toUpperCase()];
    return LIST.filter(function (x) { return x.name.toLowerCase().indexOf(lq) === 0; })[0] ||
           LIST.filter(function (x) { return x.name.toLowerCase().indexOf(lq) >= 0; })[0] || null;
  }

  /* ------------------------------------------------------------ 검색 (실적 탭과 같은 드롭다운) */
  var MKT = 'all', sugItems = [], sugActive = -1, qIn = $('q'), sugBox = $('suggest');
  var MKT_NAME = { all: '전체', kr: '국내', us: '해외', ix: '지수' };
  var CC_NAME = { KR: '한국', US: '미국', JP: '일본', HK: '홍콩', CN: '중국' };
  function inMkt(x) {
    return MKT === 'all' || (MKT === 'ix' ? x.ix : MKT === 'kr' ? (x.kr && !x.ix) : (!x.kr && !x.ix));
  }
  function search(q) {
    q = (q || '').trim().toLowerCase();
    if (state.item && q === state.item.name.toLowerCase()) q = '';     // 지금 고른 종목 이름이면 전체 보기
    var pool = LIST.filter(inMkt);
    if (!q) return { q: '', items: pool, total: pool.length };
    var a = [], b = [], c = [];
    pool.forEach(function (x) {
      var n = x.name.toLowerCase(), k = x.code.toLowerCase();
      if (n === q || k === q) a.push(x);
      else if (n.indexOf(q) === 0 || k.indexOf(q) === 0) b.push(x);
      else if (n.indexOf(q) >= 0 || k.indexOf(q) >= 0) c.push(x);
    });
    return { q: q, items: a.concat(b, c), total: pool.length };
  }
  function esc(t) { return String(t).replace(/[&<>"]/g, function (m) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]; }); }
  function closeSuggest() { sugBox.style.display = 'none'; sugActive = -1; }
  function openSuggest() {
    var r = search(qIn.value);
    sugItems = r.items.slice(0, 300);
    var html = '<div class="head">' + (r.q ? r.items.length.toLocaleString() + '개 일치'
      : (MKT === 'ix' ? '지수 ' + r.total + '개' : MKT_NAME[MKT] + ' ' + r.total.toLocaleString() + '종목') + ' · 이름이나 코드를 입력해보세요') + '</div>';
    html += sugItems.length ? sugItems.map(function (x, i) {
      return '<li role="option" data-i="' + i + '"><span>' + esc(x.name) + '</span><span class="code">' +
        (x.ix ? (CC_NAME[x.cc] || '') + ' 지수' : esc(x.code) + (MKT === 'all' ? ' · ' + (x.kr ? '국내' : '해외') : '')) + '</span></li>';
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
  document.addEventListener('click', function (e) { if (!e.target.closest('.search-wrap') && !e.target.closest('#mkts')) closeSuggest(); });
  $('go').addEventListener('click', function () {
    var it = sugBox.style.display === 'block' && sugActive >= 0 ? sugItems[sugActive] : null;
    if (!it) { var r = search(qIn.value); it = r.q ? r.items[0] : find(qIn.value); }
    if (it) choose(it); else $('qmsg').textContent = '찾는 종목이 없어요. 이름이나 종목코드·티커로 찾아 보세요.';
  });
  Array.prototype.forEach.call(document.querySelectorAll('#mkts .preset'), function (b) {
    b.addEventListener('click', function () {
      MKT = b.dataset.m;
      Array.prototype.forEach.call(document.querySelectorAll('#mkts .preset'), function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      qIn.value = ''; qIn.focus(); openSuggest();
    });
  });
  Array.prototype.forEach.call(document.querySelectorAll('#spans .preset'), function (b) {
    b.addEventListener('click', function () {
      state.span = b.dataset.s; state.titleUser = false;
      Array.prototype.forEach.call(document.querySelectorAll('#spans .preset'), function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
      render();
    });
  });
  $('c-name').addEventListener('input', function () { state.name = this.value; render(); });
  $('c-title').addEventListener('input', function () { state.title = this.value; state.titleUser = true; render(); });
  $('c-color').addEventListener('input', function () { state.color = this.value; state.colorUser = true; render(); });
  $('c-auto').addEventListener('click', function () { state.colorUser = false; state.color = (state.item && state.item.ix ? null : logoColor(state.logo)) || '#2B59C3'; $('c-color').value = state.color; render(); });
  $('c-dl').addEventListener('click', function () {
    var s = series(state.data, state.span); if (!s) return;
    var big = document.createElement('canvas'); big.width = CW * 3; big.height = CH * 3;
    var g = big.getContext('2d'); g.scale(3, 3);
    draw(g, s, { kr: state.item.ix ? 'ix' : state.item.kr, color: state.color, name: state.name || state.item.name, title: state.title, logo: state.logo, ytd: state.span === 'ytd' });
    big.toBlob(function (blob) {
      if (!blob) { alert('그림을 만들지 못했습니다. 새로고침 후 다시 눌러 주세요.'); return; }
      var a = document.createElement('a'); a.href = URL.createObjectURL(blob);
      a.download = (state.name || state.item.name) + '_주가추이_' + state.span + '.png';
      document.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 10000);
    }, 'image/png');
  });
  $('btn-mode').addEventListener('click', function () {
    var r = document.documentElement; r.setAttribute('data-mode', r.getAttribute('data-mode') === 'dark' ? 'light' : 'dark');
  });

  // 종목 목록: 국내는 data/index.json(실적 회사) + data/returns.json(ETF 포함), 해외는 returns.json 의 미국 종목
  Promise.all([
    fetch('./data/returns.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }).catch(function () { return {}; }),
    fetch('./data/index.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }).catch(function () { return {}; }),
    fetch('./data/anchor.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }).catch(function () { return {}; })
  ]).then(function (res) {
    var ret = (res[0] && res[0].items) || {}, idx = ((res[1] && res[1].companies) || []), KO = window.US_KO || {};
    var seen = {};
    function add(code, name, kr) {
      if (!code || seen[code]) return;
      seen[code] = 1;
      var it = { code: code, name: name || code, kr: kr };
      LIST.push(it); BY[code.toUpperCase()] = it;
    }
    INDICES.forEach(function (x) { add(x[0], x[1], false); LIST[LIST.length - 1].ix = true; LIST[LIST.length - 1].cc = x[2]; });   // 지수 먼저
    Object.keys(KO).forEach(function (t) { if (ret[t]) add(t, KO[t], false); });            // 한글 이름 있는 해외 먼저
    idx.forEach(function (c) { add(c.code, c.name, true); });
    Object.keys(ret).forEach(function (c) { var v = ret[c]; add(c, v.market === 'US' ? (KO[c] || v.name) : v.name, v.market !== 'US'); });
    var kr = res[2] && res[2].kr;
    // 국내는 주가를 모으는 종목(anchor.json)만 남긴다 — 실적만 있고 주가가 없는 종목은 고를 수 없게
    if (kr && kr.items) {
      LIST = LIST.filter(function (x) { return !x.kr || kr.items[x.code]; });
      BY = {}; LIST.forEach(function (x) { BY[x.code.toUpperCase()] = x; });
    }
    $('src-pill').textContent = '국내 ' + ((kr && kr.asof) || '') + ' 종가 기준';
    var q = new URLSearchParams(location.search), c0 = (q.get('code') || '005930').toUpperCase();
    if (q.get('span') && SPANS[q.get('span')]) {
      state.span = q.get('span');
      Array.prototype.forEach.call(document.querySelectorAll('#spans .preset'), function (x) { x.setAttribute('aria-pressed', x.dataset.s === state.span ? 'true' : 'false'); });
    }
    pick(BY[c0] || BY['005930'] || LIST[0]);
    Array.prototype.forEach.call(document.querySelectorAll('#ixs .preset'), function (b) {
      b.addEventListener('click', function () { var it = BY[b.dataset.c]; if (it) pick(it); });
    });
  });

  window.__pc = { series: series, draw: draw, load: load, list: function () { return LIST; }, state: state };
})();
