#!/usr/bin/env python3
"""인포그래픽 '시장 이벤트' 카드 자료 (2026-11) → data/market/

  python3 collect_market.py                 전부
  python3 collect_market.py breadth investor buyback ipo insider   일부만

  breadth   상한가·하한가 · 오른/내린 종목 · 52주 신고가/신저가  ← data/krx (거래소 정규장 종가, build_market.py)
  investor  코스피·코스닥 개인·외국인·기관 순매수 (억원, 일별)    ← 네이버 증권 (거래소 집계 값)
  buyback   올해 자기주식 취득 결정 (취득 예정 금액)            ← DART 주요사항보고서
  ipo       최근 1년 새로 상장한 종목: 공모가·첫날·지금 종가     ← data/krx 에 처음 나온 날 + DART 증권신고서 공모가
  insider   미국 종목 최근 30일 내부자 장내 매수(P)·매도(S)      ← SEC Form 4 (그 회사가 발행한 주식 거래만)

값은 출처 원문 그대로 쓴다. 어림하지 않는다.
"""
import glob
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
OUT = os.path.join("data", "market")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
SEC_UA = {"User-Agent": "earnings-card2 research (github.com/HEECHEOLDO/earnings-card2)"}


def log(*a):
    print(*a, flush=True)


def jload(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:                                  # noqa: BLE001
        return d


def jsave(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, separators=(",", ":"))


def get(u, hd=None, timeout=25):
    h = dict(UA); h.update(hd or {})
    with urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=timeout) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")


def today():
    return datetime.now(KST).date()


# ------------------------------------------------------------------ breadth
def breadth():
    import build_market
    build_market.main()


# ------------------------------------------------------------------ investor
def investor():
    p = os.path.join(OUT, "investor.json")
    old = jload(p, {}) or {}
    res = {ix: {r[0]: r for r in old.get(ix, [])} for ix in ("KOSPI", "KOSDAQ")}
    last = max([max(v) for v in res.values() if v] or [0])
    t = today()
    start = t - timedelta(days=400) if not last else datetime.strptime(str(last), "%Y%m%d").date() - timedelta(days=5)   # 잠정 → 확정 값이 바뀌니 최근 며칠은 다시
    d, n = start, 0
    f = lambda s: int(str(s).replace(",", "").replace("+", ""))   # noqa: E731
    while d <= t:
        if d.weekday() < 5:
            for ix in ("KOSPI", "KOSDAQ"):
                try:
                    j = json.loads(get("https://m.stock.naver.com/api/index/%s/trend?bizdate=%s" % (ix, d.strftime("%Y%m%d"))))
                    if j.get("bizdate") == d.strftime("%Y%m%d"):
                        k = int(j["bizdate"]); res[ix][k] = [k, f(j["personalValue"]), f(j["foreignValue"]), f(j["institutionalValue"])]; n += 1
                except Exception as e:                 # noqa: BLE001
                    log("  투자자", ix, d, e)
                time.sleep(0.05)
        d += timedelta(days=1)
    cut = int((t - timedelta(days=740)).strftime("%Y%m%d"))
    out = {ix: [res[ix][k] for k in sorted(res[ix]) if k >= cut] for ix in res}
    if not out["KOSPI"]:
        log("투자자: 받은 값 없음 — 그대로 둠"); return
    jsave(p, {"updated": str(out["KOSPI"][-1][0]), "unit": "억원", "cols": ["date", "personal", "foreign", "institution"],
              "KOSPI": out["KOSPI"], "KOSDAQ": out["KOSDAQ"], "src": "네이버 증권 (거래소 투자자별 매매 집계)"})
    log("투자자: %d건 받음 · 마지막 %s" % (n, out["KOSPI"][-1]))


# ------------------------------------------------------------------ DART 공통
def dart():
    import collect as C
    if not getattr(C, "API_KEY", None):
        C.API_KEY = C.get_key()
    return C


