#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시가총액·시총 순위 탭의 미국 회사 중 로고가 없는 곳을 채운다 → logo/us/티커.png (원형)

  python3 make_us_logos.py            없는 것만
  python3 make_us_logos.py --dry      무엇이 없는지만 보기 (받지 않음)
  python3 make_us_logos.py NVDA GE    그 회사만 (있어도 다시)

어느 회사를 채우나 (카드에 실제로 나오는 곳만):
  · 시가총액 탭  미국 / 미국 회사만 상위 50, 섹터마다 상위 50, 업종마다 상위 30
  · 시총 순위 탭 미국 칸마다 상위 15 (옛 회사 GE·엑슨·시스코 등 포함)
어디서 받나 (먼저 받아지는 것):
  1) companiesmarketcap 회사 로고   2) Financial Modeling Prep 회사 로고
받은 로고는 흰 원 가운데에 맞춰 넣는다 (국내 옛 회사 로고와 같은 모양).
이미 있는 logo/us/티커.png 는 건드리지 않는다. 끝나면 logos_us_check.html 이 열린다.
"""
import io
import json
import os
import sys
import time
import urllib.request

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("!! Pillow 가 필요합니다:  conda install -y pillow")

DIR = os.path.join("logo", "us")
SIZE = 400
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
SOURCES = [
    "https://companiesmarketcap.com/img/company-logos/256/{t}.webp",
    "https://companiesmarketcap.com/img/company-logos/256/{t}.png",
    "https://financialmodelingprep.com/image-stock/{t}.png",
]


def targets():
    want, names = {}, {}
    try:
        m = json.load(open(os.path.join("data", "mcap_us.json"), encoding="utf-8"))
    except Exception:                            # noqa: BLE001
        m = {}
    for r in (m.get("us") or [])[:50] + (m.get("us_only") or [])[:50]:
        want[r["code"]] = "시가총액 상위"; names[r["code"]] = r["name"]
    st = m.get("stocks") or {}
    for kind, top, why in (("sector", 50, "섹터"), ("industry", 30, "업종")):
        for g in (m.get("groups") or {}).get(kind, []):
            for c in g["codes"][:top]:
                want.setdefault(c, why); names.setdefault(c, (st.get(c) or {}).get("n", c))
    try:
        rk = json.load(open(os.path.join("data", "rank.json"), encoding="utf-8"))
    except Exception:                            # noqa: BLE001
        rk = {}
    for k, col in (rk.get("cols") or {}).items():
        for mk in ("us", "us_only"):
            for c, n, _ in (col.get(mk) or [])[:15]:
                want.setdefault(c, "시총 순위 " + ("현재" if k == "now" else k)); names.setdefault(c, n)
    return want, names


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
    return urllib.request.urlopen(req, timeout=30).read()


def round_logo(raw):
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    if min(im.size) < 24:
        raise ValueError("너무 작은 그림")
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    box = int(SIZE * 0.70)
    r = min(box / im.width, box / im.height)
    im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    bg = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 255))
    bg.alpha_composite(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2))
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, SIZE - 1, SIZE - 1), fill=255)
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.paste(bg, (0, 0), mask)
    b = io.BytesIO()
    out.save(b, "PNG")
    return b.getvalue()


def fetch(code):
    tries = [code] + ([code.replace("-", ".")] if "-" in code else [])
    last = ""
    for src in SOURCES:
        for t in tries:
            try:
                raw = get(src.format(t=t))
                if len(raw) < 300:
                    last = "빈 그림"
                    continue
                return round_logo(raw), src.split("/")[2]
            except Exception as e:               # noqa: BLE001
                last = type(e).__name__ + (" %s" % getattr(e, "code", "") if hasattr(e, "code") else "")
    raise RuntimeError(last)


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    want, names = targets()
    if only:
        todo = only
    else:
        todo = [c for c in want if not os.path.exists(os.path.join(DIR, c + ".png"))]
    print("카드에 나오는 미국 회사 %d곳 · 로고 없음 %d곳" % (len(want), len(todo)))
    if "--dry" in sys.argv:
        for c in todo:
            print("  %-7s %-30s %s" % (c, names.get(c, "")[:30], want.get(c, "")))
        return
    os.makedirs(DIR, exist_ok=True)
    rows, ok = [], 0
    for i, c in enumerate(todo, 1):
        try:
            png, src = fetch(c)
            open(os.path.join(DIR, c + ".png"), "wb").write(png)
            rows.append((c, names.get(c, c), src, True)); ok += 1
        except Exception as e:                   # noqa: BLE001
            rows.append((c, names.get(c, c), "못 찾음 " + str(e), False))
        if i % 25 == 0:
            print("  %d/%d … (받음 %d)" % (i, len(todo), ok))
        time.sleep(0.25)
    miss = [r for r in rows if not r[3]]
    print("\n받음 %d / %d" % (ok, len(todo)))
    if miss:
        print("못 찾은 곳 %d: %s" % (len(miss), ", ".join("%s(%s)" % (r[0], r[1][:16]) for r in miss[:40])))
    cells = "".join(
        ('<figure><img src="logo/us/%s.png"><figcaption><b>%s</b><br>%s<br><i>%s</i></figcaption></figure>' % (c, c, n, s)) if okk else
        ('<figure><div class="no">%s</div><figcaption><b>%s</b><br>%s<br><i>%s</i></figcaption></figure>' % (c, c, n, s))
        for c, n, s, okk in rows)
    open("logos_us_check.html", "w", encoding="utf-8").write(
        "<!doctype html><meta charset=utf-8><title>미국 로고 확인</title>"
        "<style>body{font:13px sans-serif;background:#f4f4f2;margin:20px}div.g{display:flex;flex-wrap:wrap;gap:12px}"
        "figure{margin:0;width:120px;text-align:center}img,.no{width:84px;height:84px;border-radius:50%;"
        "background:#6B7078;display:inline-flex;align-items:center;justify-content:center;color:#fff}"
        "figcaption{font-size:11px;color:#555;margin-top:4px;word-break:break-all}</style>"
        "<h2>새로 받은 미국 로고 — 이상한 것은 logo/us/티커.png 를 지우세요</h2><div class=g>" + cells + "</div>")
    if sys.platform == "darwin":
        os.system("open logos_us_check.html")


if __name__ == "__main__":
    main()
