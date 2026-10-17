#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""카드 제목(회사명) 왼쪽에 회사 로고를 넣는다 — 국내 실적·해외 실적·연간 수익률.

  python3 add_logo.py

  · 로고는 이미 올려둔 logo/kr/{코드}.png · logo/us/{기호}.png 를 쓴다.
    (비상장은 logo/unlisted/{회사코드}.png — 넣어두면 나온다)
  · 로고 파일이 없으면 아무것도 그리지 않는다 (제목만, 지금과 같다).
  · '회사 로고 표시' 체크박스로 넣었다 뺐다 한다. 처음엔 켜져 있다.
  · 크기는 회사명 글자 높이에 맞추고, 제목이 길면 로고 자리만큼 글자를 줄인다.
  · 연간 수익률의 '종목명에 형광펜' 은 쓰지 않아 지운다 (그 자리에 로고 체크박스).
  · 연간 수익률의 해외 ETF 는 자기 로고가 없으면 운용사 로고(그때 샀다면과 같은 규칙).

비상장 실적(unlisted.html)은 index.html 을 복사해 만드므로 이 스크립트 뒤에
make_unlisted_page.py 를 다시 돌리면 따라온다. 두 번 돌려도 괜찮다.
"""
import re
import sys

# ---------------------------------------------------------------- 공통 JS

HELPERS = r"""
  /* ---- 제목 왼쪽 회사 로고 ----
     logo/ 폴더의 원형 투명 PNG 를 회사명 글자 높이에 맞춰 그린다.
     파일이 없으면 그리지 않는다. 한 번 실패한 파일은 다시 부르지 않는다.
     d: 지름(글자 크기 대비) · gap: 로고와 글자 사이 · mid: 글자 중심 높이 */
  var LOGO_K = { d: 0.84, gap: 0.22, mid: 0.37 };
  var LOGO_CACHE = {};
  function titleLogo(list, redraw) {
    if (!list || !list.length) return null;
    var key = list.join('|');
    var im = LOGO_CACHE[key];
    if (im === undefined) {
      im = new Image();
      LOGO_CACHE[key] = im;
      var i = 0;
      im.onload = function () { redraw(); };
      im.onerror = function () {
        i++;
        if (i < list.length) im.src = list[i];
        else { LOGO_CACHE[key] = null; redraw(); }
      };
      im.src = list[0];
    }
    return (im && im.complete && im.naturalWidth) ? im : null;
  }
  function drawTitleLogo(ctx, im, x, cy, d) {
    ctx.save();
    ctx.letterSpacing = '0px';
    ctx.drawImage(im, x, cy - d / 2, d, d);
    ctx.beginPath(); ctx.arc(x + d / 2, cy, d / 2, 0, 7);
    ctx.lineWidth = 1.5; ctx.strokeStyle = 'rgba(0,0,0,0.08)'; ctx.stroke();
    ctx.restore();
  }
"""

KR_SRC = r"""
  function logoListFor(state) {
    var code = state.company && state.company.code;
    if (!code) return null;
    // 8자리는 비상장(DART 회사코드), 6자리는 상장사
    return ['./logo/' + (code.length === 8 ? 'unlisted/' : 'kr/') + code + '.png'];
  }
"""

US_SRC = r"""
  function logoListFor(state) {
    var code = state.company && state.company.code;
    return code ? ['./logo/us/' + code + '.png'] : null;
  }
