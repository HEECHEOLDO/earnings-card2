#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""index.html(국내 실적)을 복사해 unlisted.html(비상장 실적)을 만든다.

  python3 make_unlisted_page.py

화면·카드 디자인은 국내 실적과 똑같이 두고, 아래만 바꾼다.
  · 데이터를 data/unlisted/ 에서 읽는다
  · 자료가 없을 때 삼성전자 샘플(MOCK)로 대신하지 않는다
  · 8자리 회사코드 대신 대표 서비스를 보여주고, 서비스 이름으로도 찾게 한다
  · 처음 열 때 고르는 회사, 주소(?code=) 8자리 허용
  · 카드의 '연결' 표기를 회사마다 연결/별도로 (비상장사는 별도가 많다)
  · 분기가 없는 회사(감사보고서)·배당이 없는 회사는 그 탭을 숨긴다

국내 실적 화면을 고친 뒤에는 이 스크립트를 다시 돌리면 그대로 따라온다.
바꿀 자리를 못 찾으면 멈추고 알려준다 (엉뚱하게 고치지 않는다).
"""
import sys

SRC, DST = "index.html", "unlisted.html"

REPL = [
    ("제목",
     "<title>실적·배당 카드뉴스</title>",
     "<title>비상장 실적 · 실적·배당 카드뉴스</title>"),
    ("목록 경로",
     "fetch('./data/index.json', { cache: 'no-cache' })",
     "fetch('./data/unlisted/index.json', { cache: 'no-cache' })"),
    ("회사 파일 경로",
     "fetch('./data/' + code + '.json', { cache: 'no-cache' })",
     "fetch('./data/unlisted/' + code + '.json', { cache: 'no-cache' })"),
    ("목록이 없을 때 샘플 대신 빈 목록",
     """          Adapter.index = Object.keys(MOCK).map(function (k) {
            return { name: MOCK[k].name, code: k, market: MOCK[k].market, sector: MOCK[k].sector };
          });
          Adapter.source = 'mock';""",
     """          Adapter.index = [];             // 비상장은 샘플(삼성전자)로 대신하지 않는다
          Adapter.source = 'none';"""),
    ("회사 파일이 없을 때 샘플 대신 없음",
     "        .catch(function () { return MOCK[code] || null; });",
     "        .catch(function () { return null; });"),
    ("상단 배지",
     "if (!parts.length) parts.push('DART ' + total.toLocaleString('ko-KR') + '종목');",
     "parts = ['비상장 ' + total.toLocaleString('ko-KR') + '곳'];"),
    ("회사 정보 줄 — 회사코드 대신 분류",
     "[state.company.code, state.company.market, state.company.sector]",
     "[state.company.market, state.company.sector]"),
    ("검색 목록 오른쪽 — 회사코드 대신 대표 서비스",
     "'</span><span class=\"code\">' + c.code + '</span></li>'",
     "'</span><span class=\"code\">' + (c.brand || c.sector || '') + '</span></li>'"),
    ("검색 — 대표 서비스로도 찾기 (순위는 이름 다음)",
     "        else if (name.indexOf(s) >= 0) rank = 4;",
     "        else if (name.indexOf(s) >= 0) rank = 4;\n"
     "        else if ((c.brand || '').toLowerCase().replace(/\\s/g, '').indexOf(s.replace(/\\s/g, '')) >= 0) rank = 5;"),
    ("엔터로 고를 때도 대표 서비스로 찾기",
     """      for (i = 0; i < list.length; i++) {
        if (list[i].name.toLowerCase().indexOf(low) >= 0) return list[i];
      }
      return null;""",
     """      for (i = 0; i < list.length; i++) {
        if (list[i].name.toLowerCase().indexOf(low) >= 0) return list[i];
      }
      for (i = 0; i < list.length; i++) {
        if ((list[i].brand || '').toLowerCase().replace(/\\s/g, '')
              .indexOf(low.replace(/\\s/g, '')) >= 0) return list[i];
      }
      return null;"""),
    ("검색 안내 문구",
     "'전체 ' + total + '종목 · 이름이나 코드를 입력해보세요'",
     "'비상장 ' + total + '곳 · 회사 이름이나 서비스·제품으로 찾아보세요'"),
    ("처음 검색창 문구",
     "document.getElementById('q').value = '삼성전자';",
     "document.getElementById('q').value = '';"),
    ("주소의 ?code= 8자리 허용",
     r"/[?&]code=(\d{6})/",
     r"/[?&]code=(\d{6,8})/"),
    ("처음 고르는 회사",
     "Adapter.match('삼성전자') || Adapter.index[0]",
     "Adapter.match('토스') || Adapter.index[0]"),
    ("카드의 재무제표 기준 (연결/별도)",
     "      : '연결 · ' + unit + (showLine && spec.unitNote ? ' · ' + spec.unitNote : '');",
     "      : (state.company.basis || '연결') + ' · ' + unit + (showLine && spec.unitNote ? ' · ' + spec.unitNote : '');"),
    ("대시보드의 재무제표 기준 (연결/별도)",
     "        : '연결 기준 · 단위 ' + unit;",
     "        : (state.company.basis || '연결') + ' 기준 · 단위 ' + unit;"),
    ("연간만 있는 회사(감사보고서) — 분기·배당 탭 숨기기",
     """  function refresh() {
    fillRangeOptions();
    state.rows = buildSeries(state.company, state.period, state.counts[state.period]);""",
     """  function refresh() {
    syncTabs();
    fillRangeOptions();
    state.rows = buildSeries(state.company, state.period, state.counts[state.period]);"""),
    ("탭 숨기기 함수",
     "  function setPeriod(p) {",
     """  // 감사보고서만 내는 회사는 분기가 없고, 배당이 없는 회사도 많다.
  // 그런 탭은 숨기고, 숨긴 탭을 보고 있었다면 연간으로 옮긴다 (알림 없이).
  function syncTabs() {
    var c = state.company || {};
    var has = {
      annual: true,
      quarterly: (c.quarterly || []).length > 0,
      dividend: (c.annual || []).some(function (r) { return r.dps > 0; })
    };
    Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (b) {
      b.style.display = has[b.dataset.period] ? '' : 'none';
    });
    if (!has[state.period]) {
      state.period = 'annual';
      Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (b) {
        b.setAttribute('aria-selected', String(b.dataset.period === 'annual'));
      });
    }
  }

  function setPeriod(p) {"""),
    ("배당이 없는 회사 — 배당 칸 대신 순이익 지표",
     """        ['평균 배당성향', payout.toFixed(1) + '%'],
        ['연속 배당', st + '년']
      ];""",
     """        ['평균 배당성향', payout.toFixed(1) + '%'],
        ['연속 배당', st + '년']
      ];
      if (!a.some(function (d) { return d.dps > 0; })) {
        var nim = a.reduce(function (s2, d) { return s2 + (d.rev ? (d.ni || 0) / d.rev * 100 : 0); }, 0) / a.length;
        var black = a.filter(function (d) { return d.op > 0; }).length;
        items[2] = ['평균 순이익률', nim.toFixed(1) + '%'];
        items[3] = ['영업흑자', black + ' / ' + a.length + '년'];
      }"""),
    ("구간 기본값 — 회사·탭을 바꿀 때마다 가장 긴 구간",
     """    var cur = Math.min(state.counts[state.period] || max, max);""",
     """    // 회사나 탭이 바뀌면 그 회사의 가장 긴 구간으로 연다. 앞 회사가 3년뿐이었다고
    // 다음 회사도 3년으로 열리지 않게. 사용자가 고른 구간은 같은 회사·탭 안에서만 유지.
    var rkey = (state.company && state.company.code) + '|' + state.period;
    if (state.rangeKey !== rkey) { state.rangeKey = rkey; state.counts[state.period] = max; }
    var cur = Math.min(state.counts[state.period] || max, max);"""),
    ("자료가 없을 때 배지",
     "pill.textContent = '샘플 데이터';",
     "pill.textContent = '비상장 자료를 아직 받지 않았습니다';"),
]


def main():
    try:
        s = open(SRC, encoding="utf-8").read()
    except OSError:
        print("!! %s 가 없습니다. fincard 폴더에서 실행하세요." % SRC)
        sys.exit(1)
    bad = []
    for label, a, b in REPL:
        n = s.count(a)
        if n != 1:
            bad.append("%s (찾은 횟수 %d)" % (label, n))
            continue
        s = s.replace(a, b)
    if bad:
        print("!! index.html 이 예상과 달라 멈춥니다. 아래 자리를 못 찾았습니다:")
        for x in bad:
            print("   - " + x)
        print("   unlisted.html 은 만들지 않았습니다.")
        sys.exit(1)
    open(DST, "w", encoding="utf-8").write(s)
    print("%s -> %s  (%d군데 바꿈)" % (SRC, DST, len(REPL)))
    print("메뉴는 add_tab.py 로 넣습니다.")


if __name__ == "__main__":
    main()
