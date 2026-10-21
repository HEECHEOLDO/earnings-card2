#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_old_logos.py 로 못 채운 옛 회사 로고를 여러 곳에서 더 찾아 원형으로 만든다.

  python3 find_logos.py            logo/kr/코드.png 가 없는 회사만
  python3 find_logos.py 025930     그 회사만 (있어도 다시)

찾는 순서 (먼저 찾은 것을 쓴다):
 1) 한국어·영어 위키백과 문서에 들어 있는 그림 중 이름에 logo·로고·CI·심볼 이 든 파일
 2) 위키미디어 공용(Commons)에서 '회사이름 logo' 로 검색한 그림
 3) 회사 홈페이지 아이콘 (아직 있는 회사만, 주소를 아는 곳)
그래도 없으면 그대로 둔다 → 카드에서 회색 원에 이름.
직접 구한 그림이 있으면 logo_in/코드.png (jpg 도 됨) 로 넣고 다시 돌리면 원형으로 바꿔 넣는다.
끝나면 logos_check2.html 을 연다 — 어디서 가져왔는지 같이 보이니, 이상한 것은 지우면 된다.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

from make_old_logos import DIR, UA, round_logo

# 코드: (한국어 위키 문서, 영어 위키 문서, 공용 검색어들, 홈페이지)
LIST = {
    "000200": ("대우중공업", "Daewoo Heavy Industries", ["Daewoo logo", "대우 로고"], None),
    "012650": ("쌍용건설", "Ssangyong Engineering & Construction", ["Ssangyong E&C logo", "쌍용건설 로고"], "ssyenc.com"),
    "026960": ("동서 (기업)", "Dongsuh", ["Dongsuh logo", "동서식품 로고"], "dongsuh.co.kr"),
    "025930": ("팬택", "Pantech", ["Pantech logo", "팬택 로고"], None),
    "027350": ("텔슨전자", None, ["Telson logo", "텔슨 로고"], None),
    "043790": ("옥션 (기업)", "Auction (company)", ["Auction.co.kr logo", "옥션 로고"], "auction.co.kr"),
    "032380": ("핸디소프트", None, ["Handysoft logo", "핸디소프트 로고"], "handysoft.co.kr"),
    "013200": ("우방", None, ["우방 로고", "Woobang logo"], None),
    "022130": ("건영", None, ["건영 로고"], None),
    "033510": ("어필텔레콤", None, ["Appeal Telecom logo", "어필텔레콤 로고"], None),
    "031390": ("서울이동통신", None, ["서울이동통신 로고"], None),
    "089240": ("네오세미테크", None, ["네오세미테크 로고"], None),
    "026950": ("한일제관", None, ["한일제관 로고"], None),
    "011860": ("동아일렉콤", None, ["동아일렉콤 로고"], None),
    "034600": ("로커스 (기업)", None, ["로커스 로고"], None),
    "057330": ("플래닛82", None, ["Planet82 logo", "플래닛82 로고"], None),
    "089480": ("평산 (기업)", None, ["평산 로고"], None),
    "019930": ("기라정보통신", None, ["기라정보통신 로고"], None),
    "031800": ("씨티아이", None, ["씨티아이 로고"], None),
    "033300": ("보성인터내셔널", None, ["보성 로고"], None),
    "033030": ("대양이앤씨", None, ["대양이앤씨 로고"], None),
}
LOGO_WORD = re.compile(r"logo|로고|\bCI\b|_CI|심볼|심벌|symbol|wordmark|emblem", re.I)
SKIP_WORD = re.compile(r"flag|map|commons-logo|wiki|edit|icon_|question|stub|disambig", re.I)


def api(site, **q):
    q.update(format="json", redirects=1)
    req = urllib.request.Request("https://%s/w/api.php?%s" % (site, urllib.parse.urlencode(q)),
                                 headers={"User-Agent": UA})
    return json.load(urllib.request.urlopen(req, timeout=30))


