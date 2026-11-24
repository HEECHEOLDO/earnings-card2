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
    var tx = W / 2 - (x0 + x1) / 2 * sx;
    if (window.CARD_RATIO_FLEX && !one) {          // 넓은 폭을 아는 그림(가로 막대 등): 펼치지 않고 그 그림이 오른쪽 끝을 넓혀 그린다
      sx = sy; tx = m - x0 * sy;
      ctx.__cardR = (W - m - tx) / sx - (x1 - 980);
    } else ctx.__cardR = 0;
    ctx.__cardAR = W / H; ctx.__cardBoost = 0; ctx.__cardK = sy / sx;   // 가로 1 이 세로 1 의 몇 배로 그려지는지 (원·간격을 맞출 때)                           // 그리는 쪽이 넓은 비율인지 알 수 있게 (두 열로 나누기 등)
    var c = { boost: W / H > 1.2 && !(+window.CARD_RATIO_CAP), edge: true, S: S, W: W, H: H, one: one, sx: sx, sy: sy, k: sy / sx, tx: tx, ty: m - y0 * sy, x0: x0, m: m, TB: TB, FB: FB, y1: y1 };
    var cv = ctx.canvas; cv.width = W * S; cv.height = H * S;         // 크기를 바꾸면 그리기 상태가 처음으로 돌아간다
    M.set(ctx, c); DONE.add(cv); base(ctx, c, 1, 0, 0, 1, 0, 0);
  }
  function base(ctx, c, a, b, cc, d, e, f) {      // 1080×1350 기준 변환 → 실제 픽셀
    var S = c.S; O.setTransform.call(ctx, S * c.sx * a, S * c.sy * b, S * c.sx * cc, S * c.sy * d, S * (c.sx * e + c.tx), S * (c.sy * f + c.ty));
  }
  // 지금 변환에서 (x, y) 가 제목·바닥 줄이면 펼치지 않은 x 로 바꾼다. ly: 1080×1350 기준 세로 위치
  // (x, y) 가 제목·바닥 줄인지 — ly: 1080×1350 기준 세로 위치
  function band(ctx, c, x, y, isText) {
    var t = O.getTransform.call(ctx), dy = t.b * x + t.d * y + t.f;
    var ly = (dy / c.S - c.ty) / c.sy, fpx = +((/(\d+(?:\.\d+)?)px/.exec(ctx.font) || [])[1] || 0);
    c.edge = ly < c.TB || ly > c.FB || (isText && window.CARD_RATIO_BIGTITLE !== false && ly < 340 && fpx >= 40);   // 큰 글자의 둘째 줄 제목도 제목으로
    c.ly = ly;
    return c.edge;
  }
  // 제목·바닥 줄은 펼치지 않는다: 지금 변환 앞에 '가로를 세로 배율로 되돌리고 왼쪽 끝에 붙이는' 변환을 얹어 원래 함수로 그린다
  // (회전·원·국기 그림도 그대로 맞는다)
  function asEdge(ctx, c, fn, args) {
    var t = O.getTransform.call(ctx), k = c.k, e0 = c.S * (c.m - c.x0 * c.sy) - k * c.S * c.tx;
    ctx.save(); O.setTransform.call(ctx, k * t.a, t.b, k * t.c, t.d, k * t.e + e0, t.f);
    var r = fn.apply(ctx, args); ctx.restore(); return r;
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
  // 넓은 비율(7:5·16:9)은 세로가 1080 이라 글자가 4:5 의 88% 로 줄어든다. 큰 글자(제목·큰 숫자)는 그래도 충분하지만
  // 축 눈금·날짜·작은 숫자(30px 이하)는 15~16px 까지 내려가 읽기 어렵다 → 작은 글자만 키운다 (26px 이상 14% · 18px 이하 38%).
  // 그림이 가로로 넓어져 자리가 남는다. 제목 줄(꼬리표 글자 등 바탕 칸이 따로 있는 글자)은 건드리지 않는다.
  function boostPx(px) { return px <= 30 ? px * (1.14 + 0.24 * Math.max(0, Math.min(1, (26 - px) / 8))) : px; }   // 4:5 와 같은 크기(÷0.88)에 더해 작은 글자일수록 더 — 18px 은 38%, 22px 은 26%, 26px 이상은 14%
  function boosted(ctx, c) {
    if (!c.boost) return null;
    var f = ctx.font, m = /(\d+(?:\.\d+)?)px/.exec(f); if (!m) return null;
    var px = +m[1], nx = boostPx(px); if (nx === px) return null;
    ctx.font = f.replace(m[0], (Math.round(nx * 10) / 10) + 'px'); return f;
  }
  function txt(fn) {
    return function (t, x, y, mw) {
      if (this.canvas === DISP) poke();
      var c = M.get(this); if (!c) return fn.apply(this, arguments);
      if (/@돈굴/.test(String(t))) return;
      if (band(this, c, x, y, true)) {
        if (c.one && c.ly > c.FB) return;                                                     // 1:1 은 출처 줄도 뺀다
        var f0 = c.ly > c.FB ? boosted(this, c) : null, lift = c.ly > c.y1 - 8 ? c.y1 - 8 - c.ly : 0;   // 바닥 출처 줄은 키운다
        if (lift) { this.save(); this.translate(0, lift); }        // 4:5 맨 아래(1318 등)에 적은 출처는 넓은 비율에서 화면 밖 — 안으로 올린다 (주주 탭)
        var r0 = asEdge(this, c, fn, arguments); if (lift) this.restore();
        if (f0) this.font = f0; return r0;
      }
      var f1 = boosted(this, c);
      this.save(); this.translate(x, y); O.scale.call(this, c.k, 1);
      fn.call(this, t, 0, 0, mw == null ? undefined : mw / c.k); this.restore();
      if (f1) this.font = f1;
    };
  }
  P.fillText = txt(O.fillText); P.strokeText = txt(O.strokeText);
  P.measureText = function (t) {
    var c = M.get(this); if (!c || c.edge) return O.measureText.call(this, t);
    var f1 = boosted(this, c), r = O.measureText.call(this, t); if (f1) this.font = f1;   // 키워 그릴 글자는 키운 폭으로 잰다 (자리 맞춤·줄이기가 맞게)
    var w = r.width * c.k;
    return new Proxy(r, { get: function (tg, p) { return p === 'width' ? w : (typeof tg[p] === 'function' ? tg[p].bind(tg) : tg[p]); } });
  };
  P.arc = function (x, y, rad, a0, a1, ccw) {
    var c = M.get(this); if (!c) return O.arc.apply(this, arguments);
    if (band(this, c, x, y)) return asEdge(this, c, O.arc, arguments);
    this.ellipse(x, y, rad * c.k, rad, 0, a0, a1, ccw);
  };
  P.drawImage = function () {
    if (this.canvas === DISP) poke();
    var c = M.get(this), a = Array.prototype.slice.call(arguments); if (!c) return O.drawImage.apply(this, a);
    if (a.length === 3) { var im0 = a[0]; a.push(im0.width || im0.naturalWidth || 0, im0.height || im0.naturalHeight || 0); }   // drawImage(그림, x, y) 도 크기를 붙여서 (종이결 바탕이 이 꼴)
    var n = a.length, dw = a[n - 2], dh = a[n - 1];
    if (dw >= 900 && dh >= 1100) { this.save(); O.setTransform.call(this, 1, 0, 0, 1, 0, 0); a[n - 4] = 0; a[n - 3] = 0; a[n - 2] = c.W * c.S; a[n - 1] = c.H * c.S; O.drawImage.apply(this, a); this.restore(); return; }   // 종이결 바탕은 펼친다
    if (band(this, c, a[n - 4] + dw / 2, a[n - 3] + dh / 2)) { if (c.one && c.ly > c.FB) return; return asEdge(this, c, O.drawImage, a); }
    var cx = a[n - 4] + dw / 2, nw = dw * c.k;
    a[n - 4] = cx - nw / 2; a[n - 2] = nw; return O.drawImage.apply(this, a);
  };
  P.fillRect = function (x, y, w, h) {
    if (this.canvas === DISP) poke();
    var c = M.get(this); if (!c) return O.fillRect.apply(this, arguments);
    if (w >= 1000 && h >= 1100 || w >= c.W * c.S * 0.9) { this.save(); O.setTransform.call(this, 1, 0, 0, 1, 0, 0); O.fillRect.call(this, 0, 0, c.W * c.S, c.H * c.S); this.restore(); return; }
    if (c.one && h <= 3 && band(this, c, x, y) && c.ly > c.FB) return;
    if (band(this, c, x + w / 2, y + h / 2) && h <= 80 && w <= 700) { if (c.one && c.ly > c.FB) return; return asEdge(this, c, O.fillRect, arguments); }   // 제목 옆 작은 칸(꼬리표 등)도 제목과 같이 · 1:1 은 바닥 가는 선도 뺀다
    return O.fillRect.apply(this, arguments);
  };
  // 제목 옆 꼬리표 바탕(둥근 칸)도 글자와 같이 왼쪽 끝에 붙인다 — 길에 넣는 순간의 변환으로 점이 정해지므로 asEdge 로 감싸면 된다
  // (예: '그때 샀다면' 제목 옆 '2016 ~ 2026년' 바탕이 글자와 떨어져 길게 늘어나던 것)
  if (P.roundRect) {
    O.roundRect = P.roundRect;
    P.roundRect = function (x, y, w, h) {
      var c = M.get(this); if (!c) return O.roundRect.apply(this, arguments);
      if (band(this, c, x + w / 2, y + h / 2) && h <= 80 && w <= 700) return asEdge(this, c, O.roundRect, arguments);
      return O.roundRect.apply(this, arguments);
    };
  }
  P.putImageData = function (im, x, y) {
    var c = M.get(this); if (!c || im.width < 1000) return O.putImageData.apply(this, arguments);
    var t = document.createElement('canvas'); t.width = im.width; t.height = im.height; t.getContext('2d').putImageData(im, 0, 0);
    this.save(); O.setTransform.call(this, 1, 0, 0, 1, 0, 0); O.drawImage.call(this, t, 0, 0, c.W * c.S, c.H * c.S); this.restore();
  };
  P.stroke = function () {
    var c = M.get(this); if (!c) return O.stroke.apply(this, arguments);
    this.save(); var t = O.getTransform.call(this); O.setTransform.call(this, t.a * c.k, 0, 0, t.d, 0, 0); O.stroke.apply(this, arguments); this.restore();   // 선 굵기는 세로 배율로만
  };

  // ---- 미리보기: 4:5 가 아니면 화면 카드 대신 '저장될 그림'을 보여 준다
  //   저장 단추를 몰래 눌러 만든 그림(내려받기는 막는다)을 화면 카드 자리에 띄운다. 카드가 다시 그려지면 잠시 뒤 다시 만든다.
  var DISP = null, IMG = null, BTN = null, CAP = 0, busy = 0, tmr = 0;
  var aclick = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function () {
    if (CAP && this.download) { CAP = 0; show(this.href); if (pend) setTimeout(refresh, 50); return; }
    return aclick.apply(this, arguments);
  };
  function show(url) {
    if (!IMG) return;
    var im = new Image(); im.onload = function () { IMG.src = im.src; busy = Date.now(); }; im.src = url;
  }
  function poke() {
    if (cur === '45' || !BTN) return;
    if (CAP) { pend = 1; return; }
    if (Date.now() - busy < 700) return;
    clearTimeout(tmr); tmr = setTimeout(refresh, 450);
  }
  var pend = 0;
  function refresh() {
    if (cur === '45' || !BTN) return;
    if (CAP) { pend = 1; return; }                // 만드는 중이면 끝난 뒤 한 번 더
    var tok = CAP = Date.now(); busy = tok; pend = 0;
    try { BTN.click(); } catch (e) { CAP = 0; }
    setTimeout(function () { if (CAP === tok) CAP = 0; if (pend) refresh(); }, 4000);
  }
  function view() {
    if (!DISP) return;
    var on = cur !== '45';
    if (!IMG) {
      IMG = document.createElement('img'); IMG.alt = '저장될 카드 미리보기';
      IMG.className = DISP.className; IMG.style.cssText = DISP.style.cssText;
      IMG.style.width = '100%'; IMG.style.height = 'auto'; IMG.style.display = 'none';
      DISP.parentNode.insertBefore(IMG, DISP.nextSibling);
    }
    DISP.style.display = on ? 'none' : ''; IMG.style.display = on ? 'block' : 'none';
    if (on) refresh();
  }

  // ---- 저장 단추 옆 '비율' 고르기
  function mount() {
    var btn = document.getElementById('btn-png') || document.getElementById('c-dl') || document.getElementById('dl');
    if (!btn || document.getElementById('card-ratio')) return;
    var w = document.createElement('label'); w.className = 'card-ratio'; w.style.cssText = 'display:flex;align-items:center;gap:8px;font-weight:700;font-size:14px;margin:6px 0';
    w.innerHTML = '비율 <select id="card-ratio" style="flex:1;min-height:38px;border-radius:6px;padding:4px 8px;font:inherit">' +
      Object.keys(R).map(function (k) { return '<option value="' + k + '"' + (k === cur ? ' selected' : '') + '>' + R[k][2] + ' (' + R[k][0] + '×' + R[k][1] + ')' + (k === '45' ? ' · 기본' : k === '11' ? ' · 출처 없이' : '') + '</option>'; }).join('') + '</select>';
    btn.parentNode.insertBefore(w, btn);
    BTN = btn;
    DISP = ['card', 'card-canvas', 'cv'].map(function (id) { return document.getElementById(id); }).filter(function (c) { return c && c.tagName === 'CANVAS'; })[0] || null;
    var note = document.createElement('div'); note.style.cssText = 'font-size:12px;opacity:.7;margin:-2px 0 6px'; note.textContent = '4:5 가 아니면 미리보기도 그 비율로 보여요 · 사진 위치 옮기기는 4:5 에서';
    btn.parentNode.insertBefore(note, btn);
    w.querySelector('select').addEventListener('change', function () { cur = this.value; try { localStorage.setItem('cardRatio', cur); } catch (e) { /* 무시 */ } label(); view(); });
    function label() {     // 단추 글자의 크기 표시도 고른 비율로
      var r = R[cur], m = btn.textContent.match(/\((\d+)×(\d+)\)/);
      if (m) btn.textContent = btn.textContent.replace(m[0], '(' + r[0] * 3 + '×' + r[1] * 3 + ')');
    }
    label();
    if (cur !== '45') setTimeout(view, 1500);   // 처음 그릴 때까지 기다렸다가
  }
  window.CardRatio = { get: function () { return cur; }, set: function (k) { if (R[k]) cur = k; }, sizes: R };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
