/* 카드 어두운 바탕 (2026-11) — 모든 탭 공통
   화면이 다크 모드(<html data-mode="dark">)이면 캔버스 카드도 어두운 바탕으로 그린다. 화이트 모드는 그대로.

   각 탭의 그리기 코드는 손대지 않고, 캔버스에 칠하는 색을 그리는 순간에 바꾼다:
     - 종이색·글자색·눈금 같은 무채색은 밝기를 뒤집는다 (자주 쓰는 색은 정해 둔 짝으로)
     - 남색·검정에 가까운 진한 회사 색은 같은 색 계열에서 밝기만 올린다 (밝은 색은 그대로)
     - 순수한 흰색(#fff)은 그대로 — 로고 바탕·색 막대 위 흰 글자
     - 종이 질감(무늬 타일)은 어두운 판 질감으로 바꾸고, 바탕 전체를 칠한 뒤에는 옅은 빛 번짐·가장자리 그늘을 얹는다
   다크/화이트 고른 것은 기억해서 다른 탭에서도 같게 연다 (localStorage 'dg.mode'). */
(function () {
  'use strict';
  var KEY = 'dg.mode', root = document.documentElement;
  try { var saved = localStorage.getItem(KEY); if (saved === 'dark' || saved === 'light') root.setAttribute('data-mode', saved); } catch (e) { /* 저장 안 됨 */ }

  function isDark() { return root.getAttribute('data-mode') === 'dark'; }

  // 자주 쓰는 카드 색의 짝 (밝은 카드 → 어두운 카드)
  var MAP = {
    '#fafaf8': '#17191d', '#101216': '#f3f2ee', '#6b7078': '#a2a7af', '#e6e4dd': '#2e3137', '#eae8e1': '#2a2d33',
    '#c9c6bc': '#4a4e56', '#9aa0a8': '#80868f', '#f2f0ea': '#212429', '#f1efea': '#212429', '#4b4f58': '#b4b9c0',
    '#3a3e46': '#c9ccd1', '#eceae3': '#2a2d33', '#e2dfd6': '#34373e', '#a3a8af': '#7a8089', '#000000': '#f3f2ee',
    '#8c6e14': '#e2b84a'                              // 금색 꼬리표 글자 (꼬리표 바탕이 어두워지니 밝게)
  };
  var PAPER_D = [23, 25, 29];
  // 인스타 피드처럼 완전한 검정 바탕 (무늬·빛 번짐 없음) — window.__cardDark = 'gray' 이면 예전 회색 돌판
  function black() { return window.__cardDark !== 'gray'; }
  function flat() { return window.__cardDark === 'flat'; }            // 'flat': 무늬·빛 없이 완전 평평한 검정
  function stone() { return window.__cardDark === 'stone'; }          // 'stone': 검정 + 돌판 잔무늬·빛 번짐 (기본은 인스타 피드와 같은 #000 + 고운 잔무늬만)
  var MAP_BLACK = { '#fafaf8': '#000000', '#f2f0ea': '#151515', '#f1efea': '#151515', '#eceae3': '#1c1c1c', '#eae8e1': '#1c1c1c', '#e6e4dd': '#2a2a2a', '#e2dfd6': '#2f2f2f' };
  // 바꾸지 않는 색: 색 있는 막대·조각 위에 쓰는 진한 글자 (바탕이 아니라 그 색 위에 있으니 다크 모드여도 진해야 읽힌다)
  var KEEP = { '#111214': 1 };
  var paused = 0;                                   // raw() 안: 국기처럼 색이 정해진 그림은 그대로

  function hex2(v) { return ('0' + Math.max(0, Math.min(255, Math.round(v))).toString(16)).slice(-2); }
  function parse(s) {
    s = String(s).trim().toLowerCase();
    var m;
    if (s[0] === '#') {
      if (s.length === 4) return [parseInt(s[1] + s[1], 16), parseInt(s[2] + s[2], 16), parseInt(s[3] + s[3], 16), 1];
      if (s.length === 7) return [parseInt(s.substr(1, 2), 16), parseInt(s.substr(3, 2), 16), parseInt(s.substr(5, 2), 16), 1];
      if (s.length === 9) return [parseInt(s.substr(1, 2), 16), parseInt(s.substr(3, 2), 16), parseInt(s.substr(5, 2), 16), parseInt(s.substr(7, 2), 16) / 255];
      return null;
    }
    if ((m = /^rgba?\(([^)]+)\)$/.exec(s))) {
      var p = m[1].split(/[\s,\/]+/).filter(Boolean).map(parseFloat);
      if (p.length < 3) return null;
      return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
    }
    if (s === 'white') return [255, 255, 255, 1];
    if (s === 'black') return [0, 0, 0, 1];
    return null;
  }
  function out(r, g, b, a) { return a >= 1 ? '#' + hex2(r) + hex2(g) + hex2(b) : 'rgba(' + [Math.round(r), Math.round(g), Math.round(b), +a.toFixed(3)].join(',') + ')'; }
  function hsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    var mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, d = mx - mn, h = 0, s = 0;
    if (d) {
      s = d / (1 - Math.abs(2 * l - 1));
      h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
      h *= 60; if (h < 0) h += 360;
    }
    return [h, s, l];
  }
  function rgb(h, s, l) {
    var C = (1 - Math.abs(2 * l - 1)) * s, x = C * (1 - Math.abs((h / 60) % 2 - 1)), m = l - C / 2;
    var v = h < 60 ? [C, x, 0] : h < 120 ? [x, C, 0] : h < 180 ? [0, C, x] : h < 240 ? [0, x, C] : h < 300 ? [x, 0, C] : [C, 0, x];
    return [(v[0] + m) * 255, (v[1] + m) * 255, (v[2] + m) * 255];
  }

  var CACHE = {};
  function conv(c) {
    if (typeof c !== 'string') return c;
    if (CACHE[c] !== undefined) return CACHE[c];
    var res = c, p = parse(c);
    if (p) {
      var key = '#' + hex2(p[0]) + hex2(p[1]) + hex2(p[2]);
      if (KEEP[key]) res = c;
      else if (p[0] === 255 && p[1] === 255 && p[2] === 255) res = c;                  // 흰색은 그대로
      else if (black() && MAP_BLACK[key]) { var q0 = parse(MAP_BLACK[key]); res = out(q0[0], q0[1], q0[2], p[3]); }
      else if (MAP[key]) { var q = parse(MAP[key]); res = out(q[0], q[1], q[2], p[3]); }
      else {
        var H = hsl(p[0], p[1], p[2]), lu = (0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]) / 255;
        if (H[1] < 0.14 || Math.max(p[0], p[1], p[2]) - Math.min(p[0], p[1], p[2]) < 18) {
          var nl = Math.max(0.3, 0.075 + (1 - H[2]) * 0.9);                            // 무채색: 밝기 뒤집기 (막대·면은 바탕과 구분되게 너무 어둡지 않게)
          var v = rgb(H[0], H[1] * 0.6, Math.max(0, Math.min(1, nl)));
          res = out(v[0], v[1], v[2], p[3]);
        } else if (lu < 0.3) {                                                         // 진한 회사 색: 밝기만 올리기
          var w = rgb(H[0], Math.max(H[1], 0.6), 0.64);
          res = out(w[0], w[1], w[2], p[3]);
        }
      }
    }
    CACHE[c] = res;
    return res;
  }

  // ---------------------------------------------------------------- 캔버스에 끼우기
  var C2 = window.CanvasRenderingContext2D && CanvasRenderingContext2D.prototype;
  if (!C2) return;
  ['fillStyle', 'strokeStyle', 'shadowColor'].forEach(function (prop) {
    var d = Object.getOwnPropertyDescriptor(C2, prop);
    if (!d || !d.set) return;
    Object.defineProperty(C2, prop, {
      configurable: true, enumerable: d.enumerable, get: d.get,
      set: function (v) { d.set.call(this, !paused && isDark() && typeof v === 'string' && !this.canvas.__noTheme ? conv(v) : v); }
    });
  });
  if (window.CanvasGradient) {
    var addStop = CanvasGradient.prototype.addColorStop;
    CanvasGradient.prototype.addColorStop = function (o, c) { return addStop.call(this, o, !paused && isDark() && !this.__noTheme ? conv(c) : c); };
  }

  // 종이 질감: putImageData 로 만든 '거의 흰 무채색' 그림을 종이 질감으로 표시해 두고, 쓸 때 어두운 판으로 바꿔 쓴다
  var put = C2.putImageData;
  C2.putImageData = function (img) {
    try {
      var d = img.data, n = 0, sum = 0, chroma = 0;
      for (var i = 0; i < d.length; i += 4 * 97) { sum += d[i] + d[i + 1] + d[i + 2]; chroma += Math.abs(d[i] - d[i + 2]); n++; }
      if (n && sum / n / 3 > 228 && chroma / n < 12 && img.width >= 128) { this.canvas.__paper = true; this.canvas.__paperSum = sum / n / 3; }
    } catch (e) { /* 그대로 */ }
    return put.apply(this, arguments);
  };
  var DARKV = typeof WeakMap === 'function' ? new WeakMap() : null;
  // (시안) 검정 바탕 위에 얹는 추가 질감 — 밝은 쪽으로만 더해져서 가장 어두운 곳은 #000 그대로
  function texMap(W, H, fx) {
    var film = fx.indexOf('film') >= 0, weave = fx.indexOf('weave') >= 0, mottle = fx.indexOf('mottle') >= 0;
    if (!film && !weave && !mottle) return null;
    var T = new Float32Array(W * H), s = 7;
    function rnd() { s = (s * 16807) % 2147483647; return s / 2147483647; }
    if (film) {                                                         // 필름 그레인: 2px 덩어리 입자 + 아주 고운 입자
      var cw = Math.ceil(W / 2), ch = Math.ceil(H / 2), C = new Float32Array(cw * ch);
      for (var c = 0; c < C.length; c++) { var r = rnd(); C[c] = r > 0.9 ? (r - 0.9) * 130 : 0; }
      for (var y = 0; y < H; y++) for (var x = 0; x < W; x++) { var f = rnd(); T[y * W + x] += C[(y >> 1) * cw + (x >> 1)] + (f > 0.75 ? (f - 0.75) * 22 : 0); }
    }
    if (weave) {                                                        // 비단결: 아주 가는 사선 결 + 결마다 밝기 흔들림
      for (var y2 = 0; y2 < H; y2++) for (var x2 = 0; x2 < W; x2++) {
        var a = (x2 + y2 * 0.42), b = Math.sin(a * 0.9) * Math.sin(a * 0.031 + Math.sin(y2 * 0.011) * 2);
        T[y2 * W + x2] += b > 0 ? b * 7 : 0;
      }
    }
    if (mottle) {                                                       // 돌판 얼룩: 큰 덩어리 명암 (가장자리 70px 은 0 으로 사라짐)
      var G = 44, gw = Math.ceil(W / G) + 2, gh = Math.ceil(H / G) + 2, N = new Float32Array(gw * gh);
      for (var n = 0; n < N.length; n++) N[n] = rnd();
      var N2 = new Float32Array(gw * gh);                               // 한 번 흐리게 해서 부드러운 덩어리로
      for (var gy = 0; gy < gh; gy++) for (var gx = 0; gx < gw; gx++) { var t = 0, m = 0; for (var dy = -2; dy <= 2; dy++) for (var dx = -2; dx <= 2; dx++) { var yy = gy + dy, xx = gx + dx; if (yy >= 0 && yy < gh && xx >= 0 && xx < gw) { t += N[yy * gw + xx]; m++; } } N2[gy * gw + gx] = t / m; }
      for (var y3 = 0; y3 < H; y3++) for (var x3 = 0; x3 < W; x3++) {
        var fx3 = x3 / G, fy3 = y3 / G, ix = fx3 | 0, iy = fy3 | 0, u = fx3 - ix, w = fy3 - iy;
        u = u * u * (3 - 2 * u); w = w * w * (3 - 2 * w);
        var vv = (N2[iy * gw + ix] * (1 - u) + N2[iy * gw + ix + 1] * u) * (1 - w) + (N2[(iy + 1) * gw + ix] * (1 - u) + N2[(iy + 1) * gw + ix + 1] * u) * w;
        var e = Math.min(x3, y3, W - 1 - x3, H - 1 - y3) / 70; e = e > 1 ? 1 : e;
        var q = (vv - 0.45) * 80; T[y3 * W + x3] += q > 0 ? q * e : 0;
      }
    }
    return T;
  }
  function darkPaper(src) {
    if (!DARKV) return src;
    var hit = DARKV.get(src);
    if (hit) return hit;
    var cv = document.createElement('canvas'); cv.width = src.width; cv.height = src.height;
    var g = cv.getContext('2d'); cv.__noTheme = true;
    g.drawImage(src, 0, 0);
    var im = g.getImageData(0, 0, cv.width, cv.height), d = im.data, base = src.__paperSum || 249, seed = 11;
    if (black() && flat()) { for (var j = 0; j < d.length; j += 4) { d[j] = d[j + 1] = d[j + 2] = 0; d[j + 3] = 255; } put.call(g, im, 0, 0); DARKV.set(src, cv); return cv; }
    var FXS = window.__cardFx != null ? window.__cardFx : 'mottle';   // 기본: 검정 바탕 + 돌판 얼룩 질감
    var PD = !black() ? PAPER_D : stone() ? [12, 12, 13] : [0, 0, 0], KK = !black() ? 1.1 : stone() ? 2.0 : FXS.indexOf('grain') >= 0 ? 2.4 : 1.4;   // 기본: 피드와 같은 #000 바탕에 밝은 잔입자만 (어두운 쪽은 0 에서 멈춰 바탕은 그대로 검정)   // 검정 바탕에 돌판 잔무늬 (검정에서는 무늬를 조금 더 또렷하게)
    var W = cv.width, H = cv.height, TX = black() && !stone() ? texMap(W, H, FXS) : null;
    for (var i = 0; i < d.length; i += 4) {
      var k = (d[i] + d[i + 1] + d[i + 2]) / 3 - base;                 // 원래 무늬(밝고 어두운 차이)만 가져온다
      seed = (seed * 16807) % 2147483647;
      if (seed / 2147483647 > 0.9993) k += 34;                          // 드문 밝은 입자 (돌판·종이 섬유)
      var v = k * KK + (TX ? TX[i >> 2] : 0);
      d[i] = PD[0] + v; d[i + 1] = PD[1] + v; d[i + 2] = PD[2] + v; d[i + 3] = 255;
    }
    put.call(g, im, 0, 0);
    DARKV.set(src, cv);
    return cv;
  }
  function glow(ctx, x, y, w, h) {                                      // 왼쪽 위 옅은 빛 번짐 + 가장자리 그늘
    if (black() && !stone()) {                                          // 피드와 같은 검정은 가장자리를 #000 그대로 (바탕색이 달라지지 않게)
      if ((window.__cardFx || '').indexOf('spot') < 0) return;
      ctx.save();                                                       // (시안) 그래프 뒤 가운데만 아주 옅은 하늘빛 — 가장자리는 완전 검정
      var sg = ctx.createRadialGradient(x + w * 0.5, y + h * 0.56, 20, x + w * 0.5, y + h * 0.56, Math.max(w, h) * 0.5);
      sg.__noTheme = true; addStop.call(sg, 0, 'rgba(173,228,243,0.075)'); addStop.call(sg, 0.6, 'rgba(173,228,243,0.025)'); addStop.call(sg, 1, 'rgba(173,228,243,0)');
      fillStyleRaw(ctx, sg); fillRectRaw.call(ctx, x, y, w, h); ctx.restore(); return;
    }
    ctx.save();
    var rg = ctx.createRadialGradient(x + w * 0.28, y + h * 0.12, 40, x + w * 0.45, y + h * 0.35, Math.max(w, h) * 0.95);
    rg.__noTheme = true;
    addStop.call(rg, 0, 'rgba(255,255,255,0.075)'); addStop.call(rg, 1, 'rgba(255,255,255,0)');
    fillStyleRaw(ctx, rg); fillRectRaw.call(ctx, x, y, w, h);
    var vg = ctx.createRadialGradient(x + w / 2, y + h / 2, Math.max(w, h) * 0.45, x + w / 2, y + h / 2, Math.max(w, h) * 0.85);
    addStop.call(vg, 0, 'rgba(0,0,0,0)'); addStop.call(vg, 1, 'rgba(0,0,0,0.28)');
    fillStyleRaw(ctx, vg); fillRectRaw.call(ctx, x, y, w, h);
    ctx.restore();
  }
  var fsDesc = Object.getOwnPropertyDescriptor(C2, 'fillStyle');
  function fillStyleRaw(ctx, v) { Object.getOwnPropertyDescriptor(CanvasRenderingContext2D.prototype, 'fillStyle').set.call(ctx, v); }
  var fillRectRaw = C2.fillRect;

  var cp = C2.createPattern;
  C2.createPattern = function (img, rep) {
    var useDark = isDark() && img && img.__paper && !this.canvas.__noTheme;
    var p = cp.call(this, useDark ? darkPaper(img) : img, rep);
    if (p && useDark) p.__paper = true;
    return p;
  };
  C2.fillRect = function (x, y, w, h) {
    var r = fillRectRaw.apply(this, arguments);
    var fs = fsDesc.get.call(this);
    // 종이 무늬로 카드 대부분을 칠했으면 그 위에 빛 번짐을 얹는다
    if (fs && fs.__paper && isDark() && w * h >= this.canvas.width * this.canvas.height * 0.25) {
      var t = this.getTransform ? this.getTransform() : null;
      glow(this, x, y, w, h);
      if (t && this.setTransform) this.setTransform(t);
    }
    return r;
  };
  var di = C2.drawImage;
  C2.drawImage = function (img) {
    if (isDark() && img && img.__paper && !this.canvas.__noTheme) {
      var a = Array.prototype.slice.call(arguments); a[0] = darkPaper(img);
      var r = di.apply(this, a);
      if (a.length <= 5 && img.width >= 900) glow(this, a[1] || 0, a[2] || 0, a.length === 5 ? a[3] : img.width, a.length === 5 ? a[4] : img.height);
      return r;
    }
    var rr = di.apply(this, arguments);
    if (isDark() && !this.canvas.__noTheme && darkEdge(img)) ring(this, arguments);
    return rr;
  };
  // 다크 모드: 가장자리가 검은 로고(기아·폴바셋 등)는 검정 바탕에 묻히니 옅은 테두리를 두른다
  var EDGE = typeof WeakMap === 'function' ? new WeakMap() : null;
  function darkEdge(img) {
    if (!EDGE || !img || !img.src || String(img.src).indexOf('/logo/') < 0 || !img.naturalWidth) return false;
    var hit = EDGE.get(img); if (hit !== undefined) return hit;
    var res = false;
    try {
      var n = 48, cv = document.createElement('canvas'); cv.width = cv.height = n; cv.__noTheme = true;
      var g = cv.getContext('2d'); di.call(g, img, 0, 0, n, n);
      var d = g.getImageData(0, 0, n, n).data, sum = 0, cnt = 0, tot = 0;
      for (var k = 0; k < 72; k++) {                                  // 원 둘레 바로 안쪽 (반지름 90%)
        var a = k / 72 * Math.PI * 2, x = Math.round(n / 2 + Math.cos(a) * n * 0.45), y = Math.round(n / 2 + Math.sin(a) * n * 0.45);
        var i = (Math.min(n - 1, y) * n + Math.min(n - 1, x)) * 4; tot++;
        if (d[i + 3] > 200) { sum += 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]; cnt++; }
      }
      res = cnt > tot * 0.6 && sum / cnt < 40;
    } catch (e) { res = false; }
    EDGE.set(img, res);
    return res;
  }
  function ring(ctx, a) {
    var x, y, w, h;
    if (a.length === 9) { x = a[5]; y = a[6]; w = a[7]; h = a[8]; } else if (a.length === 5) { x = a[1]; y = a[2]; w = a[3]; h = a[4]; } else return;
    if (w < 16 || h < 16 || Math.abs(w - h) > w * 0.15) return;
    var r = Math.min(w, h) / 2, lw = Math.max(1, r * 0.03);
    ctx.save();
    ctx.beginPath(); ctx.arc(x + w / 2, y + h / 2, r - lw / 2, 0, Math.PI * 2);
    ssRaw(ctx, 'rgba(255,255,255,0.32)'); ctx.lineWidth = lw; ctx.stroke();
    ctx.restore();
  }
  function ssRaw(ctx, v) { Object.getOwnPropertyDescriptor(CanvasRenderingContext2D.prototype, 'strokeStyle').set.call(ctx, v); }

  // ---------------------------------------------------------------- 모드 바뀔 때
  var subs = [];
  function onChange(fn) { if (typeof fn === 'function') subs.push(fn); }
  if (window.MutationObserver) {
    new MutationObserver(function () {
      try { localStorage.setItem(KEY, isDark() ? 'dark' : 'light'); } catch (e) { /* 저장 안 됨 */ }
      subs.forEach(function (fn) { try { fn(); } catch (e) { /* 다음 */ } });
    }).observe(root, { attributes: true, attributeFilter: ['data-mode'] });
  }

  // 국기·상표처럼 색이 정해진 그림을 그리는 함수를 감싸면, 그 안에서는 색을 바꾸지 않는다
  function raw(fn) { return function () { paused++; try { return fn.apply(this, arguments); } finally { paused--; } }; }

  window.CardTheme = { isDark: isDark, conv: conv, onChange: onChange, raw: raw, INK_ON_COLOR: '#111214' };
})();
