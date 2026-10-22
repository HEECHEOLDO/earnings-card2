#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""감사보고서만 내는 비상장사 수집기 — 연간 실적  ->  data/unlisted/{회사코드}.json

  python3 collect_audit.py                   목록(audit_list.txt) 수집
  python3 collect_audit.py 우아한형제들 직방    이름(또는 8자리 회사코드)만
  python3 collect_audit.py --status          무엇이 얼마나 받아졌는지만 (호출 0회)
  python3 collect_audit.py --index           목록의 이름·분류·대표 서비스만 반영 (호출 0회)

이런 회사는 DART 재무 API(fnlttSinglAcntAll)에 숫자가 없다. 그래서 감사보고서
원문(document.xml)을 받아 손익계산서 표에서 매출·영업이익·순이익을 읽는다.
표를 읽는 방법은 probe_audit.py 와 같다 (32곳을 뉴스와 맞춰 본 그 방법).

  · 1년에 보고서 1개 → 연간만 있다. 분기 탭은 화면에서 숨겨진다.
  · 최근 10개 회계연도. 결산월이 12월이 아니면 '8월 결산' 처럼 카드에 적는다.
  · 연결감사보고서가 있으면 연결, 없으면 별도. 해마다 섞이면 '연결·별도'.
  · 다음 해 보고서의 전기(前期) 숫자로 검산한다. 1% 넘게 다르면 알려준다.
  · 사업보고서로 바꾼 회사(당근 등)는 사업보고서 원문도 같은 방법으로 읽는다.

결과는 비상장 실적 탭(data/unlisted/)에 같이 들어간다. 정기보고서를 내는
32곳(collect_unlisted.py)이 이미 받은 회사는 건너뛴다.

목록 다섯째 칸에 '별도' 를 적으면 연결이 있어도 별도로 받는다. 지주회사처럼
연결에 그룹 전체가 잡히는 회사용 (파리크라상: 연결은 SPC 그룹 5조, 별도가 파리바게뜨).

목록 한 줄에 회사코드를 + 로 여럿 적으면 합친다. 법인을 나눠 코드가 바뀐 회사용.
  01995325+00123456 | 파리크라상 | ...     (앞이 새 코드, 뒤가 옛 코드)

DART 하루 한도 2만 회 중 상장사 수집이 1만 8천 회를 쓴다. 비상장 두 수집기가
나머지를 나눠 쓴다: collect_unlisted.py 가 먼저 돌고 쓴 횟수를 남기면,
이 수집기는 --total(기본 1,500)에서 그만큼을 뺀 만큼만 쓴다.
한 번에 --minutes(기본 100)분까지만 돈다. 한 곳에 목록 2회 + 보고서 최대 10회. 처음 302곳을 다 받는 데 사나흘 걸린다.
그 뒤로는 --refresh-days(기본 14)마다 새 보고서가 있는지만 본다(2회).

