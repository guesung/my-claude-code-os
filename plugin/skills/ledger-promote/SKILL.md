---
name: ledger-promote
description: 노션 "코드 리뷰 문서화 DB"(적립층)에 쌓인 리뷰 규칙 중 아직 리뷰 원장(ledger.yaml, 실행층)에 없는 것을 골라, 검증 가능한 형태(grep 패턴 + fixture 위반 줄, 또는 judgment 판정 기준)로 초안을 만들고 사람 승인 후 원장에 올린다. 노션에서 폐기된 항목은 원장에서 내리고, 재발 카운트도 여기서 올린다. "원장 승격", "노션 규칙 원장에 올려", "원장 갱신", "ledger promote", "재발 올려줘" 같은 표현이 나오면 이 스킬을 사용한다. 최종 리뷰에서 /guesung:review-feedback-log 로 노션에 적립한 뒤 호출하는 것이 정상 경로다.
argument-hint: '[--recur <id>] [--dry-run]'
---

# /os:ledger-promote — 노션 적립층 → 원장 실행층

OS.md 3절의 되먹임 화살표가 이것이다. 사람이 지적한 것(노션)이 다음 사이클의 판정 기준(원장)이 된다.
**원장이 두꺼워지면 검사기가 자동으로 두꺼워진다.** 그래서 grep 항목은 fixture 위반 줄 없이는 올라갈 수 없다 — 기계가 잡는다는 걸 기계로 증명해야 한다.

## 역할 분담

| 누가 | 하는 것 |
|---|---|
| 이 스킬(LLM) | 노션 읽기 · 원장과 대조 · grep/judgment 분류 · 패턴·판정 기준·fixture 초안 · 사람에게 보여주기 |
| `scripts/ledger_promote.py` | 원장·fixture에 쓰기 · YAML 서브셋 준수 · 검사기로 파싱과 FAIL 증가 검증 · 실패 시 되돌림 |
| 사람 | 승인. OS.md 4.7 — 원장 갱신은 사람 검토를 거친다 |

원장 파일을 LLM이 직접 편집하지 않는다.

## 식별자

| | 값 |
|---|---|
| 노션 코드 리뷰 문서화 DB | `collection://3c1a054b-7d82-801a-a2be-000bf6c7cdf3` (`claude.ai Notion` MCP) |
| 원장 | `${CLAUDE_PLUGIN_ROOT}/ledger/ledger.yaml` |
| fixture | `${CLAUDE_PLUGIN_ROOT}/ledger/fixtures/violations.diff` |
| 스크립트 | `${CLAUDE_PLUGIN_ROOT}/skills/ledger-promote/scripts/ledger_promote.py` |

## `--recur <id>` — 재발 카운트

