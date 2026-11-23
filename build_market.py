"""시장 전체 하루 통계 (인포그래픽 '상한가·하한가', '오른 종목 vs 내린 종목', '신고가·신저가') — 2026-11
data/krx/YYYYMMDD.json (거래소 전 종목 종가) 로 날마다 센다 → data/market/breadth.json
  days: [[날짜, 오른, 내린, 보합, 상한가, 하한가, 52주신고가, 52주신저가], ...]
  lim: {날짜: {"u": [코드...], "d": [코드...]}}   (상한가·하한가 종목, 상위 날만)
상한가·하한가: 직전 거래일 종가 대비 +29.5%~+30.5% / −30.5%~−29.5% (가격제한폭 ±30%, 호가 단위로 30%보다 조금 작다).
±30.5% 를 넘는 날은 거래가 아니라(액면분할·감자·재상장 등 기준가 재산정) 오른·내린 수에서도 뺀다.
52주 신고가·신저가: 그날 종가가 직전 250거래일 종가의 최고·최저를 넘을 때 (자료가 250일 넘게 쌓인 날부터).
"""
import glob, json, os

def main():
    fs = sorted(f for f in glob.glob("data/krx/2*.json"))
    hist, prev, days, lim = {}, None, [], {}
    for f in fs:
        dt = int(os.path.basename(f)[:8])
        cur = json.load(open(f, encoding="utf-8"))["c"]
        if prev is not None:
            a = dn = fl = lu = ld = nh = nl = 0; U = []; D = []
            for k, v in cur.items():
                p = prev.get(k)
                if not p or not v:
                    continue
                r = v / p - 1
                if abs(r) > 0.305:
                    continue
                if r > 0: a += 1
                elif r < 0: dn += 1
                else: fl += 1
                if r >= 0.295: lu += 1; U.append(k)
                if r <= -0.295: ld += 1; D.append(k)
                h = hist.get(k)
                if h and len(h) >= 250:
                    w = h[-250:]
                    if v > max(w): nh += 1
                    elif v < min(w): nl += 1
            days.append([dt, a, dn, fl, lu, ld, nh, nl])
            if lu + ld:
                lim[str(dt)] = {"u": U, "d": D}
        for k, v in cur.items():
            if v:
                p = prev.get(k) if prev else None
                if p and abs(v / p - 1) > 0.305:
                    hist[k] = []                       # 기준가가 바뀌면 이전 종가와 비교할 수 없다
                hist.setdefault(k, []).append(v)
                if len(hist[k]) > 300:
                    del hist[k][:-260]
        prev = cur
    os.makedirs("data/market", exist_ok=True)
    out = {"updated": str(days[-1][0]), "cols": ["date", "adv", "dec", "flat", "limit_up", "limit_dn", "new_hi", "new_lo"], "days": days, "lim": lim,
           "note": "거래소 전 종목 종가 기준 · 상한가·하한가 = 직전 종가 대비 ±29.5~30.5% · 52주 = 직전 250거래일 종가"}
    json.dump(out, open("data/market/breadth.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("days", len(days), days[-1])

if __name__ == "__main__":
    main()
