# 전역 스킬 의존 목록

이 OS는 범용 스킬을 **이름으로 참조**한다. 전역 플러그인 `~/.claude/skills/guesung/`이 SSOT이며, 이 레포로 복사·symlink 하지 않는다. ([orchestrator-plan.md](./orchestrator-plan.md) 0절)

검사기(`/ledger-check`)는 시작 시 아래 목록의 존재를 확인하고, 없으면 실행 전에 멈춘다.

| 스킬 | 쓰이는 단계 | 상태 |
|---|---|---|
| `/guesung:spec-build` | ① 구현 | 있음 |
| `/guesung:convention-review` | ④ 리팩토링 (a) 위반 수정 | 있음 |
| `/guesung:advance-code` | ④ 리팩토링 (b) [Frontend Fundamentals](https://github.com/toss/frontend-fundamentals) 기준 개선 제안 | **미구현** |
| `/guesung:ui-verify` | ⑥ 셀프 QA | 있음 |
| `/guesung:pr` | ⑦ Draft PR | 있음 |
| `/guesung:review-feedback-log` | 되먹임 — 최종 리뷰 지적을 노션 원장(적립층)에 적립 | 있음 |

존재 확인 경로: `~/.claude/skills/guesung/commands/<name>.md` 또는 `~/.claude/skills/guesung/skills/<name>/SKILL.md`.
