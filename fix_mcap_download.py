#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시가총액(mcap.html) 'PNG 내려받기' 가 안 되던 것을 고친다.

  python3 fix_mcap_download.py

원인: 그림을 아주 긴 주소(data:)로 만들어 화면에 붙이지 않은 링크로 눌렀다.
크롬 말고는(사파리·파이어폭스) 이런 큰 그림은 받아지지 않는다.
다른 카드들과 같은 방식으로 바꾼다 — 3배(3240×4050)로 다시 그려 파일(Blob)로 넘기고,
링크를 화면에 붙였다가 누른 뒤 뗀다. 두 번 돌려도 괜찮다.
"""
import re
import sys

FN = "mcap.html"
NEW = r"""  document.getElementById('dl').addEventListener('click', function () {
    // 다른 카드와 같이 3배(3240×4050)로 다시 그려 파일로 저장한다.
    // data: 주소로 넘기면 사파리·파이어폭스에서 큰 그림이 안 받아져 Blob 으로 넘긴다.
    var SCALE = 3, big = document.createElement('canvas');
    big.width = CW * SCALE; big.height = CH * SCALE;
    var keep = ctx;
    ctx = big.getContext('2d'); ctx.scale(SCALE, SCALE);
    try { draw(); } finally { ctx = keep; }
    var mkEl = document.getElementById('mk');
    var name = (document.getElementById('title').value || '시가총액').replace(/[\s\/\\:*?"<>|]+/g, '_') +
               (mkEl ? '_' + mkEl.value : '') + '_' + big.width + 'x' + big.height + '.png';
    big.toBlob(function (blob) {
      if (!blob) { alert('그림을 만들지 못했습니다. 새로고침 후 다시 눌러 주세요.'); return; }
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = name;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 10000);
    }, 'image/png');
  });"""


def main():
    try:
        s = open(FN, encoding="utf-8").read()
    except OSError:
        print("!! %s 가 없습니다. fincard 폴더에서 실행하세요." % FN)
        sys.exit(1)
    if "big.toBlob(" in s:
        print("  그대로  %s  이미 고쳐짐" % FN)
        return
    pat = re.compile(r"  document\.getElementById\('dl'\)\.addEventListener\('click', function \(\) \{.*?\n  \}\);", re.S)
    if len(pat.findall(s)) != 1:
        print("!! %s 에서 내려받기 부분을 못 찾았습니다. mcap.html 을 보내 주세요." % FN)
        sys.exit(1)
    s = pat.sub(lambda m: NEW, s, count=1)
    open(FN, "w", encoding="utf-8").write(s)
    print("  고침    %s  (PNG 내려받기 · 3240×4050)" % FN)


if __name__ == "__main__":
    main()
