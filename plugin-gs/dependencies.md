# 전역 스킬 의존 목록

이 플러그인은 범용 스킬을 **이름으로 참조**한다. 전역 커맨드 `~/.claude/commands/`가 SSOT이며, 이 폴더로 복사·symlink 하지 않는다.

| 스킬 | 쓰이는 단계 | 없으면 |
|---|---|---|
| `/ui-verify` | ② 셀프 QA — `/gs:self-qa`가 자동 항목 판정에 호출 | 자동 항목을 전부 수동으로 돌린다 |

존재 확인 경로: `~/.claude/commands/<name>.md`.

> `/guesung:*` 접두사 플러그인은 없어졌다. PR·커밋은 전역 의존이 아니라 **플러그인 내장 스킬 `/gs:pr`·`/gs:commit`**을 쓴다.
>
> 회사판이 의존하던 `spec-build`·`convention-review`·`advance-code`·`review-feedback-log`는 쓰지 않는다 — 전부 품질 판정 구간(원장·리팩토링·되먹임)의 부품이고, 이 플러그인에는 그 구간이 없다.

## 에이전트 (플러그인 내장)

| 에이전트 | 쓰이는 곳 | 역할 |
|---|---|---|
| `gs:planner` | `/gs:idea` ① | 아이디어 → 기획서 초안 + 결정 필요 |
| `gs:designer` | `/gs:design` ①-D | 기획 → 디자인 명세 초안 (UI 있는 작업만) |
| `gs:backend-dev` | `/gs:implement-loop` ① | TDL `[BE]` 구현. API 계약을 먼저 고정 |
| `gs:frontend-dev` | `/gs:implement-loop` ① | TDL `[FE]` 구현. BE의 계약 위에 쌓는다 |

## MCP 의존

| MCP | 쓰이는 곳 | 용도 |
|---|---|---|
| `notion-home` | `/gs:idea`, `/gs:design`, `/gs:implement-loop`, `/gs:self-qa`, `/gs:problem-log` | 개인 업무 로그·QA 항목·문제 해결 일지 읽기·쓰기 (guesung) |

회사판이 쓰던 `claude.ai Notion`(팀 DB)·`slack` 플러그인은 쓰지 않는다.

DB 식별자·속성·접근 규칙은 [notion-databases.md](./notion-databases.md)가 SSOT다. 스킬 본문에는 ID를 두지 않는다.
