# 전역 스킬 의존 목록

이 OS는 범용 스킬을 **이름으로 참조**한다. 전역 플러그인 `~/.claude/skills/guesung/`이 SSOT이며, 이 레포로 복사·symlink 하지 않는다. ([orchestrator-plan.md](../docs/orchestrator-plan.md) 0절)

검사기(`/ledger-check`)는 시작 시 아래 목록의 존재를 확인하고, 없으면 실행 전에 멈춘다.

단계 번호는 [`/os:implement-loop`](./skills/implement-loop/SKILL.md)의 ①~⑧과 같다.

| 스킬 | 쓰이는 단계 | 상태 |
|---|---|---|
| `/guesung:spec-build` | ① 구현 — 브랜치 규칙(`feature/<기획명>-<작업명>`)을 따른다 | 있음 |
| `/guesung:advance-code` | ④ 리팩토링 (b) [Frontend Fundamentals](https://github.com/toss/frontend-fundamentals) 기준 개선 제안. FF 플러그인 스킬 본문을 `references/`로 가져와 직접 관리 | 없음 |
| `/guesung:ui-verify` | ⑥ 셀프 QA — `/os:self-qa`가 자동 항목 판정에 호출 | 있음 |
| `/guesung:md` | ⑦ 테섭 배포 — develop 머지 & `origin` push | 있음 |
| `/guesung:pr` | ⑧ Draft PR | 있음 |
| `/guesung:convention-review` | ⑧ 직후 — 루프가 아니라 `/guesung:pr`이 PR을 만든 뒤 스스로 호출한다 | 있음 |
| `/guesung:review-feedback-log` | 되먹임 — 최종 리뷰 지적을 노션 원장(적립층)에 적립 | 있음 |

존재 확인 경로: `~/.claude/skills/guesung/commands/<name>.md` 또는 `~/.claude/skills/guesung/skills/<name>/SKILL.md`.

### 목록에 없는 것

- **`/guesung:full-review`** — [OS.md](../OS.md) 4.9가 재사용 후보로 꼽았지만 파이프라인에 넣지 않았다. ③ 리뷰어와 ⑤ 반려자는 **원장·컨벤션에 있는 것만** · **반려 근거만** 보도록 범위를 좁혀놨는데, 그래야 회차가 수렴한다. 범위를 좁히지 않는 범용 리뷰를 섞으면 매 회차 다른 이유로 FAIL이 나서 상한 3회를 그냥 태운다. 없어서 빠진 게 아니라 **안 쓰기로 한 것**이다.

## MCP 의존

스킬이 아니라 MCP 서버다. 검사기는 확인하지 않는다 — 없으면 해당 단계에서 정지 조건 E로 멈춘다.

| MCP | 쓰이는 곳 | 용도 |
|---|---|---|
| `claude.ai Notion` | `/os:work-card`, `/os:ledger-promote` | 팀 작업리스트·스레드 모음 읽기, 코드 리뷰 문서화 DB 읽기 (cashwalkteam) |
| `notion-home` | `/os:work-card`, `/os:implement-loop`, `/os:self-qa`, `/os:problem-log` | 개인 업무 로그 페이지·QA 항목 DB·문제 해결 일지DB 읽기·쓰기 (guesung) |
| `slack` 플러그인 | `/os:work-card` | 스레드 읽기 → 설계서 초안 |

DB 식별자·속성·접근 규칙은 [notion-databases.md](./notion-databases.md)가 SSOT다. 스킬 본문에는 ID를 두지 않는다.
