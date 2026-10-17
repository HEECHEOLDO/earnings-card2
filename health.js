/* 데이터 상태 한 줄 — 모든 화면의 메뉴 아래에 붙는다 (add_tab.py 가 넣는다).
   data/health.json (check_health.py 가 매일 아침 만든다)을 읽어
   ● 데이터 정상 · 10.18 09:12 점검   처럼 보여주고, 누르면 status.html 로 간다.
   이 화면과 관련된 탭에 문제가 있으면 그 내용을 앞에 적는다. 파일이 없으면 아무것도 안 그린다. */
(function () {
  var nav = document.querySelector('nav.nav');
  if (!nav || document.getElementById('health-line')) return;
  var page = (location.pathname.split('/').pop() || 'index.html');
  if (page === 'status.html') return;      // 상태 화면에는 이미 다 나온다

  var css = document.createElement('style');
  css.textContent =
    '#health-line{display:flex;justify-content:flex-end;margin:6px 4px 0;font-size:12px;line-height:1.4}' +
    '#health-line a{display:inline-flex;align-items:center;gap:6px;text-decoration:none;' +
    'color:var(--text-mute,#8894A2);padding:2px 0}' +
    '#health-line a:hover{color:var(--text-soft,#5A6673)}' +
    '#health-line .dot{width:7px;height:7px;border-radius:50%;flex:none}' +
    '#health-line .warn{color:#9A6A00;font-weight:600}' +
    '#health-line .bad{color:#B32B22;font-weight:600}';
  document.head.appendChild(css);

  fetch('./data/health.json', { cache: 'no-cache' })
    .then(function (r) { if (!r.ok) throw 0; return r.json(); })
    .then(function (h) {
      var color = { ok: '#1D6E4E', warn: '#C8900A', bad: '#B32B22' };
      // 점검 자체가 이틀 넘게 멈췄으면 그게 먼저다
      var ck = new Date((h.checked || '').replace(' ', 'T') + ':00+09:00');
      var stale = isNaN(ck) || (Date.now() - ck.getTime()) > 2 * 864e5;
      var mine = (h.sources || []).filter(function (s) { return s.page === page && s.status !== 'ok'; });
      var st = stale ? 'warn' : (mine.length ? mine.reduce(function (a, s) {
        return s.status === 'bad' ? 'bad' : a; }, 'warn') : (h.status || 'ok'));
      var text;
      if (stale) text = '<span class="warn">데이터 점검이 멈춰 있습니다</span>';
      else if (mine.length) text = '<span class="' + st + '">' +
        mine.map(function (s) { return s.name + ' ' + s.msg; }).join(' · ') + '</span>';
      else if (h.status !== 'ok') text = '이 화면 데이터 정상 · 다른 화면에 확인할 것 있음';
      else text = '데이터 정상';
      var when = (h.checked || '').slice(5).replace('-', '.');
      var box = document.createElement('div');
      box.id = 'health-line';
      box.innerHTML = '<a href="./status.html" title="데이터 상태 자세히 보기">' +
        '<span class="dot" style="background:' + color[st] + '"></span>' + text +
        (when ? ' · ' + when + ' 점검' : '') + '</a>';
      nav.parentNode.insertBefore(box, nav.nextSibling);
    })
    .catch(function () {});
})();
