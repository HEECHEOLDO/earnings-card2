#!/usr/bin/env python3
"""
기업 로고 정리 — kr / us / us_etf  ->  logo/kr, logo/us  +  data/logos.json

하는 일
  1. 파일명에서 코드만 남긴다   000150_두산.png -> 000150.png
  2. 정사각 256px 로 줄인다      (카드에서 가장 큰 자리가 150px 안팎)
  3. 256색으로 줄여 용량을 낮춘다 (로고는 단색 위주라 눈에 거의 안 보인다)
  4. 어떤 종목에 로고가 있는지 data/logos.json 에 적는다
     -> 카드가 없는 파일을 찾느라 404 를 내지 않게 한다

사용법
  python3 prep_logos.py            # 미리보기 (아무것도 안 바꿈)
  python3 prep_logos.py --write    # 실제로 만든다
  python3 prep_logos.py --write --size 192
"""
import json, os, re, sys
from datetime import datetime, timezone, timedelta

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow 가 필요합니다:  pip install pillow")

SRC = [("kr", "kr"), ("us", "us"), ("us_etf", "us")]   # (원본 폴더, 대상 시장)
OUT = "logo"
MANIFEST = "data/logos.json"


def key_of(fn, market):
    """파일명 앞쪽의 코드만 뽑는다."""
    base = os.path.basename(fn)
    k = base.split("_")[0].strip()
    if market == "kr":
        # 우선주·전환주는 숫자만이 아니다 (00088K 한화3우B, 00104K CJ4우(전환))
        return k.upper() if re.fullmatch(r"[0-9A-Z]{6}", k.upper()) else None
    k = k.upper()
    return k if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", k) else None


def have_codes():
    """데이터가 있는 종목만 추린다. 해외 로고는 대부분 쓸 일이 없다."""
    kr, us = set(), set()
    try:
        with open("data/index.json", encoding="utf-8") as f:
            for c in json.load(f).get("companies", []):
                kr.add(str(c.get("code", "")).upper())
    except Exception:                                 # noqa: BLE001
        pass
    try:
        with open("data/us/index.json", encoding="utf-8") as f:
            for c in json.load(f).get("companies", []):
                us.add(str(c.get("code", "")).upper())
    except Exception:                                 # noqa: BLE001
        pass
    try:                                              # 수익률 탭의 ETF 까지
        with open("data/returns.json", encoding="utf-8") as f:
            for code in json.load(f).get("items", {}):
                (kr if code.isdigit() else us).add(code.upper())
    except Exception:                                 # noqa: BLE001
        pass
    return kr, us