def _won(s):
    s = str(s or "").replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def buyback():
    C = dart()
    p = os.path.join(OUT, "buyback.json")
    t = today(); y = t.year
    old = jload(p, {}) or {}
    items = {x["rcept"]: x for x in (old.get("items") or []) if old.get("year") == y}
    # 올해 '자기주식취득결정' 주요사항보고서 (정정은 원래 건을 고친 것 — 정정 뒤 값으로 바뀌게 회사별로 다시 읽는다)
    corps, rc_of = {}, {}
    a = date(y, 1, 1)
    while a <= t:
        b = min(t, date(a.year + (a.month + 2) // 12, (a.month + 2) % 12 + 1, 1) - timedelta(days=1))   # 3달씩 (DART 목록은 기간 3달까지)
        for pg in range(1, 30):
            r = C.api_get("list.json", {"bgn_de": a.strftime("%Y%m%d"), "end_de": b.strftime("%Y%m%d"), "pblntf_detail_ty": "B001", "page_count": 100, "page_no": pg})
            L = r.get("list") or []
            for x in L:
                if "자기주식취득결정" in x["report_nm"].replace(" ", ""):
                    corps.setdefault(x["corp_code"], x); rc_of.setdefault(x["corp_code"], set()).add(x["rcept_no"])
            if len(L) < 100:
                break
        a = b + timedelta(days=1)
    for cc in corps:                                   # 새 공시(정정 포함)가 있는 회사만 다시 — 올해 결정이 정정 반영된 값으로 전부 온다
        if all(r in items for r in rc_of[cc]):
            continue
        r = C.api_get("tsstkAqDecsn.json", {"corp_code": cc, "bgn_de": "%d0101" % y, "end_de": t.strftime("%Y%m%d")})
        for k in [k for k, z in items.items() if z.get("corp_code") == cc]:
            del items[k]
        for z in r.get("list") or []:
            items[z["rcept_no"]] = {"rcept": z["rcept_no"], "corp_code": cc, "name": z["corp_name"], "code": corps[cc].get("stock_code") or "",
                                    "won": _won(z.get("aqpln_prc_ostk")) + _won(z.get("aqpln_prc_estk")),
                                    "purpose": (z.get("aq_pp") or "").strip(), "how": (z.get("aq_mth") or "").strip()}
    L = sorted(items.values(), key=lambda z: -z["won"])
    jsave(p, {"year": y, "updated": t.isoformat(), "items": L, "src": "DART 주요사항보고서(자기주식취득결정) 취득예정금액"})
    log("자사주: %d건 (회사 %d) · 합계 %s원" % (len(L), len(corps), "{:,}".format(sum(z["won"] for z in L))))


def ipo():
    C = dart()
    p = os.path.join(OUT, "ipo.json")
    old = {x["code"]: x for x in ((jload(p, {}) or {}).get("items") or []) + ((jload(p, {}) or {}).get("nopr") or []) if x.get("ver") == 2}   # ver 2: 확정 공모가로 다시
    t = today(); cut = int((t - timedelta(days=366)).strftime("%Y%m%d"))
    fs = sorted(glob.glob(os.path.join("data", "krx", "2*.json")))
    seen, first, closes = set(), {}, {}
    for f in fs:
        d = int(os.path.basename(f)[:8]); c = (jload(f, {}) or {}).get("c") or {}
        for k, v in c.items():
            if k not in seen:
                seen.add(k)
                if d > 20250305:
                    first[k] = (d, v)                  # 거래소 종가 파일에 처음 나온 날 = 상장일 (파일이 시작된 첫날은 빼고)
            closes[k] = (d, v)
    cm = C.load_corp_map()
    items, nopr = [], []
    for k, (d0, v0) in sorted(first.items(), key=lambda x: x[1][0]):
        if d0 < cut:
            continue
        m = cm.get(k)
        if not m:
            continue
        nm = m.get("name") or m.get("corp_name") or ""
        if re.search(r"스팩|기업인수목적|리츠|REIT", nm):
            continue
        prc = (old.get(k) or {}).get("prc")
        if not prc and not (old.get(k) or {}).get("checked"):
            r = C.api_get("estkRs.json", {"corp_code": m["corp_code"], "bgn_de": str(d0 - 20000), "end_de": str(d0)})
            best = ""
            for g in r.get("group") or []:
                if g.get("title") == "증권의종류":
                    for x in g.get("list") or []:   # 처음 신고서는 희망 공모가 · 정정 신고서가 확정 공모가 → 가장 늦은 접수 번호를 쓴다
                        if re.sub(r"\s", "", x.get("stksen") or "") in ("보통주", "기명식보통주") and _won(x.get("slprc")) and x.get("rcept_no", "") >= best:
                            best = x.get("rcept_no", ""); prc = _won(x.get("slprc"))
        row = {"code": k, "name": nm, "list": d0, "d1": v0, "now": closes[k][1], "now_d": closes[k][0], "prc": prc, "ver": 2}
        if prc:
            items.append(row)
        else:
            row["checked"] = 1; nopr.append(row)        # 공모 없이 상장(분할·이전 상장 등) — 공모가가 없어 카드에서 뺀다
    jsave(p, {"updated": str(max(c[0] for c in closes.values())), "items": items, "nopr": nopr,
              "src": "거래소 정규장 종가(처음 나온 날 = 상장일) · DART 증권신고서(지분증권) 공모가"})
    log("공모주: %d곳 (공모가 없는 상장 %d곳 제외)" % (len(items), len(nopr)))


# ------------------------------------------------------------------ insider (SEC Form 4)
def insider():
    p = os.path.join(OUT, "insider_us.json")
    old = jload(p, {}) or {}
    cache = {x["acc"]: x for x in (old.get("tx") or [])}
    t = today(); since = (t - timedelta(days=30)).isoformat()
    idx = (jload(os.path.join("data", "us", "index.json"), {}) or {}).get("companies") or []
    tx, nfil = [], 0
    for c in idx:
        try:
            cik = c.get("cik") or (jload(os.path.join("data", "us", c["code"] + ".json"), {}) or {}).get("cik")
            cik = int(cik[0] if isinstance(cik, list) else cik)
            sub = json.loads(get("https://data.sec.gov/submissions/CIK%010d.json" % cik, SEC_UA)); time.sleep(0.12)
            rc = sub["filings"]["recent"]
            for i, f in enumerate(rc["form"]):
                if f != "4" or rc["filingDate"][i] < since:
                    continue
                acc = rc["accessionNumber"][i]
                if acc in cache:
                    tx += cache[acc]["rows"]; continue
                x = get("https://www.sec.gov/Archives/edgar/data/%d/%s/%s" % (cik, acc.replace("-", ""), rc["primaryDocument"][i].split("/")[-1]), SEC_UA); time.sleep(0.12)
                nfil += 1
                rows = []
                ic = re.search(r"<issuerCik>0*(\d+)", x)
                if ic and int(ic.group(1)) == cik:     # 이 회사가 '보고자'로 남의 주식을 산 건 빼고, 이 회사 주식 거래만
                    who = re.search(r"<rptOwnerName>([^<]+)", x); ttl = re.search(r"<officerTitle>([^<]+)", x)
                    dirr = re.search(r"<isDirector>\s*(1|true)", x, re.I); ten = re.search(r"<isTenPercentOwner>\s*(1|true)", x, re.I)
                    for blk in re.findall(r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>", x, re.S):
                        code = re.search(r"<transactionCode>(\w)", blk)
                        sh = re.search(r"<transactionShares>\s*<value>([\d.]+)", blk)
                        pr = re.search(r"<transactionPricePerShare>\s*<value>([\d.]+)", blk)
                        dt = re.search(r"<transactionDate>\s*<value>([\d-]+)", blk)
                        if code and code.group(1) in ("P", "S") and sh and pr and float(pr.group(1)) > 0:
                            rows.append({"t": c["code"], "who": (who.group(1) if who else "").replace("&amp;", "&"), "title": (ttl.group(1) if ttl else "").replace("&amp;", "&"),
                                         "dir": 1 if dirr else 0, "ten": 1 if ten else 0, "code": code.group(1),
                                         "usd": round(float(sh.group(1)) * float(pr.group(1))), "date": dt.group(1) if dt else rc["filingDate"][i]})
                cache[acc] = {"acc": acc, "filed": rc["filingDate"][i], "rows": rows}
                tx += rows
        except Exception as e:                         # noqa: BLE001
            log("  form4", c.get("code"), repr(e)[:80])
    tx = [r for r in tx if r["date"] >= since]
    keep = [v for v in cache.values() if v["filed"] >= since]
    agg = {}
    for r in tx:                                       # 같은 사람·같은 회사·같은 방향은 합친다 (여러 줄로 나눠 신고)
        k = (r["t"], r["who"], r["code"])
        if k in agg:
            agg[k]["usd"] += r["usd"]; agg[k]["date"] = max(agg[k]["date"], r["date"])
        else:
            agg[k] = dict(r)
    buy = sorted([v for v in agg.values() if v["code"] == "P"], key=lambda v: -v["usd"])
    sell = sorted([v for v in agg.values() if v["code"] == "S"], key=lambda v: -v["usd"])
    jsave(p, {"updated": t.isoformat(), "since": since, "buy": buy[:60], "sell": sell[:60], "n_buy": len(buy), "n_sell": len(sell),
              "tx": keep, "src": "SEC Form 4 (장내 매수 P · 매도 S, 주식 수 × 거래 가격)"})
    log("내부자: 새 신고 %d건 · 매수 %d명 · 매도 %d명" % (nfil, len(buy), len(sell)))


PARTS = {"breadth": breadth, "investor": investor, "buyback": buyback, "ipo": ipo, "insider": insider}

if __name__ == "__main__":
    want = [a for a in sys.argv[1:] if a in PARTS] or list(PARTS)
    bad = 0
    for k in want:
        try:
            log("== " + k); PARTS[k]()
        except Exception as e:                         # noqa: BLE001
            bad += 1; log("  %s 실패: %r" % (k, e))
    sys.exit(1 if bad == len(want) else 0)
