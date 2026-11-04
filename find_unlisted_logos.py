#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""비상장 회사 로고를 찾아 원형으로 만든다  ->  logo/unlisted/{회사코드}.png

  python3 find_unlisted_logos.py              로고가 없는 회사만 (목록 LIST + 비상장 전체)
  python3 find_unlisted_logos.py 00359386     그 회사만 (있어도 다시)
  python3 find_unlisted_logos.py --list-only  LIST 에 적은 회사만

깃허브 Actions 의 '비상장 로고 찾기' 를 눌러 돌리면 된다 (컴퓨터에서 돌려도 같다).
찾는 순서는 find_logos.py 와 같다 (먼저 찾은 것을 쓴다):
 1) 한국어·영어 위키백과 문서에 들어 있는 그림 중 이름에 logo·로고·CI·심볼 이 든 파일
 2) 위키미디어 공용(Commons)에서 '브랜드 logo' 로 검색한 그림
 3) 브랜드 홈페이지 아이콘
그래도 없으면 그대로 둔다 → 카드에서 브랜드 색 원에 이름.

직접 구한 그림은 logo_in_unlisted/{회사코드}.png (jpg·webp 도 됨) 로 넣고 다시 돌리면 원형으로 바꿔 넣는다.
끝나면 logos_check_unlisted.html 을 만든다 — 사이트에서 열어 어디서 가져왔는지 보고,
이상한 것은 logo/unlisted/코드.png 를 지우거나 NO_AUTO 에 코드를 더하면 된다.
"""
import json
import os
import re
import sys

from find_logos import from_page, from_commons, from_site, get
from make_old_logos import round_logo

DIR = os.path.join("logo", "unlisted")
IN_DIR = "logo_in_unlisted"
CHECK = "logos_check_unlisted.html"

# 회사코드: (한국어 위키 문서, 영어 위키 문서, 공용 검색어들, 브랜드 홈페이지)
# 비교 탭에 나오는 브랜드를 먼저 적는다. 여기 없는 회사는 대표 브랜드 이름으로 한국어 위키만 찾아본다.
LIST = {
    # 커피
    "00359386": ("스타벅스", "Starbucks", ["Starbucks Corporation Logo", "Starbucks logo"], "starbucks.co.kr"),
    "01450239": ("메가MGC커피", None, ["Mega Coffee logo", "메가커피 로고"], "mega-mgccoffee.com"),
    "01275948": ("투썸플레이스", "A Twosome Place", ["A Twosome Place logo"], "twosome.co.kr"),
    "01755985": ("컴포즈커피", None, ["Compose Coffee logo"], "composecoffee.com"),
    "00960942": ("이디야커피", "Ediya Coffee", ["Ediya Coffee logo"], "ediya.com"),
    "00989600": ("폴 바셋", None, ["Paul Bassett logo"], "baristapaulbassett.co.kr"),
    "00455404": ("커피빈 앤 티리프", "The Coffee Bean & Tea Leaf", ["Coffee Bean & Tea Leaf logo"], "coffeebeankorea.com"),
    "01553749": ("블루보틀 커피", "Blue Bottle Coffee", ["Blue Bottle Coffee logo"], "bluebottlecoffee.com"),
    # 치킨
    "00656988": ("BHC (기업)", None, ["bhc chicken logo"], "bhc.co.kr"),
    "00320791": ("제너시스BBQ", "Genesis BBQ", ["BBQ chicken logo", "Genesis BBQ logo"], "bbq.co.kr"),
    "00865638": ("굽네치킨", None, ["Goobne logo"], "goobne.co.kr"),
    "01461110": ("노랑통닭", None, ["노랑통닭 로고"], "norangtongdak.co.kr"),
    "01935697": ("처갓집양념치킨", None, ["처갓집 로고"], "cheogajip.co.kr"),
    "00765550": ("네네치킨", None, ["Nene Chicken logo"], "nenechicken.com"),
    # 버거
    "00120979": ("한국맥도날드", "McDonald's", ["McDonald's Golden Arches", "McDonald's logo"], "mcdonalds.co.kr"),
    "00948685": ("버거킹", "Burger King", ["Burger King 2020 logo", "Burger King logo"], "burgerking.co.kr"),
    "01089855": ("맘스터치", "Mom's Touch", ["Mom's Touch logo"], "momstouch.co.kr"),
    "00514105": ("KFC", "KFC", ["KFC logo"], "kfckorea.com"),
    # 빵집
    "01995325": ("파리바게뜨", "Paris Baguette", ["Paris Baguette logo"], "paris.co.kr"),
    "01070750": ("성심당", None, ["성심당 로고"], "sungsimdangmall.co.kr"),
    "01813687": ("런던베이글뮤지엄", None, ["London Bagel Museum logo"], None),
    # 프로야구단
    "00470050": ("두산 베어스", "Doosan Bears", ["Doosan Bears logo", "Doosan Bears emblem"], "doosanbears.com"),
    "00471271": ("롯데 자이언츠", "Lotte Giants", ["Lotte Giants logo", "Lotte Giants emblem"], "giantsclub.com"),
    "00768618": ("키움 히어로즈", "Kiwoom Heroes", ["Kiwoom Heroes logo"], "heroesbaseball.co.kr"),
    "00363097": ("SSG 랜더스", "SSG Landers", ["SSG Landers logo"], "ssglanders.com"),
    "00923507": ("NC 다이노스", "NC Dinos", ["NC Dinos logo"], "ncdinos.com"),
    "00180546": ("삼성 라이온즈", "Samsung Lions", ["Samsung Lions logo"], "samsunglions.com"),
    "00234050": ("한화 이글스", "Hanwha Eagles", ["Hanwha Eagles logo"], "hanwhaeagles.co.kr"),
    "00520249": ("KIA 타이거즈", "Kia Tigers", ["Kia Tigers logo"], "tigers.co.kr"),
    "00981954": ("kt wiz", "KT Wiz", ["KT Wiz logo"], "ktwiz.co.kr"),
    "00100090": ("LG 트윈스", "LG Twins", ["LG Twins logo"], "lgtwins.com"),
    # 수입차
    "00454159": ("메르세데스-벤츠", "Mercedes-Benz", ["Mercedes-Benz Star", "Mercedes-Benz logo"], "mercedes-benz.co.kr"),
    "00222675": ("BMW", "BMW", ["BMW logo (gray)", "BMW logo"], "bmw.co.kr"),
    "01015391": ("포르쉐", "Porsche", ["Porsche crest", "Porsche logo"], "porsche.com"),
    "00336561": ("도요타 자동차", "Toyota", ["Toyota carlogo", "Toyota logo"], "toyota.co.kr"),
    "00534066": ("아우디", "Audi", ["Audi logo detail", "Audi logo"], "audi.co.kr"),
    "00372697": ("볼보 자동차", "Volvo Cars", ["Volvo Cars logo", "Volvo iron mark"], "volvocars.com"),
    # 명품·시계·보석
    "01470792": ("샤넬", "Chanel", ["Chanel logo interlocking cs"], "chanel.com"),
    "00241096": ("루이 비통", "Louis Vuitton", ["Louis Vuitton logo and wordmark", "Louis Vuitton logo"], "louisvuitton.com"),
    "01460643": ("에르메스", "Hermès", ["Hermes logo"], "hermes.com"),
    "00255114": ("까르띠에", "Cartier (jeweler)", ["Cartier logo"], "cartier.com"),
    "00427623": ("크리스챤 디올", "Dior", ["Dior Logo"], "dior.com"),
    "00243605": ("프라다", "Prada", ["Prada logo"], "prada.com"),
    "00490373": ("롤렉스", "Rolex", ["Rolex logo"], "rolex.com"),
    "00314912": ("티파니", "Tiffany & Co.", ["Tiffany & Co. logo"], "tiffany.co.kr"),
    "00450144": ("스와로브스키", "Swarovski", ["Swarovski logo"], "swarovski.com"),
    # 편의점·유통
    "00186513": ("세븐일레븐", "7-Eleven", ["7-eleven logo"], "7-eleven.co.kr"),
    "01003031": ("이마트24", None, ["Emart24 logo"], "emart24.co.kr"),
    "00259572": ("코스트코", "Costco", ["Costco Wholesale logo"], "costco.co.kr"),
    "00411835": ("다이소", "Daiso", ["Daiso logo"], "daiso.co.kr"),
    "01423068": ("올리브영", "CJ Olive Young", ["Olive Young logo"], "oliveyoung.co.kr"),
    "01505760": ("이케아", "IKEA", ["Ikea logo"], "ikea.com"),
    # 배달·커머스
    "01063273": ("배달의민족", "Baemin", ["Baemin logo", "배달의민족 로고"], "baemin.com"),
    "01571329": ("쿠팡이츠", None, ["Coupang Eats logo"], "coupangeats.com"),
    "01695300": ("요기요", "Yogiyo", ["Yogiyo logo"], "yogiyo.co.kr"),
    "01019166": ("쿠팡", "Coupang", ["Coupang logo"], "coupang.com"),
    "01153956": ("컬리 (기업)", "Kurly", ["Kurly logo", "Market Kurly logo"], "kurly.com"),
    "01346404": ("SSG닷컴", None, ["SSG.COM logo"], "ssg.com"),
    "01326206": ("11번가", "11st", ["11st logo"], "11st.co.kr"),
    "00310280": ("G마켓", "Gmarket", ["Gmarket logo"], "gmarket.co.kr"),
    "01944598": ("알리익스프레스", "AliExpress", ["AliExpress logo"], "aliexpress.com"),
    "01137727": ("무신사", "Musinsa", ["Musinsa logo"], "musinsa.com"),
    # 패션
    "00553399": ("유니클로", "Uniqlo", ["UNIQLO logo"], "uniqlo.com"),
    "00773586": ("자라 (기업)", "Zara (retailer)", ["Zara logo"], "zara.com"),
    "00834498": ("H&M", "H&M", ["H&M-Logo"], "hm.com"),
    "00136341": ("신성통상", None, ["TOPTEN10 logo", "탑텐 로고"], "topten10mall.com"),
    "00249858": ("노스페이스", "The North Face", ["The North Face logo"], "thenorthfacekorea.co.kr"),
    "01086414": ("파타고니아 (기업)", "Patagonia, Inc.", ["Patagonia logo"], "patagonia.co.kr"),
    "00520850": ("블랙야크", "Black Yak", ["Black Yak logo"], "byn.kr"),
    "00932930": ("네파", None, ["NEPA logo"], "nepa.co.kr"),
    "00411154": ("데상트", "Descente", ["Descente logo"], "descentekorea.co.kr"),
    "01503133": ("나이키", "Nike, Inc.", ["Logo NIKE"], "nike.com"),
    # 게임
    "00547033": ("넥슨", "Nexon", ["Nexon logo"], "nexon.com"),
    "00868194": ("스마일게이트", "Smilegate", ["Smilegate logo"], "smilegate.com"),
    "01455960": ("라이엇 게임즈", "Riot Games", ["Riot Games logo"], "riotgames.com"),
    # 주류·식품
    "00254911": ("오비맥주", "Oriental Brewery", ["Cass beer logo", "Oriental Brewery logo"], "obbeer.co.kr"),
    "00470865": ("하이네켄", "Heineken", ["Heineken logo"], "heineken.com"),
    "00504047": ("아사히 맥주", "Asahi Breweries", ["Asahi Breweries logo"], "asahibeer.co.kr"),
    "00227643": ("팔도 (기업)", "Paldo (company)", ["Paldo logo"], "paldofood.co.kr"),
    # 가구
    "00669353": ("일룸", None, ["iloom logo"], "iloom.com"),
    "00201557": ("시몬스 (기업)", "Simmons Bedding Company", ["Simmons logo"], "simmons.co.kr"),
    "00250599": ("까사미아", None, ["Casamia logo"], "casamia.co.kr"),
    # 핀테크·가상자산·OTT
    "01212921": ("비바리퍼블리카", "Toss (app)", ["Toss logo", "Viva Republica logo"], "toss.im"),
    "01527984": ("토스증권", None, ["Toss Securities logo"], "tossinvest.com"),
    "01421750": ("네이버파이낸셜", None, ["Naver Pay logo"], "naverfincorp.com"),
    "01310241": ("두나무", "Dunamu", ["Upbit logo", "Dunamu logo"], "upbit.com"),
    "01214044": ("빗썸", "Bithumb", ["Bithumb logo"], "bithumb.com"),
    "01263378": ("코인원", None, ["Coinone logo"], "coinone.co.kr"),
    "01221743": ("코빗", "Korbit", ["Korbit logo"], "korbit.co.kr"),
    "01514351": ("티빙", "TVING", ["TVING logo"], "tving.com"),
    "00944926": ("웨이브 (OTT)", "Wavve", ["Wavve logo"], "wavve.com"),
    "01434295": ("넷플릭스", "Netflix", ["Netflix 2015 logo"], "netflix.com"),
    # 항공
    "01100370": ("에어서울", "Air Seoul", ["Air Seoul logo"], "flyairseoul.com"),
    "00764205": ("이스타항공", "Eastar Jet", ["Eastar Jet logo"], "eastarjet.com"),
    "01380727": ("에어프레미아", "Air Premia", ["Air Premia logo"], "airpremia.com"),
    # 빅테크·제약 한국 지사 (비교 탭은 본사 로고를 쓰지만 비상장 탭에서 쓴다)
    "00349200": ("애플 (기업)", "Apple Inc.", ["Apple logo black"], "apple.com"),
    "01473717": ("구글", "Google", ["Google 2015 logo"], "google.co.kr"),
    "01469635": ("메타 플랫폼스", "Meta Platforms", ["Meta Platforms Inc. logo"], "meta.com"),
    "00203519": ("오라클", "Oracle Corporation", ["Oracle logo"], "oracle.com"),
    "00156363": ("IBM", "IBM", ["IBM logo"], "ibm.com"),
    "01487950": ("어도비", "Adobe Inc.", ["Adobe Corporate logo"], "adobe.com"),
    "01053911": ("퀄컴", "Qualcomm", ["Qualcomm logo"], "qualcomm.com"),
    "00221621": ("인텔", "Intel", ["Intel logo (2020, dark blue)"], "intel.com"),
    "01475371": ("테슬라 (기업)", "Tesla, Inc.", ["Tesla Motors logo", "Tesla T symbol"], "tesla.com"),
    "00160603": ("화이자", "Pfizer", ["Pfizer (2021)"], "pfizer.co.kr"),
    "00157760": ("노바티스", "Novartis", ["Novartis-Logo"], "novartis.com"),
    "00248114": ("노보 노디스크", "Novo Nordisk", ["Novo Nordisk logo"], "novonordisk.co.kr"),
    "00111801": ("일라이 릴리", "Eli Lilly and Company", ["Eli Lilly and Company logo"], "lilly.co.kr"),
    "00225733": ("머크 앤드 컴퍼니", "Merck & Co.", ["MSD logo"], "msd-korea.com"),
    "00197980": ("아스트라제네카", "AstraZeneca", ["AstraZeneca logo"], "astrazeneca.co.kr"),
}
# 자동으로 찾은 그림이 틀렸던 회사 — 다시 돌려도 자동으로는 안 찾는다 (logo_in_unlisted 로 직접 넣는다)
NO_AUTO = set()


def companies():
    with open(os.path.join("data", "unlisted", "index.json"), encoding="utf-8") as f:
        return {c["code"]: c for c in json.load(f)["companies"]}


def from_folder(only):
    done = []
    if not os.path.isdir(IN_DIR):
        return done
    for f in sorted(os.listdir(IN_DIR)):
        m = re.fullmatch(r"(\d{8})\.(png|jpe?g|webp)", f, re.I)
        if not m or (only and m.group(1) not in only):
            continue
        dst = os.path.join(DIR, m.group(1) + ".png")
        open(dst, "wb").write(round_logo(open(os.path.join(IN_DIR, f), "rb").read()))
        done.append((m.group(1), f, "직접 넣음 · %s/%s" % (IN_DIR, f), dst))
        print("  %s %-16s 직접 넣음" % (m.group(1), f))
    return done


def main():
    os.makedirs(DIR, exist_ok=True)
    only = {a for a in sys.argv[1:] if re.fullmatch(r"\d{8}", a)}
    allc = companies()
    rows = from_folder(only)
    manual = {r[0] for r in rows}
    targets = list(LIST.keys())
    if "--list-only" not in sys.argv:          # 목록에 없는 비상장사도 대표 브랜드 이름으로 한 번
        targets += [c for c in allc if c not in LIST]
    for code in targets:
        if code in manual or code in NO_AUTO or (only and code not in only):
            continue
        dst = os.path.join(DIR, code + ".png")
        if not only and os.path.exists(dst):
            continue
        c = allc.get(code, {})
        if code in LIST:
            ko, en, words, domain = LIST[code]
        else:
            brand = re.split(r"[,(]", c.get("brand") or c.get("name") or "")[0].strip()
            ko, en, words, domain = brand or None, None, [], None
        name = c.get("brand") or c.get("name") or ko or code
        got, why = None, ""
        for step in (lambda: from_page("ko", ko), lambda: from_page("en", en),
                     lambda: from_commons(words), lambda: from_site(domain)):
            try:
                r = step()
            except Exception as e:            # noqa: BLE001
                why = repr(e)[:80]
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
                why = repr(e)[:80]
        rows.append((code, name, got or ("못 찾음 " + why).strip(), dst if got else None))
        print("  %s %-16s %s" % (code, name[:16], got or "못 찾음"))

    # 확인 화면 — 사이트에서 열어 본다 (https://.../logos_check_unlisted.html)
    have = sorted(f[:-4] for f in os.listdir(DIR) if f.endswith(".png"))
    seen = {r[0] for r in rows}
    rows += [(c, (allc.get(c) or {}).get("brand") or (allc.get(c) or {}).get("name") or c, "이전에 받아 둔 것",
              os.path.join(DIR, c + ".png")) for c in have if c not in seen]
    cells = "".join(
        ('<figure><img src="%s"><figcaption>%s<br><b>%s</b><br>%s</figcaption></figure>' % (p, c, n, s)) if p else
        ('<figure><div class="no">%s</div><figcaption>%s<br><b>%s</b><br>%s</figcaption></figure>' % (n, c, n, s))
        for c, n, s, p in rows)
    open(CHECK, "w", encoding="utf-8").write(
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>비상장 로고 확인</title>"
        "<style>body{font:14px sans-serif;background:#f4f4f2;margin:20px}div.g{display:flex;flex-wrap:wrap;gap:14px}"
        "figure{margin:0;width:150px;text-align:center}img,.no{width:100px;height:100px;border-radius:50%;"
        "background:#6B7078;display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:12px;"
        "box-shadow:0 0 0 1px #ddd}figcaption{font-size:11px;color:#555;margin-top:6px;word-break:break-all}</style>"
        "<h2>비상장 로고 — 이상한 것은 logo/unlisted/코드.png 를 지우세요 (회색은 못 찾은 곳: 카드에 브랜드 색 원)</h2>"
        "<div class=g>" + cells + "</div>")
    print("\n로고 있음 %d곳 · 이번에 찾음 %d / %d · 확인: %s" % (
        len(have), sum(1 for r in rows if r[3] and r[2] != "이전에 받아 둔 것"), len(rows), CHECK))


if __name__ == "__main__":
    main()
