#!/usr/bin/env python3
"""리뷰 원장 승격 스크립트.

LLM 이 초안을 만들고, 이 스크립트가 원장(ledger.yaml)·fixture 에 쓰고 검사기로 검증한다.
원장 파일을 LLM 이 직접 편집하지 않는 이유: 검사기의 YAML 서브셋을 깨뜨리기 쉽다.

모드
  --list                      원장에 올라온 출처 URL 목록 (노션 대조용)
  --add <entries.json>        항목 추가. grep 항목은 fixture 위반 줄 필수. 추가 후 검사기로 검증
  --retire <id>               항목 제거 (노션에서 폐기된 것). 제거 이력은 ledger/retired.yaml 에 남김
  --recur <id>                재발 +1
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
LEDGER = PLUGIN_ROOT / "ledger" / "ledger.yaml"
FIXTURE = PLUGIN_ROOT / "ledger" / "fixtures" / "violations.diff"
RETIRED = PLUGIN_ROOT / "ledger" / "retired.yaml"
CHECKER = PLUGIN_ROOT / "skills" / "ledger-check" / "scripts" / "ledger_check.py"

sys.path.insert(0, str(CHECKER.parent))
from ledger_check import parse_ledger  # noqa: E402


# ───────────────────────── 원장 읽기 ─────────────────────────


def load_items() -> list[dict]:
    return parse_ledger(LEDGER.read_text(encoding="utf-8"))


def next_id(items: list[dict], kind: str) -> str:
    """grep 은 L-0xx, judgment 는 L-1xx."""
    prefix = 1 if kind == "grep" else 101
    ceiling = 100 if kind == "grep" else 200
    used = {int(i["id"].split("-")[1]) for i in items}
    candidate = prefix
    while candidate in used:
        candidate += 1
    if candidate >= ceiling:
        raise ValueError(f"{kind} id 범위 초과")

    return f"L-{candidate:03d}"


# ───────────────────────── 원장 쓰기 ─────────────────────────


def _quote(value: str) -> str:
    """검사기 서브셋에 맞춘 스칼라. `: ` 나 `#` 가 들어가면 작은따옴표로 감싼다."""
    if ": " in value or " #" in value or value.startswith(("'", '"', "[", "{")):
        return "'" + value.replace("'", "''") + "'"

    return value


def render_entry(entry: dict) -> str:
    v = entry["검증"]
    lines = [
        f"- id: {entry['id']}",
        f"  규칙: {_quote(entry['규칙'])}",
        f"  출처: {entry['출처']}",
        "  검증:",
        f"    type: {v['type']}",
    ]
    if v["type"] == "grep":
        lines.append(f"    scope: {v.get('scope', 'added')}")
        lines.append(f"    pattern: '{v['pattern']}'")
        if v.get("unless_previous_line"):
            lines.append(f"    unless_previous_line: '{v['unless_previous_line']}'")
        if v.get("glob"):
            lines.append(f"    glob: '{v['glob']}'")
        if v.get("exclude"):
            lines.append(f"    exclude: '{v['exclude']}'")
    else:
        lines.append("    판정 기준: >-")
        lines.append(f"      {v['판정 기준']}")
    lines.append(f"  중요도: {entry.get('중요도', '보통')}")
    lines.append(f"  재발: {entry.get('재발', 0)}")

    return "\n".join(lines) + "\n"


def append_entries(entries: list[dict]) -> None:
    """grep 은 grep 블록 끝에, judgment 는 파일 끝에 붙인다."""
    text = LEDGER.read_text(encoding="utf-8")
    grep_marker = "# ───────────────────────── judgment (리뷰어) ─────────────────────────"
    grep_entries = [e for e in entries if e["검증"]["type"] == "grep"]
    judgment_entries = [e for e in entries if e["검증"]["type"] != "grep"]

    if grep_entries:
        block = "".join("\n" + render_entry(e) for e in grep_entries)
        head, sep, tail = text.partition(grep_marker)
        text = head.rstrip("\n") + "\n" + block + "\n" + sep + tail if sep else text + block
    if judgment_entries:
        text = text.rstrip("\n") + "\n" + "".join("\n" + render_entry(e) for e in judgment_entries)

    LEDGER.write_text(text, encoding="utf-8")


def append_fixture(entry: dict) -> None:
    """grep 항목마다 fixture 에 파일 하나짜리 hunk 를 붙인다. 위반 줄은 entry['fixture'] 에서."""
    fixture = entry["fixture"]
    path = fixture["path"]
    lines = fixture["lines"]
    hunk = [
        f"diff --git a/{path} b/{path}",
        "new file mode 100644",
        "--- /dev/null",
        f"+++ b/{path}",
        f"@@ -0,0 +1,{len(lines)} @@",
        *[f"+{line}" for line in lines],
    ]
    text = FIXTURE.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(hunk) + "\n"
    FIXTURE.write_text(text, encoding="utf-8")


# ───────────────────────── 검증 ─────────────────────────


def run_checker() -> dict:
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--diff", str(FIXTURE), "--json", "--skip-deps"],
        capture_output=True, text=True,
    )
    if result.returncode == 2:
        raise RuntimeError(f"검사기 실행 불가: {result.stderr.strip()}")

    return json.loads(result.stdout)


def fail_ids(report: dict) -> set[str]:
    return {v["id"] for v in report["verdicts"] if v["status"] == "FAIL"}


# ───────────────────────── 모드 ─────────────────────────


def mode_list() -> int:
    for item in load_items():
        print(f"{item['id']}\t{item['검증']['type']}\t{item['출처']}")

    return 0


def mode_add(entries_path: Path) -> int:
    entries = json.loads(entries_path.read_text(encoding="utf-8"))
    items = load_items()
    existing_sources = {i["출처"] for i in items}

    for entry in entries:
        kind = entry["검증"]["type"]
        if kind not in ("grep", "judgment"):
            print(f"지원하지 않는 type: {kind}", file=sys.stderr)
            return 2
        if kind == "grep" and not entry.get("fixture"):
            print(f"grep 항목 '{entry['규칙']}' 에 fixture 가 없다. 위반 줄 없이는 올리지 않는다.", file=sys.stderr)
            return 2
        if entry["출처"] in existing_sources:
            print(f"이미 원장에 있는 출처: {entry['출처']}", file=sys.stderr)
            return 2
        if kind == "grep":
            try:
                re.compile(entry["검증"]["pattern"])
            except re.error as error:
                print(f"정규식 오류 ({entry['규칙']}): {error}", file=sys.stderr)
                return 2
        entry["id"] = next_id(items, kind)
        items.append(entry)

    before = fail_ids(run_checker())
    ledger_backup = LEDGER.read_text(encoding="utf-8")
    fixture_backup = FIXTURE.read_text(encoding="utf-8")

    append_entries(entries)
    for entry in entries:
        if entry["검증"]["type"] == "grep":
            append_fixture(entry)

    try:
        after_report = run_checker()
    except (RuntimeError, json.JSONDecodeError) as error:
        LEDGER.write_text(ledger_backup, encoding="utf-8")
        FIXTURE.write_text(fixture_backup, encoding="utf-8")
        print(f"검증 실패, 되돌림: {error}", file=sys.stderr)
        return 1

    after = fail_ids(after_report)
    expected_new_fails = {e["id"] for e in entries if e["검증"]["type"] == "grep"}
    missing = expected_new_fails - (after - before)
    if missing:
        LEDGER.write_text(ledger_backup, encoding="utf-8")
        FIXTURE.write_text(fixture_backup, encoding="utf-8")
        print(f"fixture 가 위반을 만들지 못한 항목: {', '.join(sorted(missing))}. 되돌림.", file=sys.stderr)
        return 1

    for entry in entries:
        print(f"추가: {entry['id']} [{entry['검증']['type']}] {entry['규칙']}")
    print(f"검사기 FAIL {len(before)} → {len(after)}")

    return 0


def mode_retire(item_id: str) -> int:
    text = LEDGER.read_text(encoding="utf-8")
    pattern = re.compile(rf"\n- id: {re.escape(item_id)}\n(?:  .*\n|    .*\n|      .*\n)*")
    match = pattern.search(text)
    if not match:
        print(f"원장에 없는 id: {item_id}", file=sys.stderr)
        return 2

    block = match.group(0)
    LEDGER.write_text(text.replace(block, "\n", 1), encoding="utf-8")
    retired = RETIRED.read_text(encoding="utf-8") if RETIRED.exists() else "# 폐기된 원장 항목. 왜 빠졌는지 남기기 위해 지우지 않는다.\n"
    RETIRED.write_text(retired.rstrip("\n") + f"\n\n# 폐기 {date.today().isoformat()}" + block, encoding="utf-8")
    print(f"폐기: {item_id} → ledger/retired.yaml")

    return 0


def mode_recur(item_id: str) -> int:
    text = LEDGER.read_text(encoding="utf-8")
    pattern = re.compile(rf"(- id: {re.escape(item_id)}\n(?:.*\n)*?  재발: )(\d+)")
    match = pattern.search(text)
    if not match:
        print(f"원장에 없는 id: {item_id}", file=sys.stderr)
        return 2

    count = int(match.group(2)) + 1
    LEDGER.write_text(text[: match.start(2)] + str(count) + text[match.end(2):], encoding="utf-8")
    print(f"{item_id} 재발: {count}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="리뷰 원장 승격 — 노션 적립층 → ledger.yaml 실행층")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true")
    group.add_argument("--add", type=Path, metavar="ENTRIES_JSON")
    group.add_argument("--retire", metavar="ID")
    group.add_argument("--recur", metavar="ID")
    args = parser.parse_args()

    if args.list:
        return mode_list()
    if args.add:
        return mode_add(args.add)
    if args.retire:
        return mode_retire(args.retire)

    return mode_recur(args.recur)


if __name__ == "__main__":
    sys.exit(main())
