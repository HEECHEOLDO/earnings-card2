/* 카드 위에 사진 얹기 + 배경 지우기 — 국내·해외 실적 탭의 '이미지 넣기'를 그대로 옮겨 여러 탭이 같이 쓴다.
   (인포그래픽 · 돈의 흐름 탭은 CardOverlay.attach, 나머지 탭은 배경 지우기만 CardBg.remove 를 같이 쓴다)

   튕김(탭이 죽고 새로고침) 원인과 막는 법
   1) 폰 사진 원본(1200만~5000만 화소)을 통째로 풀면 그것만으로 수백 MB → 넣을 때 줄여서 푼다(createImageBitmap 축소 해독).
   2) 배경 지우기 모델 + 런타임이 200MB 넘게 잡는다 → 워커에서 돌리고 끝나면 워커를 없애 메모리를 돌려받는다.
   3) 워커가 도중에 죽었는데 페이지 안에서 한 번 더 돌리면 거의 확실히 탭이 죽는다 → 워커를 '못 만든' 경우에만 페이지 안에서 돌린다.
   4) 폰의 GPU 경로(WebGPU)는 메모리를 더 쓰고 불안정 → 폰은 CPU, 입력도 1024px 로 줄여서 보낸다(모델 입력이 1024px).
   5) 두 번 연달아 누르기 · 여러 장 동시 처리 → 한 번에 하나만.
   6) 그래도 죽으면: 넣은 사진을 세션 저장소에 작게 보관해 두었다가 다시 열릴 때 되살리고 이유를 알려준다. */
