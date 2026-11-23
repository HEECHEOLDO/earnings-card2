/* 카드 PNG 저장 비율 — 4:5(기본) · 1:1 · 7:5 · 16:9 (2026-11)
   모든 탭의 저장은 '1080·S × 1350·S 캔버스를 만들고 ctx.scale(S,S) 한 뒤 1080×1350 기준으로 그린다'.
   그 scale(S,S) 순간을 잡아, 고른 비율이 4:5가 아니면 캔버스 크기를 바꾸고 그리기를 그 비율에 맞게 옮긴다.
     · 가로는 넓게(sx), 세로는 sy 로 — 글자·원·로고·선 굵기는 sy 하나로만 키워 찌그러지지 않는다
     · 제목(위)·출처(아래) 줄은 펼치지 않고 왼쪽 끝에 붙인다
     · 1:1 은 출처·@돈굴돈굴 없이, 7:5·16:9 는 @돈굴돈굴만 뺀다 (인스타그램용이 아니라 데드존 없이 꽉)
     · 원형 그래프 탭은 window.CARD_RATIO_CAP = 1 로 가로를 펼치지 않는다
   각 탭은 이 파일만 불러오면 되고, 저장 단추 옆에 '비율' 고르기가 붙는다. */
(function () {
  'use strict';
  var R = { '45': [1080, 1350, '4:5'], '11': [1080, 1080, '1:1'], '75': [1512, 1080, '7:5'], '169': [1920, 1080, '16:9'] };
  var cur = '45';
  try { var sv = localStorage.getItem('cardRatio'); if (R[sv]) cur = sv; } catch (e) { /* 저장소를 못 쓰면 기본 */ }
  var P = CanvasRenderingContext2D.prototype, O = {};
  ['setTransform', 'resetTransform', 'getTransform', 'scale', 'fillText', 'strokeText', 'measureText', 'arc', 'drawImage', 'stroke', 'fillRect', 'putImageData'].forEach(function (n) { O[n] = P[n]; });
  var M = new WeakMap();            // 바꿔 그리는 중인 ctx → 설정
  var DONE = new WeakSet();          // 비율을 바꾼 캔버스 — 저장할 때 빈 곳(원형 그림 탭의 양옆 등)을 바탕색으로 채운다
  function filled(cv) {
    var t = document.createElement('canvas'); t.width = cv.width; t.height = cv.height; var g = t.getContext('2d');
    var px = cv.getContext('2d').getImageData(Math.round(cv.width / 2), 4, 1, 1).data;
    g.fillStyle = px[3] ? 'rgb(' + px[0] + ',' + px[1] + ',' + px[2] + ')' : '#F7F6F2'; O.fillRect.call(g, 0, 0, t.width, t.height);
    O.drawImage.call(g, cv, 0, 0); return t;
  }
  var tb0 = HTMLCanvasElement.prototype.toBlob, tu0 = HTMLCanvasElement.prototype.toDataURL;
  HTMLCanvasElement.prototype.toBlob = function () { return tb0.apply(DONE.has(this) ? filled(this) : this, arguments); };
  HTMLCanvasElement.prototype.toDataURL = function () { return tu0.apply(DONE.has(this) ? filled(this) : this, arguments); };

  function setup(ctx, S) {
    var r = R[cur], W = r[0], H = r[1], one = cur === '11', cap = +window.CARD_RATIO_CAP || 99;
    var x0 = 70, x1 = 1010, y0 = 95, y1 = one ? 1165 : 1235, m = 40, TB = window.CARD_RATIO_TB || 285, FB = 1165;
    var sy = (H - 2 * m) / (y1 - y0), sx = Math.min((W - 2 * m) / (x1 - x0), sy * cap);
    var c = { edge: true, S: S, W: W, H: H, one: one, sx: sx, sy: sy, k: sy / sx, tx: W / 2 - (x0 + x1) / 2 * sx, ty: m - y0 * sy, x0: x0, m: m, TB: TB, FB: FB };
    var cv = ctx.canvas; cv.width = W * S; cv.height = H * S;         // 크기를 바꾸면 그리기 상태가 처음으로 돌아간다
    M.set(ctx, c); DONE.add(cv); base(ctx, c, 1, 0, 0, 1, 0, 0);
  }
  function base(ctx, c, a, b, cc, d, e, f) {      // 1080×1350 기준 변환 → 실제 픽셀
    var S = c.S; O.setTransform.call(ctx, S * c.sx * a, S * c.sy * b, S * c.sx * cc, S * c.sy * d, S * (c.sx * e + c.tx), S * (c.sy * f + c.ty));
  }
  // 지금 변환에서 (x, y) 가 제목·바닥 줄이면 펼치지 않은 x 로 바꾼다. ly: 1080×1350 기준 세로 위치
  function band(ctx, c, x, y) {
    var t = O.getTransform.call(ctx), dx = t.a * x + t.c * y + t.e, dy = t.b * x + t.d * y + t.f;
    var ly = (dy / c.S - c.ty) / c.sy, lx = (dx / c.S - c.tx) / c.sx, fpx = +((/(\d+(?:\.\d+)?)px/.exec(ctx.font) || [])[1] || 0);
    var edge = ly < c.TB || ly > c.FB || (ly < 420 && fpx >= 40);   // 큰 글자의 둘째 줄 제목도 제목으로
    c.edge = edge; c.ly = ly;
    if (!edge) return x;
    var want = c.S * (c.m + (lx - c.x0) * c.sy);
    return x + (want - dx) / t.a;
  }
  P.scale = function (a, b) {
    var cv = this.canvas, S = a;
    if (cur !== '45' && a === b && a >= 2 && a <= 4 && cv && cv.width === 1080 * S && cv.height === 1350 * S && !M.has(this) && cv !== window.__cardRatioSkip) { setup(this, S); return; }
    return O.scale.apply(this, arguments);
  };
  P.setTransform = function () {
    var c = M.get(this); if (!c) return O.setTransform.apply(this, arguments);
    var a = arguments; if (a.length === 1) { var t = a[0]; a = [t.a, t.b, t.c, t.d, t.e, t.f]; }
    if (a[0] === 1 && a[3] === 1 && !a[1] && !a[2] && !a[4] && !a[5]) return base(this, c, 1, 0, 0, 1, 0, 0);
    base(this, c, a[0] / c.S, a[1] / c.S, a[2] / c.S, a[3] / c.S, a[4] / c.S, a[5] / c.S);   // 이미 S배로 준 변환
  };
  P.resetTransform = function () { var c = M.get(this); if (!c) return O.resetTransform.call(this); base(this, c, 1, 0, 0, 1, 0, 0); };
  function txt(fn) {
    return function (t, x, y, mw) {
      var c = M.get(this); if (!c) return fn.apply(this, arguments);
      if (/@돈굴/.test(String(t))) return;
      x = band(this, c, x, y);
      if (c.one && c.ly > c.FB) return;                                // 1:1 은 출처 줄도 뺀다
      this.save(); this.translate(x, y); if (!c.edge) O.scale.call(this, c.k, 1); else O.scale.call(this, c.k, 1);
      fn.call(this, t, 0, 0, mw == null ? undefined : mw / c.k); this.restore();
    };
  }
  P.fillText = txt(O.fillText); P.strokeText = txt(O.strokeText);
  P.measureText = function (t) {
    var r = O.measureText.call(this, t), c = M.get(this); if (!c || c.edge) return r;
    var w = r.width * c.k;
    return new Proxy(r, { get: function (tg, p) { return p === 'width' ? w : (typeof tg[p] === 'function' ? tg[p].bind(tg) : tg[p]); } });
  };
  P.arc = function (x, y, rad, a0, a1, ccw) { var c = M.get(this); if (!c) return O.arc.apply(this, arguments); this.ellipse(band(this, c, x, y), y, rad * c.k, rad, 0, a0, a1, ccw); };
  P.drawImage = function () {
    var c = M.get(this), a = Array.prototype.slice.call(arguments); if (!c || a.length < 5) return O.drawImage.apply(this, a);
    var n = a.length, dw = a[n - 2], dh = a[n - 1];
    if (dw >= 900 && dh >= 1100) { this.save(); O.setTransform.call(this, 1, 0, 0, 1, 0, 0); a[n - 4] = 0; a[n - 3] = 0; a[n - 2] = c.W * c.S; a[n - 1] = c.H * c.S; O.drawImage.apply(this, a); this.restore(); return; }   // 종이결 바탕은 펼친다
    var cx = band(this, c, a[n - 4] + dw / 2, a[n - 3] + dh / 2), nw = dw * c.k;
    if (c.one && c.ly > c.FB) return;
    a[n - 4] = cx - nw / 2; a[n - 2] = nw; return O.drawImage.apply(this, a);
  };
  P.fillRect = function (x, y, w, h) {
    var c = M.get(this); if (!c) return O.fillRect.apply(this, arguments);
    if (w >= 1000 && h >= 1100 || w >= c.W * c.S * 0.9) { this.save(); O.setTransform.call(this, 1, 0, 0, 1, 0, 0); O.fillRect.call(this, 0, 0, c.W * c.S, c.H * c.S); this.restore(); return; }
    if (c.one && h <= 3) { band(this, c, x, y); if (c.ly > c.FB) return; }   // 1:1: 바닥 줄 위 가는 선도 뺀다
    return O.fillRect.apply(this, arguments);
  };
  P.putImageData = function (im, x, y) {
    var c = M.get(this); if (!c || im.width < 1000) return O.putImageData.apply(this, arguments);
    var t = document.createElement('canvas'); t.width = im.width; t.height = im.height; t.getContext('2d').putImageData(im, 0, 0);
    this.save(); O.setTransform.call(this, 1, 0, 0, 1, 0, 0); O.drawImage.call(this, t, 0, 0, c.W * c.S, c.H * c.S); this.restore();
  };
  P.stroke = function () {
    var c = M.get(this); if (!c) return O.stroke.apply(this, arguments);
    this.save(); var t = O.getTransform.call(this); O.setTransform.call(this, t.a * c.k, 0, 0, t.d, 0, 0); O.stroke.apply(this, arguments); this.restore();   // 선 굵기는 세로 배율로만
  };

  // ---- 저장 단추 옆 '비율' 고르기
  function mount() {
    var btn = document.getElementById('btn-png') || document.getElementById('c-dl') || document.getElementById('dl');
    if (!btn || document.getElementById('card-ratio')) return;
    var w = document.createElement('label'); w.className = 'card-ratio'; w.style.cssText = 'display:flex;align-items:center;gap:8px;font-weight:700;font-size:14px;margin:6px 0';
    w.innerHTML = '비율 <select id="card-ratio" style="flex:1;min-height:38px;border-radius:6px;padding:4px 8px;font:inherit">' +
      Object.keys(R).map(function (k) { return '<option value="' + k + '"' + (k === cur ? ' selected' : '') + '>' + R[k][2] + ' (' + R[k][0] + '×' + R[k][1] + ')' + (k === '45' ? ' · 기본' : k === '11' ? ' · 출처 없이' : '') + '</option>'; }).join('') + '</select>';
    btn.parentNode.insertBefore(w, btn);
    w.querySelector('select').addEventListener('change', function () { cur = this.value; try { localStorage.setItem('cardRatio', cur); } catch (e) { /* 무시 */ } label(); });
    function label() {     // 단추 글자의 크기 표시도 고른 비율로
      var r = R[cur], m = btn.textContent.match(/\((\d+)×(\d+)\)/);
      if (m) btn.textContent = btn.textContent.replace(m[0], '(' + r[0] * 3 + '×' + r[1] * 3 + ')');
    }
    label();
  }
  window.CardRatio = { get: function () { return cur; }, set: function (k) { if (R[k]) cur = k; }, sizes: R };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
