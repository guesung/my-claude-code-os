#!/usr/bin/env python3
"""리뷰 원장 검사기.

ledger/ledger.yaml 의 `type: grep` 항목을 diff 에 실행해 항목별 PASS/FAIL 을 판정한다.
판정만 한다. 고치지 않는다.

외부 의존 없음 — pyyaml 이 없는 환경에서도 돌도록 원장 스키마에 맞춘 최소 YAML 파서를 내장한다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LEDGER = PLUGIN_ROOT / "ledger" / "ledger.yaml"
DEFAULT_DEPENDENCIES = PLUGIN_ROOT / "dependencies.md"
GLOBAL_SKILL_ROOT = Path.home() / ".claude" / "skills" / "guesung"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_UNAVAILABLE = 2


# ───────────────────────── 원장 파싱 ─────────────────────────


def parse_ledger(text: str) -> list[dict]:
    """원장 YAML 서브셋 파서.

    지원 범위: 최상위 리스트, 항목은 2단 매핑(`검증:` 아래 한 단계), 값은 스칼라 또는 `>-` 블록.
    원장 헤더에 이 제약을 명시해 두었다. 그 밖의 YAML 문법은 지원하지 않는다.
    """
    items: list[dict] = []
    current: dict | None = None
    nested_key: str | None = None
    block_target: tuple[dict, str] | None = None
    block_indent = 0
    block_lines: list[str] = []

    def flush_block() -> None:
        nonlocal block_target, block_lines
        if block_target is not None:
            block_target[0][block_target[1]] = " ".join(line.strip() for line in block_lines)
        block_target = None
        block_lines = []

    for raw in text.splitlines():
        if block_target is not None:
            indent = len(raw) - len(raw.lstrip(" "))
            if raw.strip() and indent >= block_indent:
                block_lines.append(raw)
                continue
            flush_block()

        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip(" "))
        if stripped.startswith("- "):
            current = {}
            items.append(current)
            nested_key = None
            stripped = stripped[2:]
            indent += 2

        if current is None:
            raise ValueError(f"리스트 항목 밖의 줄: {raw!r}")

        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()

        if value == "":
            nested_key = key
            current[key] = {}
            continue

        target = current[nested_key] if indent > 2 and nested_key else current
        if value == ">-":
            block_target = (target, key)
            block_indent = indent + 1
            block_lines = []
            continue

        target[key] = _unquote(value)

    flush_block()
    return items


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]

    return value


# ───────────────────────── diff 파싱 ─────────────────────────


@dataclass
class DiffFile:
    path: str
    added_lines: list[tuple[int, str]] = field(default_factory=list)


def parse_diff(text: str) -> list[DiffFile]:
    """unified diff 에서 파일별 추가 라인(번호, 내용)만 뽑는다."""
    files: list[DiffFile] = []
    current: DiffFile | None = None
    new_line_number = 0

    for raw in text.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            current = DiffFile(path=path)
            if path != "/dev/null":
                files.append(current)
            continue

        if current is None:
            continue

        hunk = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
        if hunk:
            new_line_number = int(hunk.group(1))
            continue

        if raw.startswith("+"):
            current.added_lines.append((new_line_number, raw[1:]))
            new_line_number += 1
        elif raw.startswith("-") or raw.startswith("\\"):
            continue
        else:
            new_line_number += 1

    return files


def read_diff_from_git(base: str | None) -> str:
    """base 이후 커밋 + 워킹트리 변경분. base 미지정 시 origin/main → main → master 순으로 찾는다."""
    if base is None:
        for candidate in ("origin/main", "main", "master"):
            if subprocess.run(["git", "rev-parse", "--verify", "--quiet", candidate], capture_output=True).returncode == 0:
                base = candidate
                break
    if base is None:
        raise RuntimeError("base 브랜치를 찾지 못했다. --base 로 지정하라.")

    merge_base = subprocess.run(["git", "merge-base", base, "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    result = subprocess.run(["git", "diff", merge_base], capture_output=True, text=True, check=True)

    return result.stdout


# ───────────────────────── 의존 확인 ─────────────────────────


def missing_global_skills(dependencies_path: Path) -> list[str]:
    """dependencies.md 에서 상태가 '있음'인 전역 스킬이 실제로 존재하는지 본다."""
    if not dependencies_path.exists():
        return []

    missing: list[str] = []
    for line in dependencies_path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\|\s*`/guesung:([\w-]+)`\s*\|.*\|\s*있음\s*\|$", line)
        if not match:
            continue
        name = match.group(1)
        as_command = GLOBAL_SKILL_ROOT / "commands" / f"{name}.md"
        as_skill = GLOBAL_SKILL_ROOT / "skills" / name / "SKILL.md"
        if not as_command.exists() and not as_skill.exists():
            missing.append(name)

    return missing


# ───────────────────────── 판정 ─────────────────────────


@dataclass
class Finding:
    path: str
    line: int
    content: str


@dataclass
class Verdict:
    id: str
    rule: str
    status: str  # PASS | FAIL | SKIP | DELEGATED
    findings: list[Finding] = field(default_factory=list)


def check_item(item: dict, files: list[DiffFile]) -> Verdict:
    verification = item["검증"]
    if verification.get("type") != "grep":
        return Verdict(id=item["id"], rule=item["규칙"], status="DELEGATED")

    pattern = re.compile(verification["pattern"])
    scope = verification.get("scope", "added")
    glob = verification.get("glob")
    exclude = verification.get("exclude")
    unless_previous = verification.get("unless_previous_line")
    unless_previous_pattern = re.compile(unless_previous) if unless_previous else None

    targets = [f for f in files if _matches_glob(f.path, glob) and not _matches_glob(f.path, exclude, default=False)]
    if not targets:
        return Verdict(id=item["id"], rule=item["규칙"], status="SKIP")

    findings: list[Finding] = []
    for diff_file in targets:
        if scope == "filename":
            if pattern.search(diff_file.path):
                findings.append(Finding(path=diff_file.path, line=0, content=diff_file.path))
            continue

        previous_content: str | None = None
        previous_number: int | None = None
        for number, content in diff_file.added_lines:
            is_consecutive = previous_number is not None and number == previous_number + 1
            if pattern.search(content):
                exempt = (
                    unless_previous_pattern is not None
                    and is_consecutive
                    and previous_content is not None
                    and unless_previous_pattern.search(previous_content)
                )
                if not exempt:
                    findings.append(Finding(path=diff_file.path, line=number, content=content.strip()))
            previous_content = content
            previous_number = number

    status = "FAIL" if findings else "PASS"

    return Verdict(id=item["id"], rule=item["규칙"], status=status, findings=findings)


def _matches_glob(path: str, glob: str | None, default: bool = True) -> bool:
    if not glob:
        return default

    # fnmatch 는 `{a,b}` 를 모르므로 직접 펼친다. `**/` 는 경로 깊이 무관으로 취급한다.
    alternatives = re.match(r"^(.*)\{([^}]*)\}(.*)$", glob)
    globs = [f"{alternatives.group(1)}{ext}{alternatives.group(3)}" for ext in alternatives.group(2).split(",")] if alternatives else [glob]
    for candidate in globs:
        stripped = candidate[3:] if candidate.startswith("**/") else candidate
        if fnmatch(path, candidate) or fnmatch(path, stripped) or fnmatch(os.path.basename(path), stripped):
            return True

    return False


# ───────────────────────── 출력 ─────────────────────────


def render_table(verdicts: list[Verdict]) -> str:
    lines = ["| id | 판정 | 규칙 | 위치 |", "|---|---|---|---|"]
    for verdict in verdicts:
        if verdict.status == "FAIL":
            location = "<br>".join(f"`{f.path}:{f.line}` {f.content}" if f.line else f"`{f.path}`" for f in verdict.findings)
        elif verdict.status == "DELEGATED":
            location = "리뷰어 위임"
        elif verdict.status == "SKIP":
            location = "대상 파일 없음"
        else:
            location = ""
        lines.append(f"| {verdict.id} | {verdict.status} | {verdict.rule} | {location} |")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="리뷰 원장 검사기 — 판정만 하고 고치지 않는다")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--diff", type=Path, help="diff 파일. 지정하면 git 을 읽지 않는다")
    parser.add_argument("--base", help="git diff 기준 ref")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skip-deps", action="store_true", help="전역 스킬 존재 확인 생략")
    args = parser.parse_args()

    if not args.skip_deps:
        missing = missing_global_skills(DEFAULT_DEPENDENCIES)
        if missing:
            print(f"전역 스킬 누락: {', '.join(missing)} — {GLOBAL_SKILL_ROOT} 를 확인하라. 검사를 시작하지 않는다.", file=sys.stderr)
            return EXIT_UNAVAILABLE

    try:
        items = parse_ledger(args.ledger.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError) as error:
        print(f"원장을 읽지 못했다: {error}", file=sys.stderr)
        return EXIT_UNAVAILABLE

    try:
        diff_text = args.diff.read_text(encoding="utf-8") if args.diff else read_diff_from_git(args.base)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"diff 를 얻지 못했다: {error}", file=sys.stderr)
        return EXIT_UNAVAILABLE

    files = parse_diff(diff_text)
    verdicts = [check_item(item, files) for item in items]
    fail_count = sum(1 for v in verdicts if v.status == "FAIL")

    if args.json:
        payload = {
            "fail_count": fail_count,
            "changed_files": [f.path for f in files],
            "verdicts": [
                {
                    "id": v.id,
                    "rule": v.rule,
                    "status": v.status,
                    "findings": [{"path": f.path, "line": f.line, "content": f.content} for f in v.findings],
                }
                for v in verdicts
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"변경 파일 {len(files)}개 · 원장 {len(items)}항목")
        print(render_table(verdicts))
        print(f"\nFAIL {fail_count}건")

    return EXIT_FAIL if fail_count else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
