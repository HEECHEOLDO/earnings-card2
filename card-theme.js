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
    '#3a3e46': '#c9ccd1', '#eceae3': '#2a2d33', '#e2dfd6': '#34373e', '#a3a8af': '#646a73', '#000000': '#f3f2ee'
  };
  var PAPER_D = [23, 25, 29];

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
      if (p[0] === 255 && p[1] === 255 && p[2] === 255) res = c;                       // 흰색은 그대로
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
      set: function (v) { d.set.call(this, isDark() && typeof v === 'string' && !this.canvas.__noTheme ? conv(v) : v); }
    });
  });
  if (window.CanvasGradient) {
    var addStop = CanvasGradient.prototype.addColorStop;
    CanvasGradient.prototype.addColorStop = function (o, c) { return addStop.call(this, o, isDark() && !this.__noTheme ? conv(c) : c); };
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
  function darkPaper(src) {
    if (!DARKV) return src;
    var hit = DARKV.get(src);
    if (hit) return hit;
    var cv = document.createElement('canvas'); cv.width = src.width; cv.height = src.height;
    var g = cv.getContext('2d'); cv.__noTheme = true;
    g.drawImage(src, 0, 0);
    var im = g.getImageData(0, 0, cv.width, cv.height), d = im.data, base = src.__paperSum || 249, seed = 11;
    for (var i = 0; i < d.length; i += 4) {
      var k = (d[i] + d[i + 1] + d[i + 2]) / 3 - base;                 // 원래 무늬(밝고 어두운 차이)만 가져온다
      seed = (seed * 16807) % 2147483647;
      if (seed / 2147483647 > 0.9993) k += 34;                          // 드문 밝은 입자 (돌판·종이 섬유)
      d[i] = PAPER_D[0] + k * 1.1; d[i + 1] = PAPER_D[1] + k * 1.1; d[i + 2] = PAPER_D[2] + k * 1.1; d[i + 3] = 255;
    }
    put.call(g, im, 0, 0);
    DARKV.set(src, cv);
    return cv;
  }
  function glow(ctx, x, y, w, h) {                                      // 왼쪽 위 옅은 빛 번짐 + 가장자리 그늘
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
    return di.apply(this, arguments);
  };

  // ---------------------------------------------------------------- 모드 바뀔 때
  var subs = [];
  function onChange(fn) { if (typeof fn === 'function') subs.push(fn); }
  if (window.MutationObserver) {
    new MutationObserver(function () {
      try { localStorage.setItem(KEY, isDark() ? 'dark' : 'light'); } catch (e) { /* 저장 안 됨 */ }
      subs.forEach(function (fn) { try { fn(); } catch (e) { /* 다음 */ } });
    }).observe(root, { attributes: true, attributeFilter: ['data-mode'] });
  }

  window.CardTheme = { isDark: isDark, conv: conv, onChange: onChange };
})();