def thumb(site, file_title):
    j = api(site, action="query", titles=file_title, prop="imageinfo", iiprop="url", iiurlwidth=600)
    for p in j.get("query", {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        return ii.get("thumburl") or ii.get("url")
    return None


def from_page(lang, title):
    if not title:
        return None
    site = "%s.wikipedia.org" % lang
    j = api(site, action="query", titles=title, prop="images", imlimit=50)
    for p in j.get("query", {}).get("pages", {}).values():
        for im in p.get("images", []):
            t = im["title"]
            if LOGO_WORD.search(t) and not SKIP_WORD.search(t):
                u = thumb(site, t)
                if u:
                    return u, "%s 위키 · %s" % (lang, t)
    return None


def from_commons(words):
    site = "commons.wikimedia.org"
    for w in words:
        j = api(site, action="query", list="search", srsearch=w, srnamespace=6, srlimit=8)
        for r in j.get("query", {}).get("search", []):
            t = r["title"]
            name = w.split()[0].lower()
            if LOGO_WORD.search(t) and not SKIP_WORD.search(t) and name[:3] in t.lower():
                u = thumb(site, t)
                if u:
                    return u, "공용 · %s" % t
    return None


def from_site(domain):
    if not domain:
        return None
    return "https://www.google.com/s2/favicons?domain=%s&sz=256" % domain, "홈페이지 아이콘 · %s" % domain


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=30).read()


def from_folder():
    """logo_in/ 에 직접 넣은 그림(코드.png·jpg·jpeg·webp)을 원형으로 바꿔 넣는다"""
    done = []
    if not os.path.isdir("logo_in"):
        return done
    for f in sorted(os.listdir("logo_in")):
        m = re.fullmatch(r"(\w{6})\.(png|jpe?g|webp)", f, re.I)
        if not m:
            continue
        dst = os.path.join(DIR, m.group(1) + ".png")
        open(dst, "wb").write(round_logo(open(os.path.join("logo_in", f), "rb").read()))
        done.append((m.group(1), f, "직접 넣음 · logo_in/" + f, dst))
        print("  %s %-14s 직접 넣음" % (m.group(1), f))
    return done


def main():
    only = [a for a in sys.argv[1:] if re.fullmatch(r"\w{6}", a)]
    rows = from_folder()
    for code, (ko, en, words, domain) in LIST.items():
        dst = os.path.join(DIR, code + ".png")
        if only and code not in only:
            continue
        if not only and os.path.exists(dst):
            continue
        got, why = None, ""
        for step in (lambda: from_page("ko", ko), lambda: from_page("en", en),
                     lambda: from_commons(words), lambda: from_site(domain)):
            try:
                r = step()
            except Exception as e:            # noqa: BLE001
                why = repr(e)
                continue
            if not r:
                continue
            try:
                raw = get(r[0])
                if len(raw) < 300:            # 빈 아이콘
                    continue
                open(dst, "wb").write(round_logo(raw))
                got = r[1]
                break
            except Exception as e:            # noqa: BLE001
                why = repr(e)
        rows.append((code, ko, got or ("못 찾음 " + why).strip(), dst if got else None))
        print("  %s %-14s %s" % (code, ko, got or "못 찾음"))

    cells = "".join(
        ('<figure><img src="%s"><figcaption>%s<br><b>%s</b><br>%s</figcaption></figure>' % (p, c, n, s)) if p else
        ('<figure><div class="no">%s</div><figcaption>%s<br><b>%s</b><br>%s</figcaption></figure>' % (n, c, n, s))
        for c, n, s, p in rows)
    open("logos_check2.html", "w", encoding="utf-8").write(
        "<!doctype html><meta charset=utf-8><title>옛 회사 로고 확인 2</title>"
        "<style>body{font:14px sans-serif;background:#f4f4f2;margin:20px}div.g{display:flex;flex-wrap:wrap;gap:14px}"
        "figure{margin:0;width:170px;text-align:center}img,.no{width:110px;height:110px;border-radius:50%;"
        "background:#6B7078;display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:12px}"
        "figcaption{font-size:11px;color:#555;margin-top:6px;word-break:break-all}</style>"
        "<h2>더 찾은 로고 — 이상한 것은 logo/kr/코드.png 를 지우세요 (회색은 못 찾은 곳: 카드에 이름으로 나옴)</h2>"
        "<div class=g>" + cells + "</div>")
    print("\n찾음 %d / %d · 확인: logos_check2.html" % (sum(1 for r in rows if r[3]), len(rows)))
    if sys.platform == "darwin":
        os.system("open logos_check2.html")


if __name__ == "__main__":
    main()
