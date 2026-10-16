#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""감사보고서만 내는 유명 비상장사의 실적을 뽑을 수 있는지 시험한다.  (파일은 안 바꾼다)

  python3 probe_audit.py                  기사가 많은 32곳 (기본)
  python3 probe_audit.py 쿠팡 직방         이름을 골라서
  python3 probe_audit.py --all            audit_list.txt 302곳 전체 (호출 600회 이상 — 하루 한도 주의)
  python3 probe_audit.py --dump 접수번호…   못 읽은 문서의 표를 audit_dump.txt 로 저장

배달의민족·쿠팡·올리브영 같은 회사는 감사보고서만 낸다. DART 재무제표 API 는
감사보고서 숫자를 주지 않아서, 문서를 받아 손익계산서 표를 직접 읽는다.
회사마다 표 모양이 조금씩 달라, 정말 정확히 뽑히는지 먼저 확인한다.

회사마다 호출 3회: 감사보고서·사업보고서 찾기 2회 + 문서 받기 1회.
연결감사보고서가 있으면 연결을, 없으면 감사보고서를 읽는다. 감사보고서가 따로
없으면(당근·빗썸처럼 사업보고서를 내는 회사) 사업보고서 문서를 읽는다.

명단은 audit_list.txt (회사코드 | 이름 | 분류 | 대표 서비스).
키는 collect.py 와 같이 DART_API_KEY 또는 key.txt 에서 읽는다.
"""
import html
import io
import os
import re
import sys
import zipfile

import collect as C

LIST = "audit_list.txt"
# 기사로 실적이 잘 알려진 곳 — 뽑은 숫자를 기사와 대조하기 쉽다
SAMPLE = ["우아한형제들", "쿠팡", "씨제이올리브영", "아성다이소", "에스씨케이컴퍼니", "이케아코리아",
          "코스트코코리아", "애플코리아", "구글코리아", "넷플릭스서비시스코리아", "샤넬코리아",
          "루이비통코리아", "에르메스코리아", "에프알엘코리아", "나이키코리아", "한국맥도날드",
          "비케이알", "파리크라상", "다이닝브랜즈그룹", "앤하우스", "메르세데스벤츠코리아",
          "비엠더블유코리아", "삼성디스플레이", "동서식품", "오비맥주", "로쏘", "직방",
          "버킷플레이스", "당근마켓", "빗썸", "한국지엠", "넥슨코리아"]


def load_list():
    out = []
    for line in open(LIST, encoding="utf-8"):
        line = line.split("#")[0].strip()
        if not line:
            continue
        p = [x.strip() for x in line.split("|")]
        if p[0].isdigit() and len(p[0]) == 8:
            out.append({"code": p[0], "name": p[1], "brand": p[3] if len(p) > 3 else ""})
    return out


REV = ["매출액", "매출", "수익(매출액)", "영업수익", "매출및지분법손익", "수익"]
OP = ["영업이익", "영업이익(손실)", "영업손실", "영업손익", "영업손실(이익)"]
NI = ["당기순이익", "당기순이익(손실)", "당기순손실", "당기순손익", "당기순손실(이익)",
      "연결당기순이익", "연결당기순이익(손실)", "연결당기순손실", "연결당기순손익",
      "당기연결순이익", "당기연결순이익(손실)", "당기연결순손실", "당기연결순손익"]


def norm(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("　", " ")
    return re.sub(r"\s+", "", s)


def acct(s):
    """계정명을 맞춘다  'Ⅰ.매출액(주석2,17,20)' 'I.매출액(주3)' '1.매출액' -> '매출액'"""
    s = re.sub(r"^[\dIVXⅠ-Ⅻ]+[.)]", "", s)
    return re.sub(r"\(주석?[\d,·\s및]*\)$", "", s)


def num(tok):
    t = tok.replace(" ", "")
    neg = t.startswith("(") and t.endswith(")") or t.startswith("-") or t.startswith("△")
    t = t.strip("()-△")
    if not re.fullmatch(r"\d{1,3}(,\d{3})*|\d+", t):
        return None
    return -float(t.replace(",", "")) if neg else float(t.replace(",", ""))


def rows_of(table):
    out = []
    for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", table, re.S | re.I):
        cells = [norm(c) for c in re.findall(r"<T[DEUH][^>]*>(.*?)</T[DEUH]>", tr, re.S | re.I)]
        if cells:
            out.append(cells)
    return out


def first_amount(cells):
    """계정명 다음 칸들에서 당기 금액을 고른다. 주석 번호(4 / 4,25)는 건너뛴다."""
    toks = [c for c in cells[1:] if c not in ("", "-")]
    vals = []
    for c in toks:
        if re.fullmatch(r"\d{1,2}(,\d{1,2})+", c):        # 주석 '4,25'
            continue
        v = num(c)
        if v is not None:
            vals.append((c, v))
    if len(vals) >= 3 and "," not in vals[0][0] and abs(vals[0][1]) < 100:
        vals = vals[1:]                                   # 맨 앞 작은 정수는 주석
    return vals[0][1] if vals else None


def unit_of(text):
    m = re.search(r"단위\s*[:：]?\s*(백만원|천원|원)", re.sub(r"<[^>]+>", "", text))
    return {"원": 1, "천원": 1e3, "백만원": 1e6}.get(m.group(1), 1) if m else 1


def pick(rows, cands, loose=False):
    names = {}
    for r in rows:
        if r:
            names.setdefault(acct(r[0]), r)
    for c in cands:
        if c in names:
            v = first_amount(names[c])
            if v is not None:
                return c, signed(c, v)
    # 정확히 같은 이름이 없으면 앞부분으로 찾는다 ('당기순이익(손실)(주석 28)' 등)
    # 매출에는 쓰지 않는다 ('매출채권' '매출원가' 가 걸린다)
    for c in (cands if loose else []):
        for n, r in names.items():
            if n.startswith(c) and not any(w in n for w in ("귀속", "주당", "률", "법인세")):
                v = first_amount(r)
                if v is not None:
                    return n, signed(n, v)
    return None


def signed(name, v):
    """'영업손실' '당기순손실' '영업손실(이익)' 처럼 손실이 앞에 오는 계정은
    양수로 적혀 있어도 손실이다 → 음수로 바꾼다. (괄호 금액은 num 이 이미 음수)"""
    i, j = name.find("손실"), name.find("이익")
    if i >= 0 and (j < 0 or i < j) and v > 0:
        return -v
    return v


def parse_income(doc):
    """매출이 있는 첫 손익 표를 찾는다. 순이익이 그 표에 없으면(표가 길어 둘로
    나뉜 문서) 바로 뒤 두 표에서 찾는다. 자본변동표(자본금 칸이 있는 표)는 건너뛴다."""
    tabs = list(re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", doc, re.S | re.I))
    rowsets = [rows_of(m.group(1)) for m in tabs]

    def is_equity(rows):
        return any("자본금" in "".join(r[1:3]) for r in rows[:2] if r)

    for i, rows in enumerate(rowsets):
        rev = pick(rows, REV)
        if not rev:
            continue
        op, ni = pick(rows, OP, True), pick(rows, NI, True)
        if not ni:
            for nxt in rowsets[i + 1:i + 3]:
                if is_equity(nxt):
                    break
                ni = pick(nxt, NI, True)
                if not op:
                    op = pick(nxt, OP, True)
                if ni:
                    break
        if not (op or ni):
            continue                          # 매출만 있는 표(주석의 매출 내역 등)
        m = tabs[i]
        u = unit_of(doc[max(0, m.start() - 1500):m.start() + 400])
        got = {"rev": rev}
        if op:
            got["op"] = op
        if ni:
            got["ni"] = ni
        return {k: (n, v * u) for k, (n, v) in got.items()}, u
    return None, None


def same_name_codes(code):
    """corpCode.xml 에서 같은 이름의 다른 비상장 회사코드들 (최근 수정 순)"""
    p = os.path.join(".cache", "corpCode.xml")
    if not os.path.exists(p):
        return []
    import xml.etree.ElementTree as ET
    k = lambda s: re.sub(r"[\s·.,()\-&]|주식회사|\(주\)|㈜", "", s)
    rows = [(n.findtext("corp_name") or "", n.findtext("corp_code") or "",
             n.findtext("stock_code") or "", n.findtext("modify_date") or "")
            for n in ET.parse(p).getroot().iter("list")]
    me = [r for r in rows if r[1] == code]
    if not me:
        return []
    same = [r for r in rows if k(r[0]) == k(me[0][0]) and r[1] != code and not r[2].strip()]
    return [r[1] for r in sorted(same, key=lambda r: r[3], reverse=True)]


def find_report(corp_code, retry=True):
    """감사보고서와 사업보고서를 모두 보고 가장 최근 회계연도의 것을 고른다.
    같은 연도에 연결이 있으면 연결. (당근처럼 감사보고서를 내다 사업보고서로
    바꾼 회사도 최신 숫자를 읽게)"""
    cand = []
    for ty, word in (("F", "감사보고서"), ("A", "사업보고서")):
        res = C.api_get("list.json", {"corp_code": corp_code, "pblntf_ty": ty,
                                      "bgn_de": "20240101", "end_de": "20261231", "page_count": 100})
        if res and res.get("status") == "000":
            cand += [r for r in res.get("list", []) if word in r.get("report_nm", "")
                     and "기재정정" not in r.get("report_nm", "")]
    if not cand:
        if retry:
            for other in same_name_codes(corp_code)[:3]:
                r = find_report(other, retry=False)
                if r:
                    r["other_code"] = other
                    return r
        return None

    def period(r):                           # '감사보고서 (2025.12)' -> '2025.12'
        m = re.search(r"\((\d{4}\.\d{2})\)", r["report_nm"])
        return m.group(1) if m else r["rcept_dt"][:4]
    cand.sort(key=lambda r: (period(r), "연결" in r["report_nm"], r["rcept_dt"]), reverse=True)
    return cand[0]


def fetch_doc(rcept_no):
    blob = C.api_get("document.xml", {"rcept_no": rcept_no}, raw=True)
    if not blob or blob[:2] != b"PK":
        return None
    texts = []
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for n in z.namelist():
            raw = z.read(n)
            for enc in ("utf-8", "euc-kr", "cp949"):
                try:
                    texts.append(raw.decode(enc))
                    break
                except UnicodeDecodeError:
                    continue
    return "\n".join(texts)


def eok(v):
    return "{:,.0f}억".format(v / 1e8)


def dump(rcepts):
    """못 읽은 문서에서 손익계산서로 보이는 표를 audit_dump.txt 로 저장한다 (문서 1개당 호출 1회)."""
    keys = ("매출", "영업", "당기순", "수익", "손익")
    out = []
    for rc in rcepts:
        doc = fetch_doc(rc)
        out.append("=" * 70 + "\n접수번호 %s  (%s)" % (rc, "문서 없음" if not doc else "%d자" % len(doc)))
        if not doc:
            continue
        tabs = list(re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", doc, re.S | re.I))
        out.append("표 %d개" % len(tabs))
        shown = 0
        for i, m in enumerate(tabs):
            rows = rows_of(m.group(1))
            firsts = "".join(r[0] for r in rows if r)
            if sum(k in firsts for k in keys) < 2:
                continue
            ctx = re.sub(r"<[^>]+>", " ", doc[max(0, m.start() - 300):m.start()])
            out.append("\n--- 표 #%d  (앞 글: %s)" % (i, re.sub(r"\s+", " ", ctx)[-120:]))
            for r in rows[:90]:
                out.append(" | ".join(r))
            shown += 1
            if shown >= 3:
                break
        if not shown:
            # 표가 TABLE 태그가 아니거나 다른 모양일 때 — 원문 일부를 보여준다
            i = doc.find("매출")
            out.append("손익 표를 못 찾음. '매출' 주변 원문:")
            out.append(doc[max(0, i - 600):i + 1500] if i >= 0 else doc[:2000])
    open("audit_dump.txt", "w", encoding="utf-8").write("\n".join(out))
    print("audit_dump.txt 저장 (문서 %d개, API %d회)" % (len(rcepts), C._call_count))


def main():
    if "--dump" in sys.argv:
        C.API_KEY = C.get_key()
        dump([a for a in sys.argv[1:] if a.isdigit()])
        return
    if not os.path.exists(LIST):
        print("!! %s 가 없습니다." % LIST)
        sys.exit(1)
    allx = load_list()
    want = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--all" in sys.argv:
        pick = allx
    else:
        names = want or SAMPLE
        pick = [x for x in allx if x["name"] in names]
        # 8자리 회사코드를 직접 넣으면 목록에 없어도 찾아본다
        pick += [{"code": a, "name": a, "brand": "(코드 직접)"} for a in names
                 if re.fullmatch(r"\d{8}", a)]
    C.API_KEY = C.get_key()
    ok = 0
    print("%-16s %-14s %-24s %10s %10s %10s" % ("법인", "서비스", "보고서", "매출", "영업이익", "순이익"))
    for x in pick:
        rep = find_report(x["code"])
        if C.ABORT:
            print("!! 중단: %s" % C.ABORT)
            break
        if not rep:
            print("%-16s %-14s 최근 감사보고서·사업보고서 없음" % (x["name"][:16], x["brand"][:14]))
            continue
        doc = fetch_doc(rep["rcept_no"])
        got, unit = parse_income(doc) if doc else (None, None)
        title = rep["report_nm"].replace(" ", "")[-22:]
        if rep.get("other_code"):
            title = (title + "*")[-22:]
            print("   (%s: 회사코드 %s → %s 로 찾음)" % (x["name"], x["code"], rep["other_code"]))
        if got:
            ok += 1
            print("%-16s %-14s %-24s %10s %10s %10s"
                  % (x["name"][:16], x["brand"][:14], title, eok(got["rev"][1]),
                     eok(got["op"][1]) if "op" in got else "-",
                     eok(got["ni"][1]) if "ni" in got else "-"))
        else:
            print("%-16s %-14s %-24s 손익계산서를 못 읽음 (접수번호 %s)"
                  % (x["name"][:16], x["brand"][:14], title, rep["rcept_no"]))
    print("\n숫자를 뽑은 곳 %d / %d  · API %d회" % (ok, len(pick), C._call_count))


if __name__ == "__main__":
    main()
