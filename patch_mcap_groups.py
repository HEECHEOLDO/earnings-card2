#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시가총액(mcap.html)에 '업종별' · '테마별' 보기를 넣는다.

  python3 patch_mcap_groups.py

시장 칸에 '업종별…' '테마별…' 이 생기고, 고르면 그 옆에 업종(테마) 목록이 나온다.
목록은 시가총액 합이 큰 순서이고, 이름 뒤에 종목 수가 붙는다 (예: 반도체 · 52).
제목은 '반도체 시가총액 TOP 20' 처럼, 종목이 20개보다 적으면 그 수로 바뀐다.
데이터는 collect_mcap.py 가 만든 data/mcap.json 의 groups·stocks 를 쓴다.
두 번 돌려도 괜찮다.
"""
import sys

FN = "mcap.html"
REPL = [
    ("시장 칸 — 업종·테마 추가 + 목록 칸",
     '<option value="all">국내 전체 (코스피+코스닥)</option></select></div>',
     '<option value="all">국내 전체 (코스피+코스닥)</option>'
     '<option value="industry">업종별…</option><option value="theme">테마별…</option></select></div>'),
    ("업종·테마 목록 칸 (순위 칸 아래 줄)",
     '      <label class="f" for="title">제목</label>',
     '      <div id="grp-wrap" style="display:none"><label class="f" for="grp" id="grp-label">업종</label>\n'
     '        <select id="grp"></select></div>\n'
     '      <label class="f" for="title">제목</label>'),
    ("데이터 고르기 — 업종·테마",
     """    var src = mk === 'all' && DATA
      ? (DATA.kospi || []).concat(DATA.kosdaq || []).sort(function (a, b) { return b.cap - a.cap; })
      : DATA && DATA[mk];""",
     """    var src = mk === 'all' && DATA
      ? (DATA.kospi || []).concat(DATA.kosdaq || []).sort(function (a, b) { return b.cap - a.cap; })
      : DATA && DATA[mk];
    var wrap = document.getElementById('grp-wrap'), gsel = document.getElementById('grp');
    var isGrp = mk === 'industry' || mk === 'theme';
    wrap.style.display = isGrp ? '' : 'none';
    if (isGrp) {
      var gs = (DATA && DATA.groups && DATA.groups[mk]) || [];
      document.getElementById('grp-label').textContent = mk === 'industry' ? '업종' : '테마';
      if (gsel.dataset.kind !== mk) {          // 목록은 종류가 바뀔 때만 다시 채운다
        gsel.innerHTML = gs.map(function (g, i) {
          return '<option value="' + i + '">' + g.name + ' · ' + g.n + '</option>'; }).join('');
        gsel.dataset.kind = mk;
      }
      var g = gs[+gsel.value || 0];
      src = g ? g.codes.map(function (c) { var s = DATA.stocks[c] || {};
        return { code: c, name: s.n || c, cap: s.c || 0, ytd: s.y }; }) : [];
    }"""),
    ("제목·아래 줄 — 업종·테마 이름",
     "    document.getElementById('title').value = '시가총액 TOP ' + n;",
     "    var cnt = document.getElementById('data').value.split('\\n').filter(function (l) { return l.trim(); }).length;\n"
     "    var gname = '';\n"
     "    if (mk === 'industry' || mk === 'theme') {\n"
     "      var gg = ((DATA && DATA.groups && DATA.groups[mk]) || [])[+document.getElementById('grp').value || 0];\n"
     "      gname = gg ? gg.name + ' ' : '';\n"
     "    }\n"
     "    document.getElementById('title').value = gname + '시가총액 TOP ' + Math.min(+n, cnt || +n);"),
    ("아래 줄 — 업종·테마",
     "{ kospi: '코스피', kosdaq: '코스닥', all: '국내 주식' }[mk] + d;",
     "{ kospi: '코스피', kosdaq: '코스닥', all: '국내 주식', industry: '업종', theme: '테마' }[mk] + d;"),
    ("목록을 고르면 다시 그리기",
     "  document.getElementById('mk').addEventListener('change', function () { fill(); draw(); });",
     "  document.getElementById('mk').addEventListener('change', function () { fill(); draw(); });\n"
     "  document.getElementById('grp').addEventListener('change', function () { fill(); draw(); });"),
]


def main():
    try:
        s = open(FN, encoding="utf-8").read()
    except OSError:
        print("!! %s 가 없습니다. fincard 폴더에서 실행하세요." % FN)
        sys.exit(1)
    if 'id="grp"' in s:
        print("  그대로  %s  이미 고쳐짐" % FN)
        return
    bad = [lab for lab, a, _ in REPL if s.count(a) != 1]
    if bad:
        print("!! %s 이 예상과 달라 고치지 않았습니다. 못 찾은 자리:" % FN)
        for b in bad:
            print("   - " + b)
        print("   mcap.html 을 보내 주세요.")
        sys.exit(1)
    for _, a, b in REPL:
        s = s.replace(a, b)
    open(FN, "w", encoding="utf-8").write(s)
    print("  고침    %s  (%d군데) — 시장 칸에 업종별·테마별" % (FN, len(REPL)))


if __name__ == "__main__":
    main()
