#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""자동 갱신 워크플로에 '금융주 보충' 단계를 끼워 넣는다.

  python3 patch_workflow.py --dry    어디에 들어가는지 보기만
  python3 patch_workflow.py          실제로 넣기

왜 필요한가
-----------
collect_anchor.py 는 돌 때마다 data/anchor.json 을 통째로 새로 쓴다.
collect_anchor_extra.py 로 보태 넣은 금융주(KB금융·삼성생명 등)는 그때
전부 사라진다. 그래서 워크플로 안에서도 collect_anchor.py 바로 다음에
보충이 따라붙어야 한다.

YAML 은 들여쓰기 한 칸에 망가지므로, 앞 단계의 들여쓰기를 그대로 읽어
맞춘다. 몇 번을 돌려도 결과가 같다.
"""

import glob
import os
import re
import sys

STEP_NAME = "금융주 보충 (은행·보험 — 실적 수집에서 빠진 종목)"
STEP_RUN = "python3 collect_anchor_extra.py || true"


def find_files():
    """collect_anchor.py 를 돌리는 워크플로를 모두 찾는다."""
    out = []
    for p in sorted(glob.glob(".github/workflows/*.yml") +
                    glob.glob(".github/workflows/*.yaml")):
        s = open(p, encoding="utf-8").read()
        if re.search(r"collect_anchor\.py", s):
            out.append(p)
    return out


def patch(path, dry):
    lines = open(path, encoding="utf-8").read().split("\n")

    if any("collect_anchor_extra.py" in ln for ln in lines):
        print("  그대로  %-32s 이미 들어 있습니다" % path)
        return False

    # collect_anchor.py 를 '실행'하는 줄.
    # 주석에도 파일 이름이 적혀 있다(설명이나 안전장치 메모). 주석을 집으면
    # 그 위에 단계가 없어 그대로 건너뛰므로, 주석과 run 줄을 가려낸다.
    hit = None
    for i, ln in enumerate(lines):
        t = ln.strip()
        if t.startswith("#"):
            continue
        if "#" in ln:                          # 줄 끝 주석은 떼고 본다
            ln = ln.split("#", 1)[0]
        if "collect_anchor.py" in ln and "collect_anchor_extra" not in ln:
            hit = i
            break
    if hit is None:
        print("  !! %-32s collect_anchor.py 를 실행하는 줄이 없습니다 (주석만 있음)" % path)
        return False

    # 그 줄이 속한 단계의 시작('- name:' 또는 '- run:')을 거슬러 찾는다
    start = None
    for i in range(hit, -1, -1):
        m = re.match(r"^(\s*)-\s", lines[i])
        if m:
            start = i
            indent = m.group(1)
            break
    if start is None:
        print("  !! %-32s 단계의 시작('- ')을 못 찾았습니다" % path)
        return False

    # 그 단계의 끝 = 같은 들여쓰기로 '-' 가 다시 나오거나, 더 바깥으로 나갈 때
    end = len(lines)
    for i in range(start + 1, len(lines)):
        ln = lines[i]
        if not ln.strip():
            continue
        cur = len(ln) - len(ln.lstrip())
        if cur < len(indent):
            end = i
            break
        if cur == len(indent) and ln.lstrip().startswith("- "):
            end = i
            break
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1                               # 빈 줄 앞에 넣는다

    inner = indent + "  "                      # 'name:' 들여쓰기
    block = ["%s- name: %s" % (indent, STEP_NAME),
             "%srun: %s" % (inner, STEP_RUN)]
    if end > 0 and lines[end - 1].strip():     # 앞 단계와 한 줄 띄운다
        block = [""] + block

    print("  넣을 곳  %s  (%d번째 줄 뒤)" % (path, end))
    print("  ─ 앞 단계 ─")
    for ln in lines[start:end]:
        print("    " + ln)
    print("  ─ 새 단계 ─")
    for ln in block:
        print("  + " + ln)

    if dry:
        return True

    out = lines[:end] + block + lines[end:]
    open(path, "w", encoding="utf-8").write("\n".join(out))
    print("  고침    %s" % path)
    return True


def check(path):
    """pyyaml 이 있으면 진짜로 읽어 본다. 없으면 건너뛴다."""
    try:
        import yaml                            # noqa: F401
    except ImportError:
        print("  (pyyaml 이 없어 문법 확인은 건너뜁니다 — pip install pyyaml)")
        return True
    import yaml
    try:
        d = yaml.safe_load(open(path, encoding="utf-8"))
    except Exception as e:                     # noqa: BLE001
        print("  !! %s YAML 이 깨졌습니다: %s" % (path, e))
        return False
    steps = []
    for job in (d.get("jobs") or {}).values():
        steps += [s.get("name") or s.get("uses") or s.get("run", "")[:40]
                  for s in (job.get("steps") or [])]
    print("  확인 OK  단계 %d개: %s" % (len(steps), " / ".join(str(x)[:22] for x in steps)))
    return True


def main():
    dry = "--dry" in sys.argv
    if not os.path.isdir(".github/workflows"):
        print("!! .github/workflows 폴더가 없습니다. fincard 폴더에서 실행하세요.")
        return
    files = find_files()
    if not files:
        print("!! collect_anchor.py 를 돌리는 워크플로를 찾지 못했습니다.")
        print("   .github/workflows 안의 파일 이름을 알려주세요:")
        for p in sorted(glob.glob(".github/workflows/*")):
            print("     " + os.path.basename(p))
        return

    print("대상 %d개\n" % len(files))
    done = 0
    for p in files:
        if patch(p, dry):
            done += 1
        if not dry:
            check(p)
        print()

    if dry:
        print("--dry 라 파일은 건드리지 않았습니다.")
    else:
        print("바꾼 워크플로 %d개" % done)


if __name__ == "__main__":
    main()
