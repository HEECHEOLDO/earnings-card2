"""상장사 분기 실적 합계 (인포그래픽 '실적 시즌 성적표', '업종별 이익 증가율', '반도체 이익 비중', '이익률 개선') — 2026-11
data/{종목}.json 의 분기 실적(DART, 연결 우선, 억원)과 data/mcap.json 의 업종(네이버 업종)·시가총액으로 센다
→ data/market/earn_q.json

  q:      최근 9개 분기 ["2024Q3", …]
  tot:    분기마다 [영업이익 합, 매출 합, 회사 수] — 9개 분기를 모두 낸 회사만 (같은 회사끼리 비교)
  semi:   분기마다 반도체 업종 영업이익 합 (같은 회사들)
  yoy:    마지막 분기 vs 1년 전 같은 분기 — 둘 다 낸 회사: {n, up, down, turn_up, turn_dn, op_now, op_prev}
  ind:    업종별 마지막 분기 vs 1년 전 [업종, 영업이익 지금, 1년 전, 회사 수, 시가총액]
  marg:   시가총액 1조 이상 · 매출 1,000억 이상 회사의 영업이익률 변화 [코드, 이름, 지금 %, 1년 전 %]
금융사(은행·보험·증권)는 실적 수집 대상이 아니라 빠진다. 분기 실적이 9월 이후 갱신되지 않은 회사가 있으면 그만큼 빠진다.
"""
import glob, json, os

OUT = os.path.join("data", "market", "earn_q.json")


def qkey(y, q):
    return "%dQ%d" % (y, q)


def prev_q(y, q, n):
    k = y * 4 + (q - 1) - n
    return k // 4, k % 4 + 1


def main():
    m = json.load(open(os.path.join("data", "mcap.json"), encoding="utf-8"))
    ind_of, cap = {}, {}
    for g in m["groups"]["industry"]:
        for c in g["codes"]:
            ind_of.setdefault(c, (g.get("short") or g["name"]).strip())
    for c, s in m["stocks"].items():
        cap[c] = s.get("c") or 0
    comp = {}
    for f in glob.glob(os.path.join("data", "[0-9]*.json")):
        code = os.path.basename(f)[:-5]
        if code not in cap:                      # 지금 상장된 보통주만 (시가총액 표에 있는 회사)
            continue
        try:
            j = json.load(open(f, encoding="utf-8"))
        except Exception:                        # noqa: BLE001
            continue
        qs = {(x["y"], x["q"]): x for x in (j.get("quarterly") or []) if x.get("op") is not None}
        if qs:
            comp[code] = (j.get("name"), qs)
    # 마지막 분기 = 회사 절반 이상이 낸 가장 최근 분기
    cnt = {}
    for _, qs in comp.values():
        for k in qs:
            cnt[k] = cnt.get(k, 0) + 1
    last = max(k for k, v in cnt.items() if v >= len(comp) * 0.5)
    Q = [prev_q(last[0], last[1], n) for n in range(8, -1, -1)]
    full = [c for c, (_, qs) in comp.items() if all(k in qs for k in Q)]
    tot = [[round(sum(comp[c][1][k]["op"] for c in full), 1), round(sum(comp[c][1][k].get("rev") or 0 for c in full), 1), len(full)] for k in Q]
    semi = [round(sum(comp[c][1][k]["op"] for c in full if ind_of.get(c) == "반도체"), 1) for k in Q]
    ya = prev_q(last[0], last[1], 4)
    pair = [c for c, (_, qs) in comp.items() if last in qs and ya in qs]
    y = {"n": len(pair), "up": 0, "down": 0, "turn_up": 0, "turn_dn": 0,
         "op_now": round(sum(comp[c][1][last]["op"] for c in pair), 1), "op_prev": round(sum(comp[c][1][ya]["op"] for c in pair), 1)}
    ind = {}
    for c in pair:
        a, b = comp[c][1][last]["op"], comp[c][1][ya]["op"]
        y["up" if a > b else "down"] += 1
        if b <= 0 < a:
            y["turn_up"] += 1
        if a <= 0 < b:
            y["turn_dn"] += 1
        g = ind_of.get(c)
        if g:
            r = ind.setdefault(g, [g, 0.0, 0.0, 0, 0.0])
            r[1] += a; r[2] += b; r[3] += 1; r[4] += cap.get(c, 0)
    marg = []
    for c in pair:
        a, b = comp[c][1][last], comp[c][1][ya]
        if cap.get(c, 0) >= 10000 and (a.get("rev") or 0) >= 1000 and (b.get("rev") or 0) >= 1000:
            marg.append([c, comp[c][0], round(a["op"] / a["rev"] * 100, 1), round(b["op"] / b["rev"] * 100, 1)])
    out = {"updated": m.get("asof"), "last": qkey(*last), "q": [qkey(*k) for k in Q], "tot": tot, "semi": semi, "yoy": y,
           "ind": sorted([[r[0], round(r[1], 1), round(r[2], 1), r[3], round(r[4])] for r in ind.values()], key=lambda r: -r[4]),
           "marg": marg, "unit": "억원", "src": "DART 분기 실적(연결 우선) · 업종은 네이버 업종 분류"}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("실적 합계: %s · 9개 분기 모두 낸 %d곳 · 1년 전과 비교 %d곳 (늘어난 곳 %d)" % (out["last"], len(full), y["n"], y["up"]))


if __name__ == "__main__":
    main()