"""

# 국내·해외 실적 — 제목 그리는 부분이 같다
DASH = [
    ("도우미 함수",
     "  function drawCard(ctx, state) {",
     None),                                   # HELPERS + SRC 를 앞에 붙인다
    ("제목 크기 — 로고 자리만큼 줄이기",
     "    var nameSize = fitFont(ctx, line1, 900, T.type.nameMax, T.type.nameMin, CWID);\n",
     "    var nameSize = fitFont(ctx, line1, 900, T.type.nameMax, T.type.nameMin, CWID);\n"
     "    var lgIm = state.showLogo ? titleLogo(logoListFor(state), drawPreview) : null;\n"
     "    var lgD = 0, lgGap = 0;\n"
     "    if (lgIm) {\n"
     "      nameSize = fitFont(ctx, line1, 900, T.type.nameMax, T.type.nameMin,\n"
     "                         CWID - nameSize * (LOGO_K.d + LOGO_K.gap));\n"
     "      lgD = nameSize * LOGO_K.d; lgGap = nameSize * LOGO_K.gap;\n"
     "    }\n"),
    ("제목 — 로고 그리고 글자를 옆으로",
     "    ctx.fillText(line1, CX, y);\n",
     "    if (lgIm) drawTitleLogo(ctx, lgIm, CX, y - nameSize * LOGO_K.mid, lgD);\n"
     "    ctx.fillText(line1, CX + lgD + lgGap, y);\n"),
    ("처음 상태 — 로고 켬",
     "    guide: false, showSource: true,",
     "    guide: false, showSource: true, showLogo: true,"),
    ("체크박스",
     '<label class="check"><input type="checkbox" id="chk-source" checked>',
     '<label class="check"><input type="checkbox" id="chk-logo" checked> 회사 로고 표시</label>\n'
     '        <label class="check"><input type="checkbox" id="chk-source" checked>'),
    ("체크박스 연결",
     "  document.getElementById('chk-source').addEventListener('change', function () {",
     "  document.getElementById('chk-logo').addEventListener('change', function () {\n"
     "    state.showLogo = this.checked; drawPreview();\n"
     "  });\n\n"
     "  document.getElementById('chk-source').addEventListener('change', function () {"),
]

# 연간 수익률
RET_SRC = r"""
  // 국내는 logo/kr/{코드}, 해외는 logo/us/{기호}. 해외 ETF 는 자기 로고가 없으면
  // 운용사 로고 (그때 샀다면과 같은 표). 지수(KOSPI·NASDAQ100 등)는 로고 없음.
  var ISSUER = {};
  (function () {
    var g = {
      SPY:  'SPLG DIA GLD XLK XLF XLE XLV XLU XLI XLP XLY XLB XLRE XLC MDY SDY KRE XBI XOP GLDM SPYG SPYV SPYD',
      IVZ:  'QQQ QQQM RSP SPLV PGX PBW',
      BLK:  'IVV IWM IWF IWD IJH IJR ITOT TLT IEF SHY AGG LQD HYG EFA EEM SLV IAU SOXX USMV DVY IBIT EWY',
      SCHW: 'SCHD SCHX SCHG SCHB SCHF SCHA SCHH SCHP SCHZ SCHV',
      JPM:  'JEPI JEPQ',
      _vanguard:  'VOO VTI VUG VTV VYM VIG BND VEA VWO VXUS VNQ VGT VB VO VT BNDX',
      _direxion:  'SOXL SOXS TMF TNA TZA FAS LABU',
      _proshares: 'TQQQ SQQQ QLD SSO UPRO SPXU SDS',
      _vaneck:    'SMH GDX'
    };
    Object.keys(g).forEach(function (k) { g[k].split(' ').forEach(function (t) { ISSUER[t] = k; }); });
  })();
  function logoListFor(state) {
    var code = state.code, it = code && RET.items && RET.items[code];
    if (!it) return null;
    if (it.market === 'KR') return /^\d{6}$/.test(code) ? ['./logo/kr/' + code + '.png'] : null;
    var out = ['./logo/us/' + code + '.png'];
    if (ISSUER[code]) out.push('./logo/us/' + ISSUER[code] + '.png');
    return out;
  }
