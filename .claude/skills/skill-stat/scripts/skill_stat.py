#!/usr/bin/env python3
"""
skill_stat.py — Claude Code 세션 transcript에서 스킬 호출 통계를 집계한다.

데이터 소스: ~/.claude/projects/<프로젝트>/<세션UUID>.jsonl
  (CLAUDE_CONFIG_DIR 환경변수가 있으면 그쪽을 우선한다)

transcript의 각 줄은 하나의 이벤트(JSON)이고, 스킬 호출은
assistant 메시지 안의 tool_use 블록으로 남는다:

    {"type":"assistant","timestamp":"...","cwd":"...","sessionId":"...",
     "message":{"content":[{"type":"tool_use","name":"Skill",
                            "input":{"skill":"guesung:commit","args":"..."}}]}}

이 스크립트는 그 블록만 골라 세어 표로 출력한다.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import sys
import unicodedata
from datetime import datetime, timedelta, timezone


def transcript_root() -> str:
    """transcript가 쌓이는 디렉터리를 돌려준다."""
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")

    return os.path.join(config_dir, "projects")


def parse_timestamp(raw: str | None) -> datetime | None:
    """ISO8601(UTC) 문자열을 aware datetime으로 바꾼다. 실패하면 None."""
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def iter_skill_calls(root: str):
    """모든 transcript를 훑어 스킬 호출 이벤트를 하나씩 내보낸다.

    dedupe는 이벤트 uuid로 한다. --resume/compaction으로 같은 이벤트가
    두 파일에 실릴 수 있어서, 세지 않고 그대로 두면 횟수가 부풀 수 있다.
    """
    seen: set[str] = set()
    files = sorted(glob.glob(os.path.join(root, "*", "*.jsonl")))

    for path in files:
        try:
            handle = open(path, "r", encoding="utf-8", errors="replace")
        except OSError:
            continue

        with handle:
            for line in handle:
                # 전체 JSON 파싱은 비싸다. 스킬 호출이 없는 줄은 문자열로 먼저 거른다.
                if '"Skill"' not in line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                message = event.get("message")
                if not isinstance(message, dict):
                    continue

                uuid = event.get("uuid")
                if uuid and uuid in seen:
                    continue

                content = message.get("content")
                if not isinstance(content, list):
                    continue

                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use" or block.get("name") != "Skill":
                        continue

                    tool_input = block.get("input")
                    if not isinstance(tool_input, dict):
                        continue

                    name = tool_input.get("skill")
                    if not name:
                        continue

                    if uuid:
                        seen.add(uuid)

                    yield {
                        "skill": name,
                        "args": tool_input.get("args") or "",
                        "at": parse_timestamp(event.get("timestamp")),
                        "cwd": event.get("cwd") or "",
                        "session": event.get("sessionId") or "",
                        "branch": event.get("gitBranch") or "",
                    }


def nfc(text: str) -> str:
    """경로 비교용 정규화.

    macOS의 os.getcwd()는 한글을 NFD(자모 분리)로 돌려주는데 transcript의 cwd는
    NFC(완성형)로 저장된다. 정규화 없이 비교하면 같은 경로인데도 매칭이 실패해
    필터가 조용히 0건을 반환한다.
    """
    return unicodedata.normalize("NFC", text)


def filter_calls(calls, days: int | None, project: str | None):
    """기간·프로젝트 조건으로 호출을 걸러낸다."""
    cutoff = None
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    needle = nfc(project) if project else None

    for call in calls:
        if cutoff is not None:
            if call["at"] is None or call["at"] < cutoff:
                continue

        if needle and needle not in nfc(call["cwd"]):
            continue

        yield call


def to_local_date(value: datetime | None) -> str:
    """UTC 타임스탬프를 로컬 날짜 문자열로 바꾼다."""
    if value is None:
        return "-"

    return value.astimezone().strftime("%Y-%m-%d")


def display_width(text: str) -> int:
    """터미널에서 차지하는 칸 수. 한글·CJK는 한 글자가 두 칸이다."""
    width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ("W", "F"):
            width += 2
        else:
            width += 1

    return width


def pad(text: str, target: int, align: str) -> str:
    """display_width 기준으로 빈칸을 채운다. len()으로 맞추면 한글에서 어긋난다."""
    space = " " * max(0, target - display_width(text))

    if align == "r":
        return space + text

    return text + space


def render_table(rows: list[list[str]], headers: list[str], aligns: list[str]) -> str:
    """고정폭 표를 만든다."""
    widths = [display_width(h) for h in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], display_width(cell))

    def line(cells: list[str]) -> str:
        parts = [pad(cell, widths[index], aligns[index]) for index, cell in enumerate(cells)]

        return "  ".join(parts).rstrip()

    out = [line(headers), line(["-" * w for w in widths])]
    out.extend(line(row) for row in rows)

    return "\n".join(out)


def report_by_skill(calls: list[dict], top: int | None) -> str:
    counts = collections.Counter(call["skill"] for call in calls)
    last_used: dict[str, datetime] = {}
    projects: dict[str, set[str]] = collections.defaultdict(set)

    for call in calls:
        name = call["skill"]
        if call["at"] is not None:
            previous = last_used.get(name)
            if previous is None or call["at"] > previous:
                last_used[name] = call["at"]
        if call["cwd"]:
            projects[name].add(call["cwd"])

    total = sum(counts.values())
    ranked = counts.most_common(top) if top else counts.most_common()

    rows = []
    for name, count in ranked:
        share = (count / total * 100) if total else 0
        bar = "█" * max(1, round(share / 100 * 24))
        rows.append([
            name,
            str(count),
            f"{share:4.1f}%",
            bar,
            to_local_date(last_used.get(name)),
            str(len(projects.get(name, ()))),
        ])

    return render_table(
        rows,
        ["스킬", "호출", "비중", "", "마지막 사용", "프로젝트"],
        ["l", "r", "r", "l", "l", "r"],
    )


def report_by_project(calls: list[dict], top: int | None) -> str:
    counts = collections.Counter(
        os.path.basename(call["cwd"]) or "(unknown)" for call in calls
    )
    ranked = counts.most_common(top) if top else counts.most_common()
    rows = [[name, str(count)] for name, count in ranked]

    return render_table(rows, ["프로젝트", "호출"], ["l", "r"])


def report_by_day(calls: list[dict], top: int | None) -> str:
    counts = collections.Counter(
        to_local_date(call["at"]) for call in calls if call["at"] is not None
    )
    ranked = sorted(counts.items())
    if top:
        ranked = ranked[-top:]

    rows = [[day, str(count), "█" * min(count, 40)] for day, count in ranked]

    return render_table(rows, ["날짜", "호출", ""], ["l", "r", "l"])


def report_recent(calls: list[dict], limit: int) -> str:
    ordered = sorted(
        (call for call in calls if call["at"] is not None),
        key=lambda call: call["at"],
        reverse=True,
    )[:limit]

    rows = []
    for call in ordered:
        args = call["args"].replace("\n", " ")
        if len(args) > 48:
            args = args[:47] + "…"
        rows.append([
            call["at"].astimezone().strftime("%Y-%m-%d %H:%M"),
            call["skill"],
            os.path.basename(call["cwd"]) or "-",
            args or "-",
        ])

    return render_table(rows, ["시각", "스킬", "프로젝트", "인자"], ["l", "l", "l", "l"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Claude Code transcript에서 스킬 호출 통계를 집계한다."
    )
    parser.add_argument(
        "--by",
        choices=["skill", "project", "day", "recent"],
        default="skill",
        help="집계 기준 (기본: skill)",
    )
    parser.add_argument("--days", type=int, help="최근 N일로 기간 제한")
    parser.add_argument("--project", help="cwd에 이 문자열이 포함된 호출만 집계")
    parser.add_argument("--here", action="store_true", help="현재 디렉터리 기준으로 필터")
    parser.add_argument("--top", type=int, help="상위 N개만 출력")
    parser.add_argument("--json", action="store_true", help="집계 결과를 JSON으로 출력")
    args = parser.parse_args()

    root = transcript_root()
    if not os.path.isdir(root):
        print(f"transcript 디렉터리를 찾을 수 없습니다: {root}", file=sys.stderr)
        return 1

    project = args.project
    if args.here:
        project = os.getcwd()

    calls = list(filter_calls(iter_skill_calls(root), args.days, project))

    if not calls:
        scope = []
        if args.days:
            scope.append(f"최근 {args.days}일")
        if project:
            scope.append(f"프로젝트 '{project}'")
        suffix = f" ({', '.join(scope)})" if scope else ""
        print(f"집계할 스킬 호출이 없습니다{suffix}.")

        return 0

    if args.json:
        payload = {
            "total": len(calls),
            "unique_skills": len({call["skill"] for call in calls}),
            "counts": dict(collections.Counter(c["skill"] for c in calls).most_common()),
            "range": {
                "from": to_local_date(min(c["at"] for c in calls if c["at"])),
                "to": to_local_date(max(c["at"] for c in calls if c["at"])),
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))

        return 0

    stamps = [call["at"] for call in calls if call["at"] is not None]
    header = f"총 {len(calls)}회 · 고유 스킬 {len({c['skill'] for c in calls})}개"
    if stamps:
        header += f" · {to_local_date(min(stamps))} ~ {to_local_date(max(stamps))}"

    print(header)
    print()

    if args.by == "skill":
        print(report_by_skill(calls, args.top))
    elif args.by == "project":
        print(report_by_project(calls, args.top))
    elif args.by == "day":
        print(report_by_day(calls, args.top))
    else:
        print(report_recent(calls, args.top or 20))

    return 0


if __name__ == "__main__":
    sys.exit(main())