def estimate(rows, size, n=40):
    """몇 장만 실제로 줄여 보고 전체 용량을 가늠한다."""
    import io, random
    pick = rows if len(rows) <= n else random.Random(0).sample(rows, n)
    src_b = out_b = 0
    for folder, fn, market, k in pick:
        path = os.path.join(folder, fn)
        try:
            im = Image.open(path).convert("RGBA")
        except Exception:                             # noqa: BLE001
            continue
        src_b += os.path.getsize(path)
        im.thumbnail((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        im.quantize(colors=255, method=Image.FASTOCTREE).save(buf, "PNG", optimize=True)
        out_b += buf.tell()
    if not src_b:
        return None
    return out_b / src_b


def main():
    write = "--write" in sys.argv
    size = 256
    if "--size" in sys.argv:
        i = sys.argv.index("--size")
        if i + 1 < len(sys.argv):
            size = int(sys.argv[i + 1])

    keep_all = "--all" in sys.argv
    hkr, hus = (set(), set()) if keep_all else have_codes()
    seen, rows, skipped, dupes, unused = {}, [], [], [], []
    for folder, market in SRC:
        if not os.path.isdir(folder):
            print("  ! %s 폴더가 없습니다 — 건너뜁니다" % folder)
            continue
        names = sorted(os.listdir(folder))
        for fn in names:
            if not fn.lower().endswith((".png", ".webp", ".jpg", ".jpeg")):
                continue
            k = key_of(fn, market)
            if not k:
                skipped.append((folder, fn))
                continue
            tag = market + "/" + k
            if tag in seen:
                dupes.append((tag, seen[tag], folder + "/" + fn))
                continue
            seen[tag] = folder + "/" + fn
            have = hkr if market == "kr" else hus
            if have and k not in have:
                unused.append(tag)                    # 데이터에 없는 종목
                continue
            rows.append((folder, fn, market, k))

    if not rows:
        sys.exit("정리할 파일이 없습니다. fincard 폴더에서 실행하고 있는지 확인하세요.")

    before = after = 0
    made = {"kr": [], "us": []}
    for folder, fn, market, k in rows:
        src = os.path.join(folder, fn)
        before += os.path.getsize(src)
        dst_dir = os.path.join(OUT, market)
        dst = os.path.join(dst_dir, k + ".png")
        if write:
            os.makedirs(dst_dir, exist_ok=True)
            try:
                im = Image.open(src).convert("RGBA")
            except Exception as e:                      # noqa: BLE001
                skipped.append((folder, fn + "  (" + type(e).__name__ + ")"))
                continue
            if max(im.size) != size:
                im.thumbnail((size, size), Image.LANCZOS)
            # 정사각 캔버스 가운데에 놓는다 (원본이 살짝 안 맞아도 중심이 맞게)
            if im.size != (size, size):
                sq = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                sq.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
                im = sq
            # 단색 위주라 256색으로 줄여도 눈에 안 띈다. 보통 3~4배 작아진다.
            # 다만 원래 색이 적은 그림은 오히려 커질 수 있어, 작은 쪽을 남긴다.
            im.quantize(colors=255, method=Image.FASTOCTREE).save(dst, optimize=True)
            n1 = os.path.getsize(dst)
            tmp = dst + ".rgba"
            im.save(tmp, optimize=True)
            n2 = os.path.getsize(tmp)
            if n2 < n1:
                os.replace(tmp, dst)
            else:
                os.remove(tmp)
            after += os.path.getsize(dst)
        made[market].append(k)

    for m in made:
        made[m] = sorted(set(made[m]))

    print("=" * 56)
    print("로고 정리 %s" % ("(실제 생성)" if write else "(미리보기 — 아무것도 안 바꿨습니다)"))
    print("=" * 56)
    print("  국내 %4d개  ->  %s/kr/" % (len(made["kr"]), OUT))
    print("  해외 %4d개  ->  %s/us/   (us + us_etf 합침)" % (len(made["us"]), OUT))
    print("  크기 %dx%d · 256색 PNG" % (size, size))
    if write:
        cut = (1 - after / before) * 100 if before else 0
        print("  용량 %.1fMB  ->  %.1fMB  (%s)"
              % (before / 1e6, after / 1e6,
                 ("%.0f%% 줄었습니다" % cut) if cut > 0 else "원본이 이미 작습니다"))
    else:
        r = estimate(rows, size)
        if r:
            print("  용량 %.0fMB  ->  %.0fMB 쯤 예상 (%d장 표본)"
                  % (before / 1e6, before * r / 1e6, min(40, len(rows))))
        else:
            print("  원본 용량 %.0fMB" % (before / 1e6))

    if unused:
        print("\n  데이터에 없어 건너뜀 %d개 — 쓸 일이 없는 로고입니다" % len(unused))
        print("    전부 넣으려면 --all 을 붙이세요")

    if dupes:
        print("\n  코드가 겹칩니다 %d건 — 먼저 찾은 것만 씁니다" % len(dupes))
        for tag, a, b in dupes[:10]:
            print("    %-12s %s  /  %s" % (tag, a, b))
        if len(dupes) > 10:
            print("    … 외 %d건" % (len(dupes) - 10))
    if skipped:
        print("\n  건너뛴 파일 %d건 (코드를 못 읽음)" % len(skipped))
        for folder, fn in skipped[:10]:
            print("    %s/%s" % (folder, fn))
        if len(skipped) > 10:
            print("    … 외 %d건" % (len(skipped) - 10))

    if write:
        os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump({
                "updated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"),
                "size": size,
                "kr": made["kr"], "us": made["us"],
            }, f, ensure_ascii=False, separators=(",", ":"))
        print("\n  %s 저장 — 카드가 이 목록만 보고 로고를 부릅니다" % MANIFEST)
        print("\n다음:")
        print("  git add logo data/logos.json")
        print("  git commit -m \"기업 로고 추가\"")
        print("  git pull --no-rebase && git push")
    else:
        print("\n문제 없어 보이면:  python3 prep_logos.py --write")


if __name__ == "__main__":
    main()
