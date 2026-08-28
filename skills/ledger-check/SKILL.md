---
name: ledger-check
description: 리뷰 원장(ledger/ledger.yaml)의 grep 항목을 이번 변경분에 실행해 항목별 PASS/FAIL을 판정한다. 판정만 하고 고치지 않는다. "원장 검사", "원장 체크", "ledger check", "원장 위반 있어?", "원장대로 검사해줘" 같은 표현이 나오면 이 스킬을 사용한다. 오케스트레이터(/os:implement-loop)의 ② 단계에서도 호출된다.
argument-hint: '[--diff <파일> | --base <ref>] [--json]'
---

# /os:ledger-check — 원장 검사기

원장의 `type: grep` 항목을 변경분에 기계적으로 실행한다. **고치지 않는다.** 결과를 표로 보여주고 멈춘다.
`type: judgment` 항목은 이 검사기의 대상이 아니다 — 리뷰어 에이전트(`ledger-reviewer`)가 판정한다.

## 실행

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/ledger-check/scripts/ledger_check.py" $ARGUMENTS
```

- 인자 없음 → 현재 브랜치가 분기한 base(`origin/main` → `main` → `master` 순 탐색) 이후 변경분 + 워킹트리.
- `--diff <파일>` → 그 diff 파일. fixture 검증용.
- `--base <ref>` → 그 ref 기준 `git diff`.
- `--json` → 기계용 출력. 오케스트레이터가 이걸 읽는다.
- `--skip-deps` → 전역 스킬 존재 확인 생략.

시작 시 `docs/dependencies.md`에 "있음"으로 적힌 전역 스킬이 실제로 있는지 확인한다. 하나라도 없으면 **검사를 시작하지 않고** 종료 코드 2로 멈춘다. 원장 기준을 실행할 환경이 아니라는 뜻이다.

## 출력을 사용자에게 보여주는 방식

스크립트의 표를 그대로 보여준다. 그 아래에 한 줄로 요약한다:

- FAIL이 있으면: `FAIL n건 — ④ 리팩토링 대상. 자동으로 고치지 않았다.`
- FAIL이 없으면: `grep 항목 전부 PASS. judgment m건은 리뷰어에게 넘긴다.`

FAIL 항목을 **먼저 고치려 들지 않는다.** 이 스킬의 책임은 판정까지다. 판정과 수정을 나눠야 "무엇이 위반이었는지"가 기록에 남는다.

## 종료 코드

| 코드 | 뜻 |
|---|---|
| 0 | FAIL 없음 |
| 1 | FAIL 있음 |
| 2 | 실행 불가 — 전역 스킬 누락, 원장 파싱 실패, diff 없음 |
