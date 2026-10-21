#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시총 순위 탭의 옛 회사 로고를 채운다 → logo/kr/코드.png (원형)

  python3 make_old_logos.py            없는 것만 만들기
  python3 make_old_logos.py --force    이 표에 있는 것 전부 다시

두 가지 방법:
 1) 이어진 회사  지금 회사의 로고 파일을 그대로 복사한다 (예: 옛 국민은행 → KB금융, KTF → KT)
 2) 없어진 회사  한국어 위키백과에서 그 회사 문서의 대표 그림(대개 로고)을 받아
                흰 원 가운데에 맞춰 넣는다
끝나면 logos_check.html 을 연다 — 만든 로고를 한눈에 보고, 이상한 것은 지우면 된다
(지운 회사는 카드에서 회색 원에 이름으로 나온다).
이미 있는 logo/kr/코드.png 는 건드리지 않는다 (--force 때만 이 표의 것을 다시 만든다).
"""
import io
import json
import os
import shutil
import sys
import urllib.parse
import urllib.request

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("!! Pillow 가 필요합니다:  conda install -y pillow")

DIR = os.path.join("logo", "kr")
SIZE = 400
UA = "fincard personal project (heecheoldo@gmail.com)"

# 1) 이어진 회사 — 옛 코드: (지금 코드, 사연)
SUCCESSOR = {
    "002610": ("066570", "LG전자 (옛 법인)"),
    "011650": ("066570", "LG정보통신 → LG전자"),
    "029890": ("000660", "LG반도체 → SK하이닉스"),
    "015940": ("032640", "데이콤 → LG유플러스"),
    "016990": ("011070", "LG마이크론 → LG이노텍"),
    "003600": ("096770", "유공·SK(주) → SK이노베이션"),
    "036490": ("034730", "SK머티리얼즈 → SK"),
    "066270": ("017670", "SK커뮤니케이션즈 → SK텔레콤"),
    "033630": ("017670", "하나로텔레콤·SK브로드밴드 → SK텔레콤"),
    "032390": ("030200", "한통프리텔·KTF → KT"),
    "030700": ("030200", "한통엠닷컴 → KT"),
    "015580": ("055550", "신한은행 → 신한지주"),
    "000010": ("055550", "조흥은행 → 신한"),
    "032710": ("055550", "LG카드 → 신한카드"),
    "023130": ("105560", "국민은행 → KB금융"),
    "060000": ("105560", "국민은행 → KB금융"),
    "031150": ("105560", "국민카드 → KB"),
    "027460": ("105560", "주택은행 → 국민은행"),
    "053000": ("316140", "우리금융 (옛 법인)"),
    "000130": ("316140", "한일은행 → 우리은행"),
    "000030": ("316140", "상업은행 → 우리은행"),
    "022870": ("316140", "평화은행 → 우리은행"),
    "002860": ("086790", "하나은행 → 하나금융"),
    "004940": ("086790", "외환은행 → 하나은행"),
    "028150": ("007070", "LG홈쇼핑·GS홈쇼핑 → GS리테일"),
    "091990": ("068270", "셀트리온헬스케어 → 셀트리온"),
    "130960": ("035760", "CJ E&M → CJ ENM"),
    "049370": ("035760", "CJ엔터테인먼트 → CJ ENM"),
    "037150": ("035760", "플레너스·CJ인터넷 → CJ ENM"),
    "016170": ("035720", "로엔(멜론) → 카카오"),
    "024660": ("136480", "하림 (옛 코드)"),
}

# 2) 없어진 회사 — 옛 코드: 한국어 위키백과 문서 이름
WIKI = {
    "000200": "대우중공업",
    "012650": "쌍용건설",
    "026960": "동서 (기업)",
    "025930": "팬택",
    "027350": "텔슨전자",
    "007020": "ADT캡스",
    "043790": "옥션 (기업)",
    "048260": "오스템임플란트",
    "032380": "핸디소프트",
    "013200": "우방",
    "022130": "건영",
    "033510": "어필텔레콤",
    "031390": "서울이동통신",
    "089240": "네오세미테크",
    "014380": "대동 (기업)",
    "026950": "한일제관",
    "011860": "동아일렉콤",
    "034600": "로커스 (기업)",
    "057330": "플래닛82",
    "089480": "평산 (기업)",
    "019930": "기라정보통신",
    "031800": "씨티아이",
    "033300": "보성인터내셔널",
    "033030": "대양이앤씨",
}


def wiki_image(title):
    q = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "pageimages",
                                "piprop": "thumbnail", "pithumbsize": 600, "redirects": 1, "format": "json"})
    req = urllib.request.Request("https://ko.wikipedia.org/w/api.php?" + q, headers={"User-Agent": UA})
    j = json.load(urllib.request.urlopen(req, timeout=30))
    for p in j.get("query", {}).get("pages", {}).values():
        t = p.get("thumbnail", {}).get("source")
        if t:
            return t
    return None


def round_logo(raw):
    """로고를 흰 원 가운데에 (원 지름의 72% 안에) 맞춰 넣은 원형 PNG"""
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    bbox = im.getbbox()                       # 투명한 가장자리 잘라내기
    if bbox:
        im = im.crop(bbox)
    box = int(SIZE * 0.72)
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


def main():
    force = "--force" in sys.argv
    os.makedirs(DIR, exist_ok=True)
    made, report = 0, []
    for old, (new, why) in SUCCESSOR.items():
        dst, src = os.path.join(DIR, old + ".png"), os.path.join(DIR, new + ".png")
        if os.path.exists(dst) and not force:
            report.append((old, why, "그대로", dst))
            continue
        if not os.path.exists(src):
            report.append((old, why, "없음 — 지금 회사 로고(%s)도 없음" % new, None))
            continue
        shutil.copyfile(src, dst)
        made += 1
        report.append((old, why, "복사", dst))
    for old, title in WIKI.items():
        dst = os.path.join(DIR, old + ".png")
        if os.path.exists(dst) and not force:
            report.append((old, title, "그대로", dst))
            continue
        try:
            url = wiki_image(title)
            if not url:
                report.append((old, title, "없음 — 위키백과에 그림 없음", None))
                continue
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            open(dst, "wb").write(round_logo(urllib.request.urlopen(req, timeout=30).read()))
            made += 1
            report.append((old, title, "위키백과", dst))
        except Exception as e:                # noqa: BLE001
            report.append((old, title, "실패 — %r" % e, None))

    for old, why, st, _ in report:
        print("  %-6s %-34s %s" % (old, why, st))
    cells = "".join(
        '<figure><img src="%s"><figcaption>%s<br><b>%s</b><br>%s</figcaption></figure>'
        % (p or "", old, why, st) if p else
        '<figure><div class="no">없음</div><figcaption>%s<br><b>%s</b><br>%s</figcaption></figure>' % (old, why, st)
        for old, why, st, p in report)
    open("logos_check.html", "w", encoding="utf-8").write(
        "<!doctype html><meta charset=utf-8><title>옛 회사 로고 확인</title>"
        "<style>body{font:14px sans-serif;background:#f4f4f2;margin:20px}div.g{display:flex;flex-wrap:wrap;gap:14px}"
        "figure{margin:0;width:150px;text-align:center}img,.no{width:110px;height:110px;border-radius:50%;"
        "background:#ddd;display:inline-flex;align-items:center;justify-content:center;color:#888}"
        "figcaption{font-size:12px;color:#555;margin-top:6px}</style>"
        "<h2>옛 회사 로고 — 이상한 것은 logo/kr/코드.png 를 지우세요</h2><div class=g>" + cells + "</div>")
    print("\n새로 만든 로고 %d개 · 확인: logos_check.html" % made)
    if sys.platform == "darwin":
        os.system("open logos_check.html")


if __name__ == "__main__":
    main()
