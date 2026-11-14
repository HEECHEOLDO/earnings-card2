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
        var ink = x.rest ? T.inkSoft : (lum(x.c) < 0.62 ? '#fff' : '#101216');
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
      X.strokeStyle = T.dark ? '#5C6169' : '#A9AEB5'; X.lineWidth = 2;
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