키는 collect.py 와 같이 환경변수 DART_API_KEY 또는 key.txt 에서 읽는다.
"""
import os
import re
import sys
import time
from datetime import datetime

import collect as C
import collect_unlisted as U
import probe_audit as P

LIST = "audit_list.txt"
OUT = U.OUT
CHECKED = os.path.join(OUT, "_audit_checked.json")
FAILED = os.path.join(OUT, "_audit_failed.json")
CALLS = os.path.join(OUT, "_calls.json")          # collect_unlisted.py 가 남긴 오늘 호출 수
YEARS = 10
PER_COMPANY = 2 + YEARS + 2

log = U.log


# ------------------------------------------------------------ 목록

def load_list():
    out = []
    if not os.path.exists(LIST):
        log("!! %s 가 없습니다." % LIST)
        return out
    for line in open(LIST, encoding="utf-8"):
        line = line.split("#")[0].strip()
        if not line:
            continue
        p = [x.strip() for x in line.split("|")]
        codes = [c for c in p[0].split("+") if c]
        if not codes or not all(c.isdigit() and len(c) == 8 for c in codes):
            log("  ? 무시된 줄: %s" % line)
            continue
        brand = ", ".join(x.strip() for x in (p[3] if len(p) > 3 else "").split(",") if x.strip())
        out.append({"code": codes[0], "codes": codes,
                    "name": p[1] if len(p) > 1 and p[1] else codes[0],
                    "sector": p[2] if len(p) > 2 else "", "brand": brand,
                    "basis": p[4] if len(p) > 4 and p[4] in ("연결", "별도") else ""})
    return out


def owned_by_unlisted(code):
    """정기보고서 수집기(collect_unlisted.py)가 만든 파일이면 True — 건드리지 않는다"""
    d = U.jload(os.path.join(OUT, code + ".json"), None)
    return bool(d) and d.get("source") != "audit"


# ------------------------------------------------------------ 보고서 목록

def period_of(nm):
    """'연결감사보고서 (2025.12)' -> (2025, 12)"""
    m = re.search(r"\((\d{4})\.(\d{2})\)", nm)
    return (int(m.group(1)), int(m.group(2))) if m else None


def list_reports(codes, since):
    """회계연도별로 고를 수 있는 보고서들 {(년,월): [보고서, ...]}"""
    by = {}
    for code in codes:
        for ty, word in (("F", "감사보고서"), ("A", "사업보고서")):
            res = C.api_get("list.json", {"corp_code": code, "pblntf_ty": ty,
                                          "bgn_de": "%d0101" % since,
                                          "end_de": datetime.now().strftime("%Y%m%d"),
                                          "page_count": 100})
            if C.ABORT:
                return by
            if not (res and res.get("status") == "000"):
                continue
            for r in res.get("list", []):
                nm = r.get("report_nm", "")
                if word not in nm:
                    continue
                per = period_of(nm)
                if per:
                    r["_kind"] = ty
                    by.setdefault(per, []).append(r)
    return by


def choose(reps, want_cfs):
    """같은 회계연도 보고서 중 하나 — 기준(연결/별도)이 맞는 것, 정정 아닌 것, 늦게 낸 것"""
    def score(r):
        nm = r["report_nm"]
        cfs = "연결" in nm or r["_kind"] == "A"       # 사업보고서는 연결이 앞에 있다
        return (cfs == want_cfs, "기재정정" not in nm and "첨부" not in nm, r["rcept_dt"])
    return sorted(reps, key=score, reverse=True)[0]


# ------------------------------------------------------------ 표 읽기

def amounts(cells):
    """계정 줄에서 금액들 (주석 번호는 건너뛴다). [당기, 전기] 순서"""
    vals = []
    for c in cells[1:]:
        if c in ("", "-"):
            continue
        if re.fullmatch(r"\d{1,2}(,\d{1,2})+", c):
            continue
        v = P.num(c)
        if v is not None:
            vals.append((c, v))
    if len(vals) >= 3 and "," not in vals[0][0] and abs(vals[0][1]) < 100:
        vals = vals[1:]
    return [v for _, v in vals]


def pick2(rows, cands, loose):
    """(계정명, 당기, 전기) — 전기는 금액이 딱 둘일 때만 (아니면 None)"""
    names = {}
    for r in rows:
        if r:
            names.setdefault(P.acct(r[0]), r)
    hits = [(c, names[c]) for c in cands if c in names]
    if loose and not hits:
        for c in cands:
            hits += [(n, r) for n, r in names.items() if n.startswith(c)
                     and not any(w in n for w in ("귀속", "주당", "률", "법인세"))]
    for n, r in hits:
        vs = amounts(r)
        if vs:
            prev = P.signed(n, vs[1]) if len(vs) == 2 else None
            return n, P.signed(n, vs[0]), prev
    return None


def parse(doc):
    """probe_audit.parse_income 과 같은 순서로 찾되 전기 숫자와 연결 여부까지 돌려준다"""
    tabs = list(re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", doc, re.S | re.I))
    rowsets = [P.rows_of(m.group(1)) for m in tabs]

    def is_equity(rows):
        return any("자본금" in "".join(r[1:3]) for r in rows[:2] if r)

    for i, rows in enumerate(rowsets):
        rev = pick2(rows, P.REV, False)
        if not rev:
            continue
        op, ni = pick2(rows, P.OP, True), pick2(rows, P.NI, True)
        if not ni:
            for nxt in rowsets[i + 1:i + 3]:
                if is_equity(nxt):
                    break
                ni = pick2(nxt, P.NI, True)
                if not op:
                    op = pick2(nxt, P.OP, True)
                if ni:
                    break
        if not (op or ni):
            continue
        m = tabs[i]
        before = doc[max(0, m.start() - 1500):m.start()]
        u = P.unit_of(before + doc[m.start():m.start() + 400])
        cfs = bool(re.search(r"연결|종속기업", re.sub(r"<[^>]+>", "", before)[-400:]))

        def val(x, j):
            return None if (not x or x[j] is None) else x[j] * u
        cur = {"rev": val(rev, 1), "op": val(op, 1), "ni": val(ni, 1)}
        prev = {"rev": val(rev, 2), "op": val(op, 2), "ni": val(ni, 2)}
        return cur, prev, cfs
    return None, None, None


def sane(row):
    """말이 안 되는 숫자는 버린다 (다른 표를 잘못 읽은 경우)"""
    rev, op, ni = row.get("rev"), row.get("op"), row.get("ni")
    if rev is None or rev <= 0:
        return False
    if op is not None and abs(op) > rev * 3 and rev > 1e9:
        return False
    return True


# ------------------------------------------------------------ 한 회사

def collect_one(item, old):
    latest = datetime.now().year
    by = list_reports(item["codes"], latest - YEARS - 1)
    if C.ABORT:
        return None, "중단"
    if not by:
        return None, "감사보고서 없음"
    pers = sorted(by, reverse=True)
    # 기준: 최근 보고서에 연결이 있으면 연결로 맞춘다
    want_cfs = any("연결" in r["report_nm"] or r["_kind"] == "A" for r in by[pers[0]])
    if item.get("basis"):                     # 목록 다섯째 칸에 '별도' 라고 적은 회사
        want_cfs = item["basis"] == "연결"
    fy_month = pers[0][1]
    pers = [p for p in pers if p[1] == fy_month][:YEARS]   # 결산월을 바꾼 해는 뺀다

    old = old if (old and old.get("source") == "audit") else {}
    have = {a["p"]: a for a in old.get("annual", [])}
    srcs = dict(old.get("reports", {}))
    rows, prevs, kinds = {}, {}, {}
    for per in pers:
        y = per[0]
        r = choose(by[per], want_cfs)
        if y in have and srcs.get(str(y)) == r["rcept_no"]:
            rows[y] = {k: have[y].get(k) for k in ("rev", "op", "ni")}
            kinds[y] = have[y].get("_cfs", want_cfs)
            continue                          # 이미 읽은 보고서는 다시 받지 않는다
        if C._call_count + 1 > BUDGET:
            break
        doc = P.fetch_doc(r["rcept_no"])
        if C.ABORT:
            return None, "중단"
        cur, prev, cfs = parse(doc) if doc else (None, None, None)
        if not cur or not sane(cur):
            log("  - %d년 표를 못 읽음 (%s)" % (y, r["rcept_no"]))
            continue
        rows[y] = {k: C.eok(v) for k, v in cur.items()}
        prevs[y - 1] = {k: C.eok(v) for k, v in prev.items()}
        kinds[y] = cfs
        srcs[str(y)] = r["rcept_no"]
        log("  %d년  매출 %s억  영업이익 %s억  순이익 %s억  %s"
            % (y, f"{rows[y]['rev']:,.0f}",
               "-" if rows[y]["op"] is None else f"{rows[y]['op']:,.0f}",
               "-" if rows[y]["ni"] is None else f"{rows[y]['ni']:,.0f}",
               "연결" if cfs else "별도"))

    # 지난번에 전기 숫자로 채워 둔 해는 그대로 둔다 (그 보고서를 다시 받지 않았으므로)
    for y, a in have.items():
        if y not in rows and srcs.get(str(y), "").startswith("전기:"):
            rows[y] = {k: a.get(k) for k in ("rev", "op", "ni")}
            kinds[y] = a.get("_cfs", want_cfs)

    # 검산: 다음 해 보고서의 전기 숫자와 비교. 빈 해는 전기 숫자로 채운다.
    notes = []
    for y, pv in prevs.items():
        if pv.get("rev") is None:
            continue
        if y in rows:
            a, b = rows[y]["rev"], pv["rev"]
            if a and abs(a - b) / abs(a) > 0.01:
                notes.append("%d년 매출이 다음 해 보고서와 %.1f%% 다름(재작성)" % (y, abs(a - b) / abs(a) * 100))
        elif y >= latest - YEARS and sane(pv):
            rows[y] = dict(pv)
            kinds[y] = kinds.get(y + 1, want_cfs)
            srcs[str(y)] = "전기:" + srcs.get(str(y + 1), "")
    for n in notes:
        log("  ! " + n)
    if not rows:
        return None, "표를 못 읽음"

    years = sorted(rows)[-YEARS:]
    ks = {kinds[y] for y in years}
    basis = "연결·별도" if len(ks) > 1 else ("연결" if ks.pop() else "별도")
    if fy_month != 12:
        basis += " · %d월 결산" % fy_month
    annual = [{"p": y, "rev": rows[y]["rev"], "op": rows[y]["op"], "ni": rows[y]["ni"],
               "assets": None, "liab": None, "equity": None,
               "dps": None, "payout": None, "yield": None, "_cfs": kinds[y]} for y in years]
    return {
        "name": item["name"],
        "legal_name": item["name"],
        "code": item["code"],
        "market": "비상장",
        "sector": item["sector"],
        "brand": item.get("brand", ""),
        "basis": basis,
        "source": "audit",                    # 감사보고서 원문에서 읽은 파일
        "fy_end": fy_month,
        "updated": U.today(),
        "annual": annual,
        "quarterly": [],
        "reports": {str(y): srcs.get(str(y), "") for y in years},
    }, notes


# ------------------------------------------------------------ 실행

BUDGET = 0


def status(lst):
    checked, failed = U.jload(CHECKED, {}), U.jload(FAILED, {})
    have = other = 0
    for x in lst:
        d = U.jload(os.path.join(OUT, x["code"] + ".json"), None)
        if d and d.get("source") == "audit":
            have += 1
            a = d.get("annual") or []
            log("  %-16s %2d년 (%s~%s) %-10s 확인 %s" % (x["name"][:16], len(a),
                a[0]["p"] if a else "-", a[-1]["p"] if a else "-", d.get("basis", ""),
                checked.get(x["code"], "-")))
        elif d:
            other += 1
            log("  %-16s 정기보고서 수집기가 받음 (건너뜀)" % x["name"][:16])
        elif x["code"] in failed:
            log("  %-16s 실패 — %s" % (x["name"][:16], failed[x["code"]].get("reason")))
    log("\n목록 %d곳 · 받음 %d곳 · 정기보고서 쪽 %d곳 · 실패 %d곳 · 아직 %d곳"
        % (len(lst), have, other, len(failed), len(lst) - have - other - len(failed)))


def sync_meta(lst):
    n = 0
    for x in lst:
        path = os.path.join(OUT, x["code"] + ".json")
        d = U.jload(path, None)
        if not d or d.get("source") != "audit":
            continue
        new = dict(d, name=x["name"], sector=x["sector"], brand=x.get("brand", ""))
        if new != d:
            U.jsave(path, new, indent=1)
            n += 1
    return n


def main():
    global BUDGET
    lst = load_list()
    args = [a for i, a in enumerate(sys.argv[1:], 1)
            if not a.startswith("--") and sys.argv[i - 1] not in ("--total", "--budget", "--refresh-days", "--minutes")]
    if args:
        named = {x["name"]: x for x in lst}
        named.update({x["code"]: x for x in lst})
        lst = [named.get(a) or {"code": a, "codes": [a], "name": a, "sector": "", "brand": ""}
               for a in args if a in named or re.fullmatch(r"\d{8}", a)]
    if "--status" in sys.argv:
        status(lst)
        return
    if "--index" in sys.argv:
        n = sync_meta(load_list())
        log("이름·분류·대표 서비스 반영 %d곳 · 목록 총 %d곳 (API 0회)" % (n, U.rebuild_index()))
        return
    if not lst:
        return

    C.API_KEY = C.get_key()
    total = U.opt("--total", 1500)
    used = U.jload(CALLS, {})
    used = used.get("calls", 0) if used.get("date") == U.today() else 0
    BUDGET = U.opt("--budget", max(0, total - used))
    refresh = U.opt("--refresh-days", 14)
    force = "--force" in sys.argv or bool(args)
    os.makedirs(OUT, exist_ok=True)

    checked, failed = U.jload(CHECKED, {}), U.jload(FAILED, {})
    fresh, stale, skipped = [], [], 0
    for x in lst:
        if owned_by_unlisted(x["code"]):
            skipped += 1
            continue
        has = os.path.exists(os.path.join(OUT, x["code"] + ".json"))
        if not has and not force and x["code"] in failed \
                and U.age_days(failed[x["code"]].get("date", "")) < 30:
            continue                          # 실패한 곳은 한 달 뒤에 다시 본다
        if not has:
            fresh.append(x)
        else:
            a = U.age_days(checked.get(x["code"], ""))
            if force or a >= refresh:
                stale.append((a, x))
    stale.sort(key=lambda t: -t[0])
    todo = fresh + [x for _, x in stale]
    log("목록 %d곳 | 새로 %d | 갱신 %d | 정기보고서 쪽 %d | 예산 %d회 (비상장 정기 %d회 사용)"
        % (len(lst), len(fresh), len(stale), skipped, BUDGET, used))

    done = []
    t0, minutes = time.time(), U.opt("--minutes", 100)
    for x in todo:
        if time.time() - t0 > minutes * 60:
            log("\n>> %d분이 지나 여기서 멈춥니다 (작업 시간 제한). 다음 실행에서 이어갑니다." % minutes)
            break
        if C.ABORT:
            log("\n>> 중단: %s" % C.ABORT)
            break
        if C._call_count + PER_COMPANY > BUDGET:
            log("\n>> 예산 %d회에 닿아 여기서 멈춥니다. 다음 실행에서 이어갑니다." % BUDGET)
            break
        log("\n=== %s (%s) ===" % (x["name"], "+".join(x["codes"])))
        path = os.path.join(OUT, x["code"] + ".json")
        try:
            data, notes = collect_one(x, U.jload(path, None))
        except Exception as e:                # noqa: BLE001
            log("! 예외: %r" % e)
            failed[x["code"]] = {"name": x["name"], "reason": "예외 %s" % type(e).__name__,
                                 "date": U.today()}
            continue
        if not data:
            if C.ABORT:
                break
            failed[x["code"]] = {"name": x["name"], "reason": notes, "date": U.today()}
            done.append((x["name"], "실패", notes))
            continue
        failed.pop(x["code"], None)
        wrote = not (os.path.exists(path) and C.data_unchanged(path, data))
        if wrote:
            U.jsave(path, data, indent=1)
        checked[x["code"]] = U.today()
        a = data["annual"]
        done.append((x["name"], "정상" if wrote else "동일",
                     "%d년 (%d~%d) %s%s" % (len(a), a[0]["p"], a[-1]["p"], data["basis"],
                                         " · 확인 필요 %d" % len(notes) if notes else "")))

    U.jsave(CHECKED, checked, sort_keys=True, separators=(",", ":"))
    U.jsave(FAILED, failed, indent=1)
    if not C.ABORT:                           # 끝까지 돈 날을 남긴다 (받을 회사가 없던 날도)
        U.jsave(os.path.join(OUT, "_audit_run.json"),
                {"updated": U.today(), "done": len(done), "calls": C._call_count}, indent=1)
    sync_meta(load_list())
    n = U.rebuild_index()
    log("\n" + "=" * 50)
    for nm, st, note in done:
        log("  %-16s %-4s %s" % (nm[:16], st, note))
    log("이번 %d곳 · API %d회 · 비상장 탭 총 %d곳" % (len(done), C._call_count, n))


if __name__ == "__main__":
    main()
