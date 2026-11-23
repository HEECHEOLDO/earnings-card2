"""국내 주가 차트 일별 종가를 거래소 정규장 종가로 바로잡는다 (2026-11)

네이버 일별 종가는 가끔 하루만 틀린다 — 장 마감 뒤 거래(NXT) 가격이 섞이거나, 수정주가 보정이 그날만 빠진다
(예: 006980 2026-10-08 21,550원 · 앞뒤 날은 16,500원대 · 거래소 정규장 종가 15,920원).
data/krx/YYYYMMDD.json (거래소 정규장 종가, krx_close.py) 과 견줘서
  · 앞뒤 날의 '차트 ÷ 거래소' 비율(수정주가 배율)이 같은데 그날만 다르면 → 거래소 종가 × 그 배율로 고친다
  · 마지막 날은 수정주가 배율이 1 이어야 하므로 → 거래소 종가와 다르면 거래소 종가로
수정주가 배율 자체(액면분할·유무상증자 보정)는 건드리지 않는다.

  python3 fix_close.py            data/chart/kr/*.json 을 고친다 (호출 0회)
  python3 fix_close.py --dry      고칠 곳만 보여 준다
"""
import glob, json, os, sys

_KRX = None


def krx():
    global _KRX
    if _KRX is None:
        _KRX = {}
        for f in glob.glob(os.path.join("data", "krx", "2*.json")):
            try:
                _KRX[int(os.path.basename(f)[:8])] = json.load(open(f, encoding="utf-8"))["c"]
            except Exception:                    # noqa: BLE001
                pass
    return _KRX


def _mode(xs):
    """가장 많이 나온 비율 (0.1% 안이면 같은 것으로) — (그 비율들의 평균, 개수)"""
    best = (None, 0)
    for x in xs:
        same = [y for y in xs if abs(y / x - 1) <= 0.001]
        if len(same) > best[1]:
            best = (sum(same) / len(same), len(same))
    return best


def fix(code, rows):
    """rows: [[날짜, 종가], ...] 날짜순. 고친 곳 목록을 돌려주고 rows 를 그 자리에서 고친다.
    배율(차트 ÷ 거래소 종가)이 같은 날들을 묶는다(0.1% 안). 짧은 묶음(1~5일)의 앞 10일·뒤 10일이 각각 5일 넘게
    같은 배율이면 그 며칠만 잘못 들어온 값이라 보고 '거래소 종가 × 앞뒤 배율'로 고친다.
    배율이 한 번 바뀌고 그대로 가는 날(액면분할·무상증자 등 진짜 수정주가 보정)은 건드리지 않는다.
    마지막 1~2일이 바로 앞 묶음(3일 이상)과 다르면 그 배율로 맞춘다 (장 마감 뒤 거래 가격이 섞인 최근 종가).
    5% 넘게 바뀌는 값은 고친 값이 앞뒤 날과 훨씬 매끄럽게 이어질 때만 고친다 (어느 쪽이 맞는지 애매하면 그대로 둔다)."""
    K = krx()
    idx = [(i, rows[i][1] / K[int(rows[i][0])][code]) for i in range(len(rows))
           if int(rows[i][0]) in K and K[int(rows[i][0])].get(code) and rows[i][1]]
    runs = []
    for p in idx:
        if runs and abs(p[1] / runs[-1][-1][1] - 1) <= 0.001:
            runs[-1].append(p)
        else:
            runs.append([p])
    fac = [_mode([x[1] for x in g])[0] for g in runs]
    ch = []
    for k in range(1, len(runs)):
        g = runs[k]
        last = k == len(runs) - 1
        if last:
            ok = len(g) <= 2 and len(runs[k - 1]) >= 3 and g[-1][0] == len(rows) - 1
            f = fac[k - 1]
        else:
            j0 = idx.index(g[0]); j1 = idx.index(g[-1])
            L, nl = _mode([x[1] for x in idx[max(0, j0 - 10):j0]])
            R, nr = _mode([x[1] for x in idx[j1 + 1:j1 + 11]])
            ok = len(g) <= 5 and L is not None and R is not None and nl >= 5 and nr >= 5 and abs(L / R - 1) <= 0.001   # 앞뒤 10일 중 5일 넘게 같은 배율
            f = (L + R) / 2 if ok else None
            if not ok and len(g) <= 5 and len(runs[k - 1]) >= 3 and len(runs[k + 1]) >= 3 and abs(fac[k - 1] / fac[k + 1] - 1) <= 0.001:
                ok, f = True, (fac[k - 1] + fac[k + 1]) / 2       # 바로 앞뒤 묶음이 3일 넘게 같은 배율
        if not ok or abs(fac[k] / f - 1) <= 0.002:
            continue
        for i, r in g:
            kc = K[int(rows[i][0])][code]
            v = round(kc * f, 2)
            v = int(v) if v == int(v) else v
            if abs(v / rows[i][1] - 1) > 0.05:
                p0 = rows[i - 1][1] if i > 0 else None
                p1 = rows[i + 1][1] if i + 1 < len(rows) else None
                if p0 is None or p1 is None or not abs(v - p0) + abs(p1 - v) < (abs(rows[i][1] - p0) + abs(p1 - rows[i][1])) * 0.5:
                    continue
            ch.append((i, v))
    out = []
    for i, v in ch:
        out.append((rows[i][0], rows[i][1], v))
        rows[i][1] = v
    return out


def main():
    dry = "--dry" in sys.argv
    n = files = 0
    for f in sorted(glob.glob(os.path.join("data", "chart", "kr", "*.json"))):
        code = os.path.basename(f)[:-5]
        j = json.load(open(f, encoding="utf-8"))
        ch = fix(code, j.get("d") or [])
        if not ch:
            continue
        n += len(ch); files += 1
        for c in ch[:3]:
            print("  %s %s  %s → %s" % (code, c[0], c[1], c[2]))
        if not dry:
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(j, fh, separators=(",", ":"))
    print("고친 날 %d · 종목 %d%s" % (n, files, " (미리 보기)" if dry else ""))


if __name__ == "__main__":
    main()
