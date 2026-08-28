# 전역 스킬 의존 목록

이 OS는 범용 스킬을 **이름으로 참조**한다. 전역 플러그인 `~/.claude/skills/guesung/`이 SSOT이며, 이 레포로 복사·symlink 하지 않는다. ([orchestrator-plan.md](../docs/orchestrator-plan.md) 0절)

검사기(`/ledger-check`)는 시작 시 아래 목록의 존재를 확인하고, 없으면 실행 전에 멈춘다.

| 스킬 | 쓰이는 단계 | 상태 |
|---|---|---|
| `/guesung:spec-build` | ① 구현 | 있음 |
| `/guesung:convention-review` | ④ 리팩토링 (a) 위반 수정 | 있음 |
| `/guesung:advance-code` | ④ 리팩토링 (b) [Frontend Fundamentals](https://github.com/toss/frontend-fundamentals) 기준 개선 제안 | **미구현** |
| `/guesung:ui-verify` | ⑥ 셀프 QA — `/os:self-qa`가 자동 항목 판정에 호출 | 있음 |
| `/guesung:pr` | ⑦ Draft PR | 있음 |
| `/guesung:review-feedback-log` | 되먹임 — 최종 리뷰 지적을 노션 원장(적립층)에 적립 | 있음 |

존재 확인 경로: `~/.claude/skills/guesung/commands/<name>.md` 또는 `~/.claude/skills/guesung/skills/<name>/SKILL.md`.

## MCP 의존

스킬이 아니라 MCP 서버다. 검사기는 확인하지 않는다 — 없으면 해당 단계에서 정지 조건 E로 멈춘다.

| MCP | 쓰이는 곳 | 용도 |
|---|---|---|
| `claude.ai Notion` | `/os:work-card` | 팀 작업리스트·스레드 모음 읽기 (cashwalkteam) |
| `notion-home` | `/os:work-card`, `/os:implement-loop`, `/os:self-qa` | 개인 업무 로그 페이지·QA 항목 DB 읽기·쓰기 (guesung) |
| `slack` 플러그인 | `/os:work-card` | 스레드 읽기 → 설계서 초안 |