최종 검토에서 사람이 **원장에 이미 있는 항목**을 다시 지적했을 때. 새 규칙이 아니라 기존 규칙이 안 지켜진 것이다.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/ledger-promote/scripts/ledger_promote.py" --recur L-001
```

재발이 2 이상이면 출력에 한 줄 덧붙인다: `L-001 재발 n회 — 검증법이 실제로 잡고 있는지 fixture와 pattern을 의심하라.` 재발이 쌓이는 건 규칙 문제가 아니라 **검증법이 약하다는 신호**일 때가 많다.

## 승격 절차 (인자 없음)

### ① 노션 읽기

```sql
SELECT url, "이름", "내용", "분류", "상태", "중요도", "적용 범위", "PR"
FROM "collection://3c1a054b-7d82-801a-a2be-000bf6c7cdf3"
```

### ② 원장과 대조

```bash
python3 …/ledger_promote.py --list        # id, type, 출처 URL
```

- 노션 `상태`=적용중 이고 `url`이 원장 `출처`에 없음 → **승격 후보**
- 노션 `상태`=폐기 이고 `url`이 원장 `출처`에 있음 → **폐기 후보**
- 둘 다 없으면 "승격할 항목 없음"으로 끝

### ③ 후보마다 초안

**grep이 되는가**를 먼저 판단한다. 기준: 위반이 **한 줄 안의 문자열 패턴**으로 드러나는가.

| grep 가능 | grep 불가 → judgment |
|---|---|
| 특정 API·키워드·속성 사용 (`useCallback(`, `is:global`, `<svg`) | "이름이 구체적인가", "사용처가 한 곳인가"처럼 문맥이 필요한 것 |
| 파일명 패턴 (`.test.`) | 여러 파일에 걸친 구조 |
| 임의값 형태 (`-[13px]`) | 의도·설계 판단 |

**애매하면 judgment.** grep으로 올렸다가 오탐이 나면 원장 신뢰가 깎인다. judgment로 두고 재발이 쌓이면 그때 grep으로 승격해도 늦지 않다.

초안 형식 (JSON, 스크립트 입력):

```json
[
  {
    "규칙": "한 줄. 노션 `이름` 기반, 검증 가능하게 다듬음",
    "출처": "https://app.notion.com/<노션 페이지>",
    "중요도": "높음 | 보통 | 낮음  ← 노션 값 그대로",
    "검증": { "type": "grep", "scope": "added", "pattern": "정규식", "glob": "**/*.{ts,tsx}" },
    "fixture": { "path": "src/fixtures/<규칙-slug>.ts", "lines": ["위반하는 코드 한두 줄"] }
  },
  {
    "규칙": "…",
    "출처": "…",
    "중요도": "…",
    "검증": { "type": "judgment", "판정 기준": "무엇을 보면 FAIL인가 한 문장. 예외가 있으면 명시" }
  }
]
```

- `pattern`은 fixture `lines` 중 **정확히 한 줄**에만 걸려야 한다. 두 줄 이상 걸리면 fixture를 줄인다.
- `fixture.path`는 기존 fixture 파일과 겹치지 않게. glob에 맞는 확장자.
- `판정 기준`에 `: ` 가 들어가도 된다(스크립트가 `>-` 블록으로 쓴다).

### ④ 사람 승인

승격 후보·폐기 후보를 표로 보여준다. 항목마다 `규칙 · type · pattern 또는 판정 기준 · fixture 줄`. **승인 없이 쓰지 않는다.** `--dry-run`이면 여기서 끝.

`AskUserQuestion` multiSelect로 올릴 항목을 고르게 한다. 고른 것만 JSON 파일로 만든다(`${CLAUDE_PLUGIN_ROOT}/ledger/.promote.json`, 임시).

### ⑤ 쓰기 + 검증

```bash
python3 …/ledger_promote.py --add "${CLAUDE_PLUGIN_ROOT}/ledger/.promote.json"
python3 …/ledger_promote.py --retire L-0xx     # 폐기 후보마다
```

스크립트가 하는 검증 — 하나라도 실패하면 **원장·fixture를 되돌리고** 종료 코드 1:

1. 정규식 컴파일
2. 출처 중복
3. 원장 파싱(검사기 서브셋)
4. fixture로 검사기 실행 → **새 grep id가 전부 FAIL로 잡히는가**

성공하면 `추가: L-0xx [grep] …` 와 `검사기 FAIL n → m`이 나온다. 임시 JSON을 지운다.

### ⑥ 마무리

- `git diff --stat ledger/` 를 보여주고 커밋한다: `feat(ledger): L-0xx, L-1xx 승격 — <규칙 요약>`
- 폐기는 `ledger/retired.yaml`에 날짜와 함께 남는다. 지우지 않는다 — 왜 빠졌는지가 남아야 한다.

## 하지 않는 것

- 노션을 쓰지 않는다. 노션 적립은 `/guesung:review-feedback-log`의 일이다.
- 승인 없이 원장을 바꾸지 않는다.
- fixture 없는 grep 항목을 올리지 않는다. 스크립트가 거부한다.
- 노션 30건을 한 번에 다 올리지 않는다. 후보가 많으면 **중요도 높음부터 5개 이내**로 끊어 제안한다. 원장은 "다시 지적받으면 안 되는 것"의 목록이지 규칙 백과가 아니다.

## 왜 이렇게 나눴나

- **fixture 강제** — "검증 가능한 형태로 적는다"(OS.md 4.1)를 사람의 의지가 아니라 스크립트의 거부로 보장한다.
- **되돌림** — 원장이 반쯤 깨진 상태로 남으면 다음 검사기 실행이 전부 멈춘다. 전부 성공하거나 전부 없던 일이어야 한다.
- **애매하면 judgment** — grep 오탐 1건이 judgment 누락 1건보다 비싸다. 오탐은 원장 전체를 의심하게 만든다.
- **재발을 검증법 신호로** — 같은 규칙이 반복 지적되면 사람이 아니라 검사기가 놓친 것이다.
