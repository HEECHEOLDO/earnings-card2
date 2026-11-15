#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""XBRL 원본(인스턴스)을 차원(부문·제품 축)까지 읽는 작은 도구 — 돈의 흐름 카드의 '매출 종류'·'비용 세부'용.
contexts: {id: {"start","end","dims":[(축, 멤버)]}}, facts: [(이름, context, 값)], labels: {요소: 이름표}"""
import io
import re
import zipfile


def parse(text):
    ctx = {}
    for m in re.finditer(r'<(?:\w+:)?context\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</(?:\w+:)?context>', text, re.S):
        body = m.group(2)
        a = re.search(r"<(?:\w+:)?startDate>\s*([\d-]+)", body)
        b = re.search(r"<(?:\w+:)?endDate>\s*([\d-]+)", body)
        if not (a and b):
            continue
        dims = re.findall(r'<(?:\w+:)?explicitMember[^>]*dimension="([^"]+)"[^>]*>\s*([^<\s]+)\s*<', body)
        ctx[m.group(1)] = {"start": a.group(1), "end": b.group(1), "dims": dims}
    facts = []
    for m in re.finditer(r'<([\w-]+:[\w-]+)\b([^>]*\bcontextRef="([^"]+)"[^>]*)>([^<]*)</\1>', text):
        name, attrs, c, val = m.group(1), m.group(2), m.group(3), m.group(4).strip()
        if c not in ctx or "unitRef" not in attrs:
            continue
        try:
            v = float(val)
        except ValueError:
            continue
        sc = re.search(r'\bscale="(-?\d+)"', attrs)            # iXBRL 이면 배율
        if sc:
            v *= 10 ** int(sc.group(1))
        if re.search(r'\bsign="-"', attrs):
            v = -v
        facts.append((name, c, v))
    return ctx, facts


def labels(text):
    """라벨 링크베이스 → {요소 이름(접두사:이름 또는 이름): 표준 라벨}"""
    loc = {}
    for m in re.finditer(r'<(?:\w+:)?loc\b[^>]*xlink:href="[^"#]*#([^"]+)"[^>]*xlink:label="([^"]+)"', text):
        loc[m.group(2)] = m.group(1)
    for m in re.finditer(r'<(?:\w+:)?loc\b[^>]*xlink:label="([^"]+)"[^>]*xlink:href="[^"#]*#([^"]+)"', text):
        loc[m.group(1)] = m.group(2)
    lab = {}
    for m in re.finditer(r'<(?:\w+:)?label\b([^>]*)>([^<]*)</(?:\w+:)?label>', text):
        attrs, val = m.group(1), m.group(2).strip()
        k = re.search(r'xlink:label="([^"]+)"', attrs)
        role = re.search(r'xlink:role="([^"]+)"', attrs)
        if not k or (role and not role.group(1).endswith("/label")):
            continue
        lab[k.group(1)] = val
    out = {}
    for m in re.finditer(r'<(?:\w+:)?labelArc\b[^>]*xlink:from="([^"]+)"[^>]*xlink:to="([^"]+)"', text):
        el = loc.get(m.group(1))
        if el and m.group(2) in lab and el not in out:
            out[el] = lab[m.group(2)]
    # 'ifrs-full_Revenue' → 'ifrs-full:Revenue' 꼴로도
    return {**out, **{k.replace("_", ":", 1): v for k, v in out.items()}}


def unzip(blob):
    z = zipfile.ZipFile(io.BytesIO(blob))
    return {n: z.read(n).decode("utf-8", "replace") for n in z.namelist()}


def calc(text):
    """계산 링크베이스 → {부모 요소: [자식 요소들]} (요소 이름은 'prefix:Name')"""
    loc = {}
    for m in re.finditer(r'<(?:\w+:)?loc\b([^>]*)/?>', text):
        a = m.group(1)
        h = re.search(r'xlink:href="[^"#]*#([^"]+)"', a)
        l = re.search(r'xlink:label="([^"]+)"', a)
        if h and l:
            loc[l.group(1)] = h.group(1).replace("_", ":", 1)
    out = {}
    for m in re.finditer(r'<(?:\w+:)?calculationArc\b([^>]*)/?>', text):
        a = m.group(1)
        f = re.search(r'xlink:from="([^"]+)"', a)
        t = re.search(r'xlink:to="([^"]+)"', a)
        w = re.search(r'weight="(-?[\d.]+)"', a)
        if f and t and f.group(1) in loc and t.group(1) in loc:
            out.setdefault(loc[f.group(1)], [])
            c = (loc[t.group(1)], float(w.group(1)) if w else 1.0)
            if c not in out[loc[f.group(1)]]:
                out[loc[f.group(1)]].append(c)
    return out