"""

RET = [
    ("도우미 함수",
     "  function drawCard(ctx, anim) {",
     None),
    ("제목 크기 — 로고 자리만큼 줄이기",
     "    var ns = fitFont(ctx, state.name || ' ', 900, T.type.nameMax, T.type.nameMin, CWID);\n",
     "    var ns = fitFont(ctx, state.name || ' ', 900, T.type.nameMax, T.type.nameMin, CWID);\n"
     "    var lgIm = state.showLogo ? titleLogo(logoListFor(state), drawPreview) : null;\n"
     "    var lgD = 0, lgGap = 0;\n"
     "    if (lgIm) {\n"
     "      ns = fitFont(ctx, state.name || ' ', 900, T.type.nameMax, T.type.nameMin,\n"
     "                   CWID - ns * (LOGO_K.d + LOGO_K.gap));\n"
     "      lgD = ns * LOGO_K.d; lgGap = ns * LOGO_K.gap;\n"
     "    }\n"
     "    var NX = CX + lgD + lgGap;               // 회사명이 시작하는 자리\n"),
    ("형광펜 삭제 — 쓰지 않아서 뺀다",
     "    if (state.name && state.mark) {",
     None),                                   # 아래 main 에서 블록째 지운다
    ("제목 — 로고 그리고 글자를 옆으로",
     "    ctx.fillStyle = T.ink;\n    ctx.fillText(state.name || '', CX, y);",
     "    if (lgIm) drawTitleLogo(ctx, lgIm, CX, y - ns * LOGO_K.mid, lgD);\n"
     "    ctx.fillStyle = T.ink;\n    ctx.fillText(state.name || '', NX, y);"),
    ("주석 정리",
     "    // 형광펜과 글자를 같은 상태에서 처리한다.\n    // 재는 도중에 자간을 껐다 켜면 폭이 어긋나 형광펜이 짧아진다.\n",
     ""),
    ("처음 상태 — 로고 켬",
     "source:'', handle:'@돈굴돈굴', mark:true, guide:false };",
     "source:'', handle:'@돈굴돈굴', guide:false, showLogo:true, code:'' };"),
    ("고른 종목 코드 기억",
     "    state.mark = document.getElementById('chk-mark').checked;",
     "    state.showLogo = document.getElementById('chk-logo').checked;\n"
     "    state.code = document.getElementById('f-code').value;"),
    ("불러오기로 고른 종목도 코드 기억",
     "    document.getElementById('f-data').value = lines.join('\\n');",
     "    document.getElementById('f-data').value = lines.join('\\n');\n"
     "    document.getElementById('f-code').value = code;"),
    ("체크박스 — 형광펜 자리에 로고",
     '<label class="check"><input type="checkbox" id="chk-mark" checked> 종목명에 형광펜</label>',
     '<label class="check"><input type="checkbox" id="chk-logo" checked> 회사 로고 표시</label>'),
    ("체크박스 연결 — 형광펜 대신 로고",
     "  document.getElementById('chk-mark').addEventListener('change', refresh);",
     "  document.getElementById('chk-logo').addEventListener('change', refresh);"),
]

JOBS = [("index.html", DASH, KR_SRC), ("us.html", DASH, US_SRC), ("returns.html", RET, RET_SRC)]


def main():
    bad_any = False
    for fn, repl, src in JOBS:
        try:
            s = open(fn, encoding="utf-8").read()
        except OSError:
            print("  없음    %s" % fn)
            continue
        if "function drawTitleLogo" in s:
            print("  그대로  %-13s 이미 로고가 들어가 있음" % fn)
            continue
        bad = []
        for label, a, b in repl:
            if s.count(a) != 1:
                bad.append("%s (찾은 횟수 %d)" % (label, s.count(a)))
                continue
            if b is not None:
                s = s.replace(a, b)
            elif a.startswith("    if (state.name && state.mark)"):
                s = re.sub(r"    if \(state\.name && state\.mark\) \{.*?\n      ctx\.fill\(\);\n    \}\n\n?",
                           "", s, count=1, flags=re.S)
            else:
                s = s.replace(a, HELPERS + src + "\n" + a)
        if bad:
            bad_any = True
            print("  !! %s 는 고치지 않았습니다. 못 찾은 자리:" % fn)
            for x in bad:
                print("       - " + x)
            continue
        open(fn, "w", encoding="utf-8").write(s)
        print("  고침    %-13s (%d군데)" % (fn, len(repl)))
    if bad_any:
        sys.exit(1)
    print("비상장 실적도 넣으려면:  python3 make_unlisted_page.py && python3 add_tab.py")


if __name__ == "__main__":
    main()
