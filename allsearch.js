/* 실적 탭(국내·해외·비상장)의 '전체' 찾기 — 2026-11
   세부 탭 '전체'(주소 ?all=1)를 고르면 지금 화면의 검색창이 국내·해외·비상장 회사를 한꺼번에 찾는다.
   다른 시장 회사를 고르면 그 탭으로 옮겨 간다(?code=…&all=1 이라 '전체'가 그대로 유지된다). */
(function () {
  'use strict';
  var PAGE = { kr: './index.html', us: './us.html', ul: './unlisted.html' };
  var LB = { kr: '국내', us: '해외', ul: '비상장' };
  var ME = /unlisted\.html/.test(location.pathname) ? 'ul' : /us\.html/.test(location.pathname) ? 'us' : 'kr';
  var ON = /[?&]all=1\b/.test(location.search);
  function J(u) { return fetch(u, { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); }
  function ko() {
    if (window.US_KO) return Promise.resolve(window.US_KO);
    return new Promise(function (res) {
      var s = document.createElement('script'); s.src = './us_ko.js';
      s.onload = function () { res(window.US_KO || {}); }; s.onerror = function () { res({}); };
      document.head.appendChild(s);
    });
  }
  var A = { on: ON, me: ME, list: null, label: LB };
  A.load = function () {
    if (A._p) return A._p;
    A._p = Promise.all([J('./data/index.json'), J('./data/us/index.json'), J('./data/unlisted/index.json'), ko()]).then(function (r) {
      var out = [], K = r[3] || {};
      ((r[0] && r[0].companies) || []).forEach(function (c) { out.push({ m: 'kr', code: c.code, name: c.name, sub: c.code }); });
      ((r[1] && r[1].companies) || []).forEach(function (c) {
        var k = K[c.code] || K[String(c.code).replace('.', '-')];
        out.push({ m: 'us', code: c.code, name: k || c.name, sub: c.code + (c.legal_name ? ' · ' + c.legal_name : ''), alt: (c.legal_name || '') + ' ' + c.name });
      });
      ((r[2] && r[2].companies) || []).forEach(function (c) { out.push({ m: 'ul', code: c.code, name: c.name, sub: c.brand || c.sector || '', alt: c.brand || '' }); });
      A.list = out;
      return out;
    });
    return A._p;
  };
  A.search = function (q) {
    var list = A.list || [], s = String(q || '').trim().toLowerCase();
    if (!s) return list.slice();
    var out = [];
    list.forEach(function (c) {
      var n = c.name.toLowerCase(), k = String(c.code).toLowerCase(), r = -1;
      if (k === s) r = 0; else if (n === s) r = 1; else if (n.indexOf(s) === 0) r = 2;
      else if (k.indexOf(s) === 0) r = 3; else if (n.indexOf(s) >= 0) r = 4;
      else if ((c.alt || '').toLowerCase().indexOf(s) >= 0) r = 5;
      if (r >= 0) out.push({ c: c, r: r });
    });
    out.sort(function (a, b) { return a.r - b.r || a.c.name.localeCompare(b.c.name); });
    return out.map(function (x) { return x.c; });
  };
  function esc(t) { return String(t).replace(/[&<>"]/g, function (m) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]; }); }
  // 검색 목록 그리기 — 이 화면 회사는 그 화면의 회사 정보(Adapter.match)로, 다른 시장 회사는 옮겨 갈 주소(__go)로
  A.open = function (q, box, Adapter, setItems) {
    var hits = A.search(q).slice(0, 300), items = hits.map(function (c) {
      if (c.m === ME) return (Adapter && Adapter.match && Adapter.match(c.code)) || { name: c.name, code: c.code };
      return { name: c.name, code: c.code, __go: PAGE[c.m] + '?code=' + encodeURIComponent(c.code) + '&all=1' };
    });
    var n = { kr: 0, us: 0, ul: 0 }; (A.list || []).forEach(function (c) { n[c.m]++; });
    var html = '<div class="head">' + (String(q || '').trim() ? hits.length.toLocaleString() + '개 일치'
      : '전체 ' + (A.list || []).length.toLocaleString() + '곳 (국내 ' + n.kr.toLocaleString() + ' · 해외 ' + n.us.toLocaleString() + ' · 비상장 ' + n.ul.toLocaleString() + ') · 이름이나 코드를 입력해보세요') + '</div>';
    html += hits.length ? hits.map(function (c, i) {
      return '<li role="option" data-i="' + i + '"><span>' + esc(c.name) + '</span><span class="code">' + LB[c.m] + ' · ' + esc(c.sub || c.code) + '</span></li>';
    }).join('') : '<li class="empty">일치하는 회사가 없습니다</li>';
    box.innerHTML = html; box.style.display = 'block';
    setItems(items);
  };
  window.AllSearch = A;
  if (ON) A.load();
  // 세부 탭 표시: '전체'면 전체에 불, 아니면 지금 시장에 불
  function marks() {
    var sub = document.querySelector('.subnav'); if (!sub) return;
    Array.prototype.forEach.call(sub.querySelectorAll('a'), function (a) {
      var isAll = a.hasAttribute('data-all'), cur = !isAll && a.getAttribute('href') === PAGE[ME];
      var on = ON ? isAll : cur;
      a.classList.toggle('on', on);
      if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    var q = document.getElementById('q');
    if (ON && q) q.placeholder = '국내·해외·비상장 전체에서 회사 이름이나 코드 (눌러서 전체 보기)';
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', marks); else marks();
})();