(function () {
  var BG_CDN = 'https://cdn.jsdelivr.net/npm/@imgly/background-removal@1.5.8/+esm';
  var IS_PHONE = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent) ||
    (navigator.maxTouchPoints > 1 && Math.min(screen.width, screen.height) < 900);
  var BG_MAX = IS_PHONE ? 1024 : 1600;            // 배경 지우기에 보내는 크기
  var OV_MAX = 1600;                              // 카드에 얹는 사진 크기 (카드는 가로 1080)
  var SAVE_MAX = 560;                             // 새로고침 대비 보관본 (세션 저장소 5MB 안)

  /* ---------------------------------------------------------------- 사진 줄여서 풀기 */
  function scaledBlob(source, max, type) {         // source: Blob 또는 Image/ImageBitmap → 긴 변 max 이하 Blob
    function fromDrawable(d, w, h) {
      var s = Math.min(1, max / Math.max(w, h)), c = document.createElement('canvas');
      c.width = Math.max(1, Math.round(w * s)); c.height = Math.max(1, Math.round(h * s));
      c.getContext('2d').drawImage(d, 0, 0, c.width, c.height);
      return new Promise(function (res) { c.toBlob(function (b) { c.width = c.height = 0; res(b); }, type || 'image/png'); });
    }
    if (source instanceof Blob) {
      return decodeSmall(source, max).then(function (bm) {
        var w = bm.width || bm.naturalWidth, h = bm.height || bm.naturalHeight;
        return fromDrawable(bm, w, h).then(function (b) { if (bm.close) bm.close(); return b; });
      });
    }
    return fromDrawable(source, source.naturalWidth || source.width, source.naturalHeight || source.height);
  }
  // 큰 사진을 원본 크기로 풀지 않도록: 크기만 먼저 읽고(머리말만 읽음) 줄인 크기로 해독한다
  function readSize(blob) {
    return new Promise(function (res) {
      var u = URL.createObjectURL(blob), im = new Image();
      im.onload = function () { var r = { w: im.naturalWidth, h: im.naturalHeight }; URL.revokeObjectURL(u); im.src = ''; res(r); };
      im.onerror = function () { URL.revokeObjectURL(u); res(null); };
      im.src = u;
    });
  }
  function decodeSmall(blob, max) {
    return readSize(blob).then(function (sz) {
      if (!sz) throw new Error('이미지를 열 수 없습니다');
      var s = Math.min(1, max / Math.max(sz.w, sz.h));
      if (window.createImageBitmap) {
        var o = s < 1 ? { resizeWidth: Math.round(sz.w * s), resizeHeight: Math.round(sz.h * s), resizeQuality: 'high' } : undefined;
        return (o ? createImageBitmap(blob, o) : createImageBitmap(blob)).then(function (bm) {
          if (s < 1 && Math.max(bm.width, bm.height) > max * 1.05) {      // 축소 옵션을 무시하는 브라우저
            var c = document.createElement('canvas'); c.width = Math.round(sz.w * s); c.height = Math.round(sz.h * s);
            c.getContext('2d').drawImage(bm, 0, 0, c.width, c.height); bm.close(); return c;
          }
          return bm;
        }).catch(function () { return viaImg(blob, s); });
      }
      return viaImg(blob, s);
    });
  }
  function viaImg(blob, s) {
    return new Promise(function (res, rej) {
      var u = URL.createObjectURL(blob), im = new Image();
      im.onload = function () {
        var c = document.createElement('canvas'); c.width = Math.max(1, Math.round(im.naturalWidth * s)); c.height = Math.max(1, Math.round(im.naturalHeight * s));
        c.getContext('2d').drawImage(im, 0, 0, c.width, c.height); URL.revokeObjectURL(u); im.src = ''; res(c);
      };
      im.onerror = function () { URL.revokeObjectURL(u); rej(new Error('이미지를 열 수 없습니다')); };
      im.src = u;
    });
  }
  function blobToImg(blob) {
    return new Promise(function (res, rej) { var im = new Image(); im.onload = function () { res(im); }; im.onerror = rej; im.src = URL.createObjectURL(blob); });
  }

  /* ---------------------------------------------------------------- 배경 지우기 (공용) */
  var _lib = null, _workerBroken = false, _busy = false;
  function loadLib() { return _lib ? Promise.resolve(_lib) : import(BG_CDN).then(function (m) { _lib = m; return m; }); }
  function device() { return IS_PHONE ? 'cpu' : 'gpu'; }

  function inWorker(src, model, onProgress) {
    return new Promise(function (resolve, reject) {
      if (_workerBroken || typeof Worker === 'undefined') { reject(new Error('worker-unavailable')); return; }
      var code =
        "let lib=null;\n" +
        "self.onmessage = async (e) => {\n" +
        "  try {\n" +
        "    self.postMessage({ up: 1 });\n" +
        "    if (!lib) lib = await import(e.data.cdn);\n" +
        "    const out = await lib.removeBackground(e.data.src, {\n" +
        "      model: e.data.model, device: e.data.device,\n" +
        "      output: { format: 'image/png', quality: 1 },\n" +
        "      progress: (k, c, t) => self.postMessage({ p: 1, k: k, c: c, t: t })\n" +
        "    });\n" +
        "    self.postMessage({ ok: 1, blob: out });\n" +
        "  } catch (err) {\n" +
        "    self.postMessage({ err: String((err && err.message) || err) });\n" +
        "  }\n" +
        "};\n";
      var wUrl = null, w = null, done = false, alive = false, dog = null;
      function kick() { clearTimeout(dog); dog = setTimeout(function () { finish(reject, new Error('응답이 없어 멈췄습니다 (3분)')); }, 180000); }   // 멈춘 채로 붙잡혀 있지 않게
      function finish(fn, arg) {
        if (done) return; done = true; clearTimeout(dog);
        try { if (w) w.terminate(); } catch (e) {}          // ← 여기서 메모리가 돌아온다
        try { if (wUrl) URL.revokeObjectURL(wUrl); } catch (e) {}
        w = null; fn(arg);
      }
      try {
        wUrl = URL.createObjectURL(new Blob([code], { type: 'text/javascript' }));
        w = new Worker(wUrl, { type: 'module' });
      } catch (e) { _workerBroken = true; finish(reject, new Error('worker-create-failed')); return; }
      w.onerror = function (ev) {
        if (ev && ev.preventDefault) ev.preventDefault();
        // 워커가 아예 못 뜬 경우에만 '페이지 안에서' 다시 해 본다. 돌다가 죽은 거면 메모리 부족일 가능성이 커서 다시 하면 탭이 죽는다.
        if (!alive) { _workerBroken = true; finish(reject, new Error('worker-error')); }
        else finish(reject, new Error('메모리가 모자라 멈췄습니다'));
      };
      w.onmessage = function (ev) {
        var d = ev.data || {}; alive = true; kick();
        if (d.up) return;
        if (d.p) { onProgress(d.k, d.c, d.t); return; }
        if (d.err) { finish(reject, new Error(d.err)); return; }
        if (d.ok) finish(resolve, d.blob);
      };
      kick(); w.postMessage({ src: src, model: model, cdn: BG_CDN, device: device() });
    });
  }

  /* 누끼 다듬기 — 가벼운 모델(빠름)은 배경에 반투명 얼룩·자잘한 점을 남긴다 (어두운 카드 위에선 머리카락이 날리는 것처럼 보인다).
     ① 아주 옅은 픽셀은 지우고 ② 사람(큰 덩어리)과 떨어진 작은 조각은 버리고 ③ 덩어리 둘레 몇 px 밖의 반투명은 지운다.
     덩어리는 여러 개(두 사람)여도 큰 것 대비 3% 넘으면 남긴다. */
  function cleanCut(blob) {
    return new Promise(function (resolve) {
      var url = URL.createObjectURL(blob), img = new Image();
      img.onload = function () {
        try {
          var w = img.naturalWidth, h = img.naturalHeight, n = w * h;
          var cv = document.createElement('canvas'); cv.width = w; cv.height = h; cv.__noTheme = true;
          var x = cv.getContext('2d'); x.drawImage(img, 0, 0);
          var id = x.getImageData(0, 0, w, h), px = id.data, i;
          var lab = new Int32Array(n), stack = new Int32Array(n), sizes = [0], big = 0;
          for (i = 0; i < n; i++) if (px[i * 4 + 3] < 60) px[i * 4 + 3] = 0;
          for (i = 0; i < n; i++) {                         // 진한 픽셀끼리 이어진 덩어리 번호
            if (lab[i] || px[i * 4 + 3] < 128) continue;
            var id2 = sizes.length, sp = 0, cnt = 0; lab[i] = id2; stack[sp++] = i;
            while (sp) {
              var q = stack[--sp], qx = q % w; cnt++;
              if (qx > 0 && !lab[q - 1] && px[(q - 1) * 4 + 3] >= 128) { lab[q - 1] = id2; stack[sp++] = q - 1; }
              if (qx < w - 1 && !lab[q + 1] && px[(q + 1) * 4 + 3] >= 128) { lab[q + 1] = id2; stack[sp++] = q + 1; }
              if (q >= w && !lab[q - w] && px[(q - w) * 4 + 3] >= 128) { lab[q - w] = id2; stack[sp++] = q - w; }
              if (q < n - w && !lab[q + w] && px[(q + w) * 4 + 3] >= 128) { lab[q + w] = id2; stack[sp++] = q + w; }
            }
            sizes.push(cnt); if (cnt > big) big = cnt;
          }
          if (!big) { resolve(blob); return; }
          var keepMin = Math.max(big * 0.03, 30), keep = new Uint8Array(n);
          for (i = 0; i < n; i++) if (lab[i] && sizes[lab[i]] >= keepMin) keep[i] = 1;
          var r = Math.max(4, Math.round(Math.max(w, h) / 120)), tmp = new Uint8Array(n), yy, xx, k;   // 남길 덩어리를 r px 만큼 넓힌다 (머리카락 가장자리)
          for (yy = 0; yy < h; yy++) { var run = -1e9; for (xx = 0; xx < w; xx++) { if (keep[yy * w + xx]) run = xx; if (xx - run <= r) tmp[yy * w + xx] = 1; } run = 1e9; for (xx = w - 1; xx >= 0; xx--) { if (keep[yy * w + xx]) run = xx; if (run - xx <= r) tmp[yy * w + xx] = 1; } }
          var near = new Uint8Array(n);
          for (xx = 0; xx < w; xx++) { var rn = -1e9; for (yy = 0; yy < h; yy++) { if (tmp[yy * w + xx]) rn = yy; if (yy - rn <= r) near[yy * w + xx] = 1; } rn = 1e9; for (yy = h - 1; yy >= 0; yy--) { if (tmp[yy * w + xx]) rn = yy; if (rn - yy <= r) near[yy * w + xx] = 1; } }
          // 옅은 픽셀(60 이상)끼리 이어진 덩어리 중 사람에 닿지 않는 것은 통째로 버린다 — 머리카락처럼 사람에 붙은 가닥은 남는다
          var lab2 = new Int32Array(n), hit = [0], sp2, id3;
          for (i = 0; i < n; i++) {
            if (lab2[i] || !px[i * 4 + 3]) continue;
            id3 = hit.length; hit.push(0); sp2 = 0; lab2[i] = id3; stack[sp2++] = i;
            while (sp2) {
              var q2 = stack[--sp2], q2x = q2 % w; if (keep[q2]) hit[id3] = 1;
              if (q2x > 0 && !lab2[q2 - 1] && px[(q2 - 1) * 4 + 3]) { lab2[q2 - 1] = id3; stack[sp2++] = q2 - 1; }
              if (q2x < w - 1 && !lab2[q2 + 1] && px[(q2 + 1) * 4 + 3]) { lab2[q2 + 1] = id3; stack[sp2++] = q2 + 1; }
              if (q2 >= w && !lab2[q2 - w] && px[(q2 - w) * 4 + 3]) { lab2[q2 - w] = id3; stack[sp2++] = q2 - w; }
              if (q2 < n - w && !lab2[q2 + w] && px[(q2 + w) * 4 + 3]) { lab2[q2 + w] = id3; stack[sp2++] = q2 + w; }
            }
          }
          for (i = 0; i < n; i++) {
            k = i * 4 + 3;
            if (!px[k]) continue;
            if (lab[i] && !keep[i]) px[k] = 0;                // 떨어진 작은 조각
            else if (!hit[lab2[i]]) px[k] = 0;                // 사람에 닿지 않은 옅은 얼룩
            else if (!lab[i] && !near[i] && px[k] < 110) px[k] = 0;   // 사람에서 먼 아주 옅은 안개
          }
          x.putImageData(id, 0, 0);
          cv.toBlob(function (b2) { URL.revokeObjectURL(url); resolve(b2 || blob); }, 'image/png');
        } catch (e) { URL.revokeObjectURL(url); resolve(blob); }
      };
      img.onerror = function () { URL.revokeObjectURL(url); resolve(blob); };
      img.src = url;
    });
  }

  // src: Blob / Image — 줄여서 워커로 보내고, 투명 PNG Blob 을 돌려준다
  function removeBg(src, model, onProgress) {
    if (_busy) return Promise.reject(new Error('이미 배경을 지우는 중입니다'));
    _busy = true;
    if (IS_PHONE && model === 'isnet') model = 'isnet_fp16';
    if (IS_PHONE && model === 'isnet_fp16' && device() === 'cpu') model = 'isnet_quint8';    // 폰 CPU 는 가벼운 모델만
    onProgress = onProgress || function () {};
    // 주소(blob:/data:)로 온 사진도 받아서 줄인다 — 예전엔 주소면 원래 크기(1600px) 그대로 보내 폰 메모리가 튀었다
    var asBlob = typeof src === 'string' ? fetch(src).then(function (r) { return r.blob(); }).catch(function () { return src; }) : Promise.resolve(src);
    return asBlob.then(function (s0) {
      return s0 instanceof Blob || (s0 && s0.naturalWidth) ? scaledBlob(s0, BG_MAX) : s0;
    }).then(function (small) {
      return inWorker(small, model, onProgress).catch(function (e) {
        // 폰에서 돌다가 메모리로 멈췄으면 더 작게(720px) 새 워커로 한 번만 다시
        if (IS_PHONE && /메모리|응답이 없어/.test(e && e.message || '') && small instanceof Blob) {
          onProgress('compute', 0, 0);
          return scaledBlob(small, 720).then(function (tiny) { return inWorker(tiny, 'isnet_quint8', onProgress); });
        }
        if (!/worker-/.test(e && e.message || '')) throw e;
        return loadLib().then(function (lib) {
          return lib.removeBackground(small, { model: model, device: device(), output: { format: 'image/png', quality: 1 }, progress: onProgress });
        });
      });
    }).then(function (b) { return window.__noClean ? b : cleanCut(b); }).then(function (b) { _busy = false; return b; }, function (e) { _busy = false; throw e; });
  }
  window.CardBg = { remove: removeBg, isPhone: IS_PHONE, maxSide: BG_MAX, scaledBlob: scaledBlob, decodeSmall: decodeSmall };

  /* ---------------------------------------------------------------- 카드 위 사진 (인포그래픽·돈의 흐름 탭) */
  var CSS =
    '.ovx-sec{display:flex;flex-direction:column;gap:8px;border-top:1px solid var(--border,#e5e3dc);padding-top:12px;margin-top:2px}' +
    '.ovx-sec h4{margin:0;font-size:13px;font-weight:800;color:var(--text,#101216)}' +
    '.ovx-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}' +
    '.ovx-row input[type=file]{font-size:12px;max-width:100%;color:var(--text-soft,#6b7078);flex:1;min-width:0}' +
    '.ovx-btn{height:34px;padding:0 10px;font-family:inherit;font-size:12.5px;font-weight:700;border-radius:8px;cursor:pointer;' +
    'border:1px solid var(--border-strong,#d6d3ca);background:var(--surface,#fff);color:var(--text,#101216)}' +
    '.ovx-btn:hover{border-color:var(--accent,#2E6FD9);color:var(--accent,#2E6FD9)}' +
    '.ovx-btn:disabled{opacity:.5;cursor:default}' +
    '.ovx-danger{color:#B32B22;border-color:#E1B7B2}' +
    '.ovx-edit{display:none;flex-direction:column;gap:9px;padding:11px 13px;border-radius:9px;background:var(--surface-2,#f4f3ef);border:1px solid var(--border,#e5e3dc)}' +
    '.ovx-edit .r{display:flex;align-items:center;gap:10px}' +
    '.ovx-edit .l{font-size:12.5px;color:var(--text-soft,#6b7078);width:46px;flex:none;font-weight:600}' +
    '.ovx-edit input[type=range]{flex:1;min-width:0;margin:0;accent-color:var(--accent,#2E6FD9)}' +
    '.ovx-edit .v{font-size:12px;color:var(--text-soft,#6b7078);width:46px;text-align:right;flex:none}' +
    '.ovx-edit .b{display:flex;gap:6px;flex-wrap:wrap}.ovx-edit .b>*{flex:1 1 30%}' +
    '.ovx-edit select.ovx-btn{padding:0 8px}' +
    '.ovx-hint{font-size:12px;color:var(--text-mute,#8a8f96);line-height:1.6;margin:0}';

  function attach(opt) {
    var canvas = opt.canvas, CW = opt.width || canvas.width, CH = opt.height || canvas.height;
    var redraw = opt.redraw, KEY = 'fincard.ov.' + location.pathname, FLAG = 'fincard.bg.' + location.pathname;
    if (!document.getElementById('ovx-css')) { var st = document.createElement('style'); st.id = 'ovx-css'; st.textContent = CSS; document.head.appendChild(st); }

    var sec = document.createElement('div'); sec.className = 'ovx-sec';
    sec.innerHTML = '<h4>이미지 넣기</h4>' +
      '<div class="ovx-row"><input type="file" accept="image/*" multiple aria-label="이미지 고르기"><button class="ovx-btn ovx-danger" type="button" data-a="clear">전체 삭제</button></div>' +
      '<p class="ovx-hint">여러 장 올릴 수 있습니다. 미리보기에서 <b>끌어서 위치</b>를 잡고, 아래에서 크기·회전·투명도를 조절하세요. 빈 곳을 누르면 선택이 풀립니다.</p>' +
      '<div class="ovx-edit">' +
      '<div class="r"><span class="l">크기</span><input type="range" data-a="size" min="60" max="' + CW + '" step="4"><span class="v" data-v="size">–</span></div>' +
      '<div class="r"><span class="l">회전</span><input type="range" data-a="rot" min="-180" max="180" step="1"><span class="v" data-v="rot">–</span></div>' +
      '<div class="r"><span class="l">투명도</span><input type="range" data-a="op" min="10" max="100" step="1"><span class="v" data-v="op">–</span></div>' +
      '<div class="b"><button class="ovx-btn" type="button" data-a="rot0">0°</button><button class="ovx-btn" type="button" data-a="front">앞으로</button><button class="ovx-btn" type="button" data-a="back">뒤로</button>' +
      '<select class="ovx-btn" data-a="q" title="배경 지우기 품질"><option value="isnet_quint8">빠름</option><option value="isnet_fp16">보통</option><option value="isnet">최고</option></select>' +
      '<button class="ovx-btn" type="button" data-a="bg">배경 지우기</button><button class="ovx-btn" type="button" data-a="undo" style="display:none">원본으로</button>' +
      '<button class="ovx-btn ovx-danger" type="button" data-a="del">삭제</button></div>' +
      '<p class="ovx-hint" data-v="status" style="display:none"></p></div>';
    (opt.mount || canvas.parentNode).appendChild(sec);
    var q = function (s) { return sec.querySelector(s); }, edit = q('.ovx-edit'), fileIn = q('input[type=file]');
    var sel = q('[data-a=q]');
    if (IS_PHONE) { sel.value = 'isnet_quint8'; sel.querySelector('option[value=isnet]').disabled = true; sel.querySelector('option[value=isnet_fp16]').disabled = true; }
    else sel.value = 'isnet_fp16';

    var list = [], cur = -1;
    function status(t) { var el = q('[data-v=status]'); el.textContent = t || ''; el.style.display = t ? '' : 'none'; }
    function paint(X, back) {
      list.forEach(function (o) {
        if ((o.layer === 'back') !== back || !o.img) return;
        X.save(); X.globalAlpha = o.opacity == null ? 1 : o.opacity; X.translate(o.cx, o.cy); X.rotate(o.rot || 0);
        X.drawImage(o.img, -o.w / 2, -o.h / 2, o.w, o.h); X.restore();
      });
    }
    function paintSel(X) {
      var o = list[cur]; if (!o) return;
      X.save(); X.translate(o.cx, o.cy); X.rotate(o.rot || 0); X.strokeStyle = '#2E6FD9'; X.lineWidth = 4; X.setLineDash([12, 9]);
      X.strokeRect(-o.w / 2, -o.h / 2, o.w, o.h); X.restore();
    }
    function sync() {
      save();
      var o = list[cur];
      if (!o) { edit.style.display = 'none'; return; }
      edit.style.display = 'flex';
      q('[data-a=undo]').style.display = o.orig ? '' : 'none';
      q('[data-a=size]').value = Math.round(o.w); q('[data-v=size]').textContent = Math.round(o.w / CW * 100) + '%';
      var deg = Math.round((o.rot || 0) * 180 / Math.PI); q('[data-a=rot]').value = deg; q('[data-v=rot]').textContent = deg + '°';
      var op = o.opacity == null ? 1 : o.opacity; q('[data-a=op]').value = Math.round(op * 100); q('[data-v=op]').textContent = Math.round(op * 100) + '%';
    }

    // ---- 새로고침 대비 보관
    var saveT = null, restoring = false;
    function thumb(img, cut) {
      try {
        var w = img.naturalWidth || img.width, h = img.naturalHeight || img.height, s = Math.min(1, SAVE_MAX / Math.max(w, h)), c = document.createElement('canvas');
        c.width = Math.max(1, Math.round(w * s)); c.height = Math.max(1, Math.round(h * s)); c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
        var u = cut ? c.toDataURL('image/png') : c.toDataURL('image/jpeg', 0.85); c.width = c.height = 0; return u;
      } catch (e) { return null; }
    }
    function save(delay) {
      if (restoring) return;
      clearTimeout(saveT);
      saveT = setTimeout(function () {
        try {
          var out = [];
          list.forEach(function (o) { if (!o.keep) o.keep = thumb(o.img, o.cut); if (o.keep) out.push({ d: o.keep, aspect: o.aspect, layer: o.layer, opacity: o.opacity, rot: o.rot, w: o.w, h: o.h, cx: o.cx, cy: o.cy, cut: !!o.cut }); });
          if (out.length) sessionStorage.setItem(KEY, JSON.stringify(out)); else sessionStorage.removeItem(KEY);
        } catch (e) { /* 용량 초과면 보관을 포기 */ }
      }, delay || 400);
    }
    function restore() {
      var raw, died;
      try { raw = sessionStorage.getItem(KEY); died = sessionStorage.getItem(FLAG); sessionStorage.removeItem(FLAG); } catch (e) { return; }
      var tell = function () { if (died) status('배경을 지우다 메모리가 모자라 페이지가 다시 열렸습니다. 사진을 더 작게 잘라 넣거나 \'빠름\'으로 해 보세요.'); };
      var arr = null; try { arr = raw && JSON.parse(raw); } catch (e) {}
      if (!arr || !arr.length) { tell(); return; }
      restoring = true; var left = arr.length, box = [];
      arr.forEach(function (o, i) {
        var im = new Image();
        im.onload = function () { box[i] = { img: im, keep: o.d, aspect: o.aspect, layer: o.layer, opacity: o.opacity, rot: o.rot, w: o.w, h: o.h, cx: o.cx, cy: o.cy, cut: o.cut }; fin(); };
        im.onerror = fin; im.src = o.d;
      });
      function fin() { if (--left) return; box.forEach(function (b) { if (b) list.push(b); }); restoring = false; if (list.length) cur = list.length - 1; sync(); tell(); redraw(); }
    }

    // ---- 넣기
    var adding = Promise.resolve();
    fileIn.addEventListener('change', function () {
      var files = Array.prototype.slice.call(fileIn.files || []); fileIn.value = '';
      files.forEach(function (file, idx) {
        adding = adding.then(function () {              // 한 장씩 차례로 (여러 장 동시에 풀면 메모리가 튄다)
          status(files.length > 1 ? '사진 넣는 중… ' + (idx + 1) + '/' + files.length : '');
          return decodeSmall(file, OV_MAX).then(function (d) {
            return new Promise(function (res) { (d.toBlob ? d : (function () { var c = document.createElement('canvas'); c.width = d.width; c.height = d.height; c.getContext('2d').drawImage(d, 0, 0); if (d.close) d.close(); return c; })()).toBlob(res, 'image/png'); });
          }).then(function (blob) { return blobToImg(blob).then(function (im) { return [im, blob]; }); }).then(function (r) {
            var im = r[0], aspect = im.naturalWidth / im.naturalHeight || 1, w = Math.max(90, Math.min(CW * 0.25, im.naturalWidth));
            list.push({ img: im, src: r[1], aspect: aspect, layer: 'front', opacity: 1, rot: 0, w: w, h: w / aspect, cx: CW / 2 + idx * 30, cy: CH / 2 + idx * 30 });
            cur = list.length - 1; sync(); redraw(); status('');
            if (idx === 0) try { canvas.scrollIntoView({ behavior: 'smooth', block: 'start' }); } catch (x) {}
          }).catch(function () { status('이미지를 불러오지 못했습니다.'); });
        });
      });
    });
    function freeImg(o) { [o.img, o.orig].forEach(function (im) { if (im && /^blob:/.test(im.src || '')) try { URL.revokeObjectURL(im.src); } catch (e) {} }); }
    q('[data-a=clear]').addEventListener('click', function () { list.forEach(freeImg); list.length = 0; cur = -1; sync(); redraw(); });
    q('[data-a=del]').addEventListener('click', function () { if (cur < 0) return; freeImg(list[cur]); list.splice(cur, 1); cur = -1; sync(); redraw(); });
    q('[data-a=front]').addEventListener('click', function () { if (cur < 0) return; var o = list.splice(cur, 1)[0]; o.layer = 'front'; list.push(o); cur = list.length - 1; sync(); redraw(); });
    q('[data-a=back]').addEventListener('click', function () { if (cur < 0) return; var o = list.splice(cur, 1)[0]; o.layer = 'back'; list.unshift(o); cur = 0; sync(); redraw(); });
    q('[data-a=size]').addEventListener('input', function () { var o = list[cur]; if (!o) return; o.w = +this.value; o.h = o.w / o.aspect; q('[data-v=size]').textContent = Math.round(o.w / CW * 100) + '%'; redraw(); save(); });
    q('[data-a=rot]').addEventListener('input', function () { var o = list[cur]; if (!o) return; o.rot = +this.value * Math.PI / 180; q('[data-v=rot]').textContent = Math.round(+this.value) + '°'; redraw(); save(); });
    q('[data-a=rot0]').addEventListener('click', function () { var o = list[cur]; if (!o) return; o.rot = 0; sync(); redraw(); });
    q('[data-a=op]').addEventListener('input', function () { var o = list[cur]; if (!o) return; o.opacity = +this.value / 100; q('[data-v=op]').textContent = Math.round(o.opacity * 100) + '%'; redraw(); save(); });

    // ---- 배경 지우기
    q('[data-a=bg]').addEventListener('click', function () {
      var o = list[cur], btn = this; if (!o || !o.img) return;
      btn.disabled = true;
      var model = sel.value, lab = { isnet_quint8: '빠름 · 약 40MB', isnet_fp16: '보통 · 약 80MB', isnet: '최고 · 약 160MB' }[model] || '';
      status('준비 중… (' + lab + ' — 처음이면 내려받는 데 시간이 걸립니다)');
      if (!o.orig) { o.orig = o.img; o.origSrc = o.src; o.origKeep = o.keep; }
      try { sessionStorage.setItem(FLAG, JSON.stringify({ t: Date.now(), q: model })); } catch (e) {}
      save(1);
      removeBg(o.origSrc || o.orig, model, function (k, c, t) { status(/fetch/.test(k) ? '모델 내려받는 중 ' + (t ? Math.round(c / t * 100) : 0) + '%' : '배경 지우는 중…'); })
        .then(blobToImg).then(function (im) {
          if (o.img && o.img !== o.orig && /^blob:/.test(o.img.src)) try { URL.revokeObjectURL(o.img.src); } catch (e) {}
          o.img = im; o.cut = true; o.keep = null; status(''); sync(); save(1500); redraw();
        }).catch(function (e) {
          status('배경을 지우지 못했습니다: ' + (e && e.message || e)); setTimeout(function () { status(''); }, 5000);
        }).then(function () { btn.disabled = false; try { sessionStorage.removeItem(FLAG); } catch (e) {} });
    });
    q('[data-a=undo]').addEventListener('click', function () { var o = list[cur]; if (!o || !o.orig) return; o.img = o.orig; o.src = o.origSrc; o.keep = o.origKeep; o.cut = false; sync(); redraw(); });

    // ---- 끌어서 옮기기
    function xy(e) { var r = canvas.getBoundingClientRect(); return { x: (e.clientX - r.left) * (CW / r.width), y: (e.clientY - r.top) * (CH / r.height) }; }
    function hit(p) {
      for (var i = list.length - 1; i >= 0; i--) {
        var o = list[i], dx = p.x - o.cx, dy = p.y - o.cy, a = -(o.rot || 0);
        if (Math.abs(dx * Math.cos(a) - dy * Math.sin(a)) <= o.w / 2 && Math.abs(dx * Math.sin(a) + dy * Math.cos(a)) <= o.h / 2) return i;
      }
      return -1;
    }
    var drag = null;
    canvas.style.touchAction = 'none';
    canvas.addEventListener('pointerdown', function (e) {
      if (!list.length) return;
      var p = xy(e), h = hit(p);
      if (h >= 0) { cur = h; drag = { dx: p.x - list[h].cx, dy: p.y - list[h].cy }; try { canvas.setPointerCapture(e.pointerId); } catch (x) {} canvas.style.cursor = 'grabbing'; e.preventDefault(); }
      else cur = -1;
      sync(); redraw();
    }, { passive: false });
    canvas.addEventListener('pointermove', function (e) {
      if (drag && cur >= 0) { var p = xy(e), o = list[cur]; o.cx = Math.max(0, Math.min(CW, p.x - drag.dx)); o.cy = Math.max(0, Math.min(CH, p.y - drag.dy)); redraw(); e.preventDefault(); }
      else if (list.length) canvas.style.cursor = hit(xy(e)) >= 0 ? 'grab' : 'default';
    });
    function end(e) { if (!drag) return; drag = null; canvas.style.cursor = 'grab'; save(); try { canvas.releasePointerCapture(e.pointerId); } catch (x) {} }
    canvas.addEventListener('pointerup', end); canvas.addEventListener('pointercancel', end);

    setTimeout(restore, 0);
    return {
      paintBack: function (X) { paint(X, true); },
      paintFront: function (X) { paint(X, false); },
      paintSelection: paintSel,
      count: function () { return list.length; }
    };
  }
  window.CardOverlay = { attach: attach };
})();
