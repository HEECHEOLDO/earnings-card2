#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시총 순위 탭에 1995~2019년 연말을 채운다 — 승인·키 필요 없음.

  python3 import_marcap.py              1995~2019 빠진 해 채우기
  python3 import_marcap.py 2008 2009    그 해만
  python3 import_marcap.py --force      이미 있는 해도 다시

출처: FinanceData/marcap (GitHub 공개 자료, 1995년 5월부터 매일 전 종목 시가총액 —
      한국거래소 자료를 모아 둔 것). 해마다 파일 하나(수 MB)를 받아 그 해 마지막 거래일만 쓴다.
받은 파일은 _marcap/ 에 두어 다시 받지 않는다 (.gitignore 에 넣는다).
결과는 collect_rank.py 와 같은 data/rank.json 에 연도 칸으로 더한다 (src: marcap).
연말 자료는 바뀌지 않으므로 한 번만 돌리면 된다.
"""
import csv
import gzip
import io
import json
import os
import sys
import re
import time
import urllib.parse
import urllib.request
from datetime import date

import collect_rank as C

CACHE = "_marcap"
REPO = "FinanceData/marcap"
FIRST, LAST = 1995, C.START - 1
_TREE = {}


def gh(url):
    req = urllib.request.Request(url, headers={"User-Agent": "fincard personal project",
                                               "Accept": "application/vnd.github+json"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def tree():
    """저장소의 파일 목록 (한 번만 받는다)"""
    if not _TREE:
        br = gh("https://api.github.com/repos/%s" % REPO).get("default_branch", "master")
        t = gh("https://api.github.com/repos/%s/git/trees/%s?recursive=1" % (REPO, br))
        _TREE["branch"] = br
        _TREE["paths"] = [x["path"] for x in t.get("tree", []) if x.get("type") == "blob"]
        data = [p for p in _TREE["paths"] if re.search(r"(19|20)\d\d", os.path.basename(p))]
        print("  저장소 %s (가지 %s) · 연도 파일 %d개 · 예: %s" % (REPO, br, len(data), ", ".join(data[:3])))
    return _TREE


def find_path(y):
    ps = [p for p in tree()["paths"] if re.search(r"(?<!\d)%d(?!\d)" % y, os.path.basename(p))
          and re.search(r"\.(csv(\.gz)?|parquet)$", p)]
    ps.sort(key=lambda p: (not p.endswith(".parquet"), not p.endswith(".gz"), len(p)))
    return ps[0] if ps else None


def fetch(y):
    os.makedirs(CACHE, exist_ok=True)
    for ext in (".parquet", ".csv.gz", ".csv"):
        path = os.path.join(CACHE, "marcap-%d%s" % (y, ext))
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    src = find_path(y)
    if not src:
        raise RuntimeError("저장소에 %d년 파일이 없습니다" % y)
    br, last = tree()["branch"], None
    for base in ("https://raw.githubusercontent.com/%s/%s/" % (REPO, br),
                 "https://media.githubusercontent.com/media/%s/%s/" % (REPO, br)):
        try:
            req = urllib.request.Request(base + urllib.parse.quote(src), headers={"User-Agent": "fincard personal project"})
            raw = urllib.request.urlopen(req, timeout=180).read()
        except Exception as e:                   # noqa: BLE001
            last = repr(e)
            continue
        if raw.startswith(b"version https://git-lfs"):
            last = "LFS 안내문"
            continue
        ext = ".parquet" if raw[:4] == b"PAR1" else ".csv.gz" if raw[:2] == b"\x1f\x8b" else ".csv"
        path = os.path.join(CACHE, "marcap-%d%s" % (y, ext))
        open(path, "wb").write(raw)
        return path
    raise RuntimeError("받지 못함 (%s): %s" % (src, last))


def year_end_parquet(path, y):
    try:
        import pandas as pd
        df = pd.read_parquet(path)
    except ImportError:
        sys.exit("\n!! parquet 파일을 읽으려면 pyarrow 가 필요합니다. 아래를 한 번 실행한 뒤 다시 돌려 주세요:\n"
                 "   pip3 install pandas pyarrow")
    cols = {str(k).lower(): k for k in df.columns}
    if "date" not in cols and df.index.name and str(df.index.name).lower() == "date":
        df = df.reset_index()
        cols = {str(k).lower(): k for k in df.columns}
    miss = [k for k in ("code", "name", "market", "marcap", "date") if k not in cols]
    if miss:
        raise RuntimeError("열 이름이 다릅니다: 없는 것 %s / 있는 것 %s" % (miss, list(df.columns)))
    d = df[cols["date"]].astype(str).str[:10]
    df = df[d.str.startswith(str(y))]
    if df.empty:
        return "", []
    last = df[cols["date"]].astype(str).str[:10].max()
    df = df[df[cols["date"]].astype(str).str[:10] == last]
    rows = []
    for code, name, mk, cap in zip(df[cols["code"]], df[cols["name"]], df[cols["market"]], df[cols["marcap"]]):
        m = str(mk or "").upper()
        m = "KOSDAQ" if m.startswith("KOSDAQ") else "KOSPI" if m.startswith("KOSPI") else m
        try:
            cap = int(float(cap or 0))
        except (TypeError, ValueError):
            cap = 0
        rows.append((str(code).zfill(6), str(name), m, cap))
    if rows and max(r[3] for r in rows) < 10 ** 11:
        rows = [(c, n, m, cap * 10 ** 6) for c, n, m, cap in rows]
    return last, rows


def year_end(path, y):
    if path.endswith(".parquet"):
        return year_end_parquet(path, y)
    """그 해 마지막 거래일과 그날 [(코드, 이름, 시장, 시총원)]"""
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", errors="replace") as f:
        rd = csv.DictReader(f)
        cols = {k.lower(): k for k in rd.fieldnames or []}
        need = ("code", "name", "market", "marcap", "date")
        miss = [k for k in need if k not in cols]
        if miss:
            raise RuntimeError("열 이름이 다릅니다: 없는 것 %s / 있는 것 %s" % (miss, rd.fieldnames))
        best, rows = "", []
        for r in rd:
            d = (r[cols["date"]] or "")[:10]
            if not d.startswith(str(y)) or d < best:
                continue
            if d > best:
                best, rows = d, []
            m = (r[cols["market"]] or "").upper()
            m = "KOSDAQ" if m.startswith("KOSDAQ") else "KOSPI" if m.startswith("KOSPI") else m
            try:
                cap = int(float(r[cols["marcap"]] or 0))
            except ValueError:
                cap = 0
            rows.append((str(r[cols["code"]]).zfill(6), r[cols["name"]], m, cap))
    # 시가총액 단위: 안내문엔 '백만원', 실제 파일은 '원'인 경우가 있다. 1위가 1천억보다 작으면 백만원으로 본다.
    if rows and max(r[3] for r in rows) < 10 ** 11:
        rows = [(c, n, m, cap * 10 ** 6) for c, n, m, cap in rows]
    return best, rows


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    years = [int(a) for a in args] or list(range(FIRST, LAST + 1))
    force = "--force" in sys.argv
    try:
        j = json.load(open(C.OUT, encoding="utf-8"))
    except Exception:                            # noqa: BLE001
        j = {"cols": {}}
    cols = j.setdefault("cols", {})
    done = 0
    for y in years:
        if str(y) in cols and not force:
            print("  그대로  %d (이미 있음)" % y)
            continue
        try:
            path = fetch(y)
            d, rows = year_end(path, y)
        except Exception as e:                   # noqa: BLE001
            print("  !! %d  %s" % (y, e))
            continue
        if not rows:
            print("  !! %d  그 해 자료가 없습니다" % y)
            continue
        col = C.column(date.fromisoformat(d), rows)
        col["src"] = "marcap"
        cols[str(y)] = col
        done += 1
        k = col["kospi"][:3]
        print("  %d  %s  코스피 %s · 코스닥 %d종목" % (y, d, " · ".join("%s %s조" % (r[1], format(r[2] // 10000, ",")) for r in k),
                                                    len(col["kosdaq"])))
        time.sleep(0.5)
    ig = open(".gitignore", encoding="utf-8").read() if os.path.exists(".gitignore") else ""
    if "/_marcap/" not in ig.split():
        open(".gitignore", "a", encoding="utf-8").write(("" if ig.endswith("\n") or not ig else "\n") + "/_marcap/\n")
    if done:
        os.makedirs("data", exist_ok=True)
        with open(C.OUT, "w", encoding="utf-8") as f:
            json.dump(j, f, ensure_ascii=False, separators=(",", ":"))
    print("\n%d개 해를 더했습니다 → %s (칸 %d개)" % (done, C.OUT, len(cols)))


if __name__ == "__main__":
    main()
