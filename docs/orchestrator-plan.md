# 오케스트레이터 구축 계획

> [OS.md](../OS.md) 3절 골격을 실제 파일로 옮기는 계획. 2026-08-28 점검 결과를 바탕으로 작성.
> 원칙: **부품 먼저, 최소로.** 오케스트레이터(3주차)는 원장·리뷰어·검사기(1·2주차) 위에 얹는다.

## 0. 점검에서 확정한 것

| 쟁점 | 결정 | 근거 |
|---|---|---|
| 진행 순서 | 원장 v0 → 검사기 v0 → 리뷰어/반려자 에이전트 → 오케스트레이터 | 원장 없는 오케스트레이터는 판정 기준이 빈 껍데기 |
| 전역 스킬 연결 | **이름으로 참조.** 복사·symlink 하지 않는다 | symlink는 다른 PC·조별 리뷰에서 끊기고 이중 로드됨. 복사는 7절 동기화 문제를 OS 안으로 끌어들임 |
| 원장 소스 | **노션 "코드 리뷰 문서화 DB"(30건)** 가 적립층. 레포 `ledger.yaml`이 실행층 | 이미 `/guesung:review-feedback-log`가 채우고 있는 자산. 다만 노션엔 `검증법`·`재발` 필드가 없어 실행층이 따로 필요 |
| 설계 문서 위치 | 이 레포 `docs/` | 노션 원장의 "스펙은 레포에 커밋하지 않는다" 규칙은 업무 레포 대상. 이 레포는 CLAUDE.md 1번이 우선 |

### 전역(SSOT)과 레포의 경계

```
~/.claude/skills/guesung/        (전역 플러그인, ~/.claude git 레포로 버전 관리됨)
  범용 스킬 — spec-build · full-review · ui-verify · pr · review-feedback-log · advance-code(미구현)
        ▲ 이름으로 호출 (/guesung:xxx)
        │
my-claude-code-os/               (이 레포)
  OS 고유 부품 — 원장 · 검사기 · 리뷰어/반려자 에이전트 · 오케스트레이터
  docs/dependencies.md — 필요한 전역 스킬 목록. 검사기가 시작 시 존재 확인
```

OS.md 4.8에 적힌 `/self-qa-checklist`는 전역에 존재하지 않는다. 셀프 QA는 `/guesung:ui-verify`로 대체한다.

## 1. 목표 파일 구조

```
my-claude-code-os/
├── ledger/
│   ├── ledger.yaml                 # 실행 원장 v0
│   └── fixtures/
│       └── violations.diff         # 검사기·리뷰어 검증용. 원장 항목을 일부러 위반한 diff
├── .claude/
│   ├── agents/
│   │   ├── ledger-reviewer.md      # 리뷰어: 원장 + 컨벤션 기준으로만 판정
│   │   └── rejector.md             # 교차 컨펌: diff만 보고 "반려 근거"를 찾는다
│   └── skills/
│       ├── ledger-check/           # 검사기 v0
│       │   ├── SKILL.md
│       │   └── scripts/ledger_check.py
│       └── implement-loop/         # 오케스트레이터 (3주차)
│           └── SKILL.md
└── docs/
    ├── dependencies.md             # 전역 스킬 의존 목록
    └── orchestrator-plan.md        # 이 문서
```

## 2. 작업 카드 (노션, SSOT)

기능 하나 = 노션 작업 카드 하나. 오케스트레이터의 **입력이자 출력**이다. 레포 안에 md로 상태를 남기지 않는다(OS.md 4.6).

| 섹션 | 쓰는 쪽 | 읽는 쪽 |
|---|---|---|
| 설계서 | AI 초안 → 사람 확정 | ① 구현 |
| TDL (작업 체크리스트) | AI가 설계서에서 뽑고 회차마다 체크 | ① 구현, 사람의 진행 파악 |
| QA 체크리스트 | AI가 기획서에서 뽑음. 자동/수동 구분 | ⑥ 셀프 QA. 수동 항목은 재현 방법과 함께 사람에게 |
| 논의 필요 | AI가 "막힐 지점"·판단 못 한 것을 적립 | 사람. 답이 나오면 설계서에 반영 |
| 루프 로그 | 회차별 검사기·리뷰어·반려자 판정 요약 | 사람의 최종 검토, 4주차 재발률 집계 |

- 카드 접근은 노션 MCP(`notion-fetch` / `notion-update-page`). 카드 URL을 오케스트레이터 인자로 받는다.
- 루프 **상태**(현재 회차 등)는 `.omc/state/implement-loop.json`에 두되, 사람이 볼 **기록**은 카드의 루프 로그에 남긴다. 상태는 휘발돼도 되고 기록은 남아야 하기 때문에 둘을 나눈다.

## 3. 원장 스키마 (`ledger/ledger.yaml`)

```yaml
- id: L-001
  규칙: useCallback / useMemo 를 습관적으로 붙이지 않는다
  출처: ~/.claude/CLAUDE.md 핵심 규칙 9        # 노션 항목이면 페이지 URL
  검증:
    type: grep                                # grep | ast | judgment
    pattern: '\b(useCallback|useMemo)\('
    scope: added                              # added(추가 라인) | files(변경 파일 전체)
    glob: '**/*.{ts,tsx}'
  중요도: 높음
  재발: 0
```

- `type: grep` — 검사기가 기계로 판정. 발견 즉시 FAIL.
- `type: ast` — ast-grep 패턴. v0에서는 비워두고 스키마만 예약.
- `type: judgment` — 기계 판정 불가. 리뷰어 에이전트에게 지침으로만 전달. `pattern` 대신 `판정 기준` 한 줄.
- `재발` — 최종 리뷰에서 사람이 같은 걸 다시 지적하면 +1. 4주차 채점 지표.

### v0 후보 (노션 30건 + 전역 컨벤션에서 grep 가능한 것)

| id | 규칙 | 검증 |
|---|---|---|
| L-001 | useCallback/useMemo 습관적 사용 금지 | grep `useCallback\|useMemo` |
| L-002 | 테스트 코드는 작성하지 않는다 | 변경 파일명에 `.test.`/`.spec.` |
| L-003 | 외부 fetch는 공통 fetchClient를 쓴다 | 추가 라인에 `fetch(` (fetchClient 파일 제외) |
| L-004 | 인라인 svg는 파일로 분리해 import한다 | 추가 라인에 `<svg` |
| L-005 | Tailwind 임의값 대신 기본 스케일 | grep `\[[0-9.]+(px\|rem)\]` |
| L-006 | 레거시 CSS를 `is:global`로 통째로 옮기지 않는다 | 추가 라인에 `is:global` |
| L-007 | export 대상에 JSDoc | `export` 직전 줄이 `*/`가 아님 (regex, 오탐 허용) |
| L-008 | 비밀값 아닌 설정은 env 대신 코드 상수 | grep `process.env\|import.meta.env` → **judgment로 승격 필요**(비밀값인지 사람이 봐야 함) |

나머지 22건 중 "이름은 구체적으로", "범용 유틸과 도메인 로직 분리" 같은 것은 `judgment`로 5개 내외만 골라 넣는다. 전부 옮기지 않는다 — 리뷰어 컨텍스트가 비대해지면 판정이 흐려진다.

## 4. 단계별 작업

각 단계는 **독립적으로 검증 가능**해야 다음 단계로 간다.

### Step 1 — 원장 v0 (1주차)

- `ledger/ledger.yaml` 수기 작성. grep 5~8개 + judgment 5개 내외.
- `ledger/fixtures/violations.diff` — 각 grep 항목을 정확히 하나씩 위반하는 diff.
- **검증**: 없음(데이터). Step 2가 검증한다.

### Step 2 — 검사기 v0 (2주차)

- `ledger_check.py`: `ledger.yaml`을 읽고 `git diff <base>...HEAD`(또는 인자로 받은 diff 파일)에 grep 항목을 실행. 항목별 `PASS/FAIL + 파일:라인` 출력, `--json` 옵션.
- 시작 시 `docs/dependencies.md`의 전역 스킬 존재 확인. 없으면 실행 전에 멈춘다.
- `SKILL.md`: "원장 검사", "ledger check" 트리거. 결과를 표로 보여주기만 하고 고치지 않는다.
- **검증**: fixture로 돌려 grep 항목 전부 FAIL, 깨끗한 diff로 돌려 전부 PASS.

### Step 3 — 리뷰어 에이전트 (2주차)

`.claude/agents/ledger-reviewer.md`

- 입력: diff + `ledger.yaml`의 judgment 항목 + 검사기 JSON 결과.
- 출력: 항목별 `PASS/FAIL/N.A. + 근거 라인`. **원장·컨벤션에 없는 지적은 금지** — 범위 규율이 없으면 리뷰어가 매번 다른 걸 지적해 루프가 수렴하지 않는다.
- 별도 컨텍스트(Agent 도구)로 실행. 구현자의 대화 내용을 보지 않는다.
- **검증**: fixture로 실행해 judgment 항목 중 명백한 위반을 잡는지 확인.

### Step 4 — 반려자 에이전트 (2주차 후반)

`.claude/agents/rejector.md`

- 입력: **diff만.** 설계서·리뷰어 결과를 주지 않는다.
- 임무: "이 PR을 반려시킬 근거를 찾아라". 못 찾으면 "반려 근거 없음"과 함께 **diff에서 읽어낸 의도**를 한 문단으로 쓴다 → 가독성 테스트.
- **검증**: fixture에서 의도가 올바로 읽히는지, 억지 반려를 만들어내지 않는지 2~3회 돌려본다.

### Step 5 — 오케스트레이터 (3주차)

`.claude/skills/implement-loop/SKILL.md`. 상태 파일 `.omc/state/implement-loop.json`에 회차·판정을 기록.

```
[사람] 설계서 확정
   │
   ▼
① 구현          /guesung:spec-build 또는 직접. 카드의 설계서·TDL을 읽는다
② 검사기        /ledger-check          ─┐
③ 리뷰어        ledger-reviewer         │  하나라도 FAIL → ④ → ②로
④ 리팩토링      (a) FAIL 항목 수정 — 필수 │  회차 ≤ 3. 초과 시 멈추고 사람에게
               (b) FF 기준 개선 제안 — 선택 │  조기 종료: 전부 PASS + 반려 없음 + (b) 제안 없음
⑤ 반려자        rejector               ─┘  반려 근거 있음 → ④로 (회차 공유)
⑥ 셀프 QA       /guesung:ui-verify     카드의 QA 체크리스트 기준. 자동 불가 항목은 재현 방법을 남긴다
⑦ Draft PR      /guesung:pr
   │
   ▼
[사람] 최종 검토 → 지적 → /guesung:review-feedback-log → 노션 → (4주차) ledger 승격
```

- 회차 상한 3은 ②~⑤ 전체를 한 회차로 센다. **상한이지 고정이 아니다** — 종료 조건을 만족하면 1회차에도 끝난다.
- ④(a)와 ④(b)는 성격이 다르다. (a)는 원장·컨벤션 **위반**이라 반드시 고친다. (b)는 [Frontend Fundamentals](https://github.com/toss/frontend-fundamentals)(가독성·예측 가능성·응집도·결합도) 기준으로 **더 나은 코드가 될 수 있는지**를 제안하는 것이라, 적용 여부는 사람이 고른다. 둘을 섞으면 "위반"과 "취향"이 구분되지 않아 원장이 오염된다.
- (b)는 전역 스킬 `/guesung:advance-code`로 분리한다(**미구현**, `docs/dependencies.md`에 표기). FF 4원칙 각각에 대해 변경분을 대조하고 "현재 → 제안 → 근거(FF 문서 링크)" 형태로만 낸다. 자동으로 고치지 않는다.
- 사람 개입은 **시작(설계서)과 끝(최종 검토)** 두 번. (b)의 제안 선택은 최종 검토에 합친다.
- **검증**: 실제 대상 레포에서 작은 기능 1개를 end-to-end로 돌린다. → 이 시점에 §6의 미결 사항을 확정해야 한다.

### Step 6 — 되먹임 자동화 (4주차)

- 노션 → `ledger.yaml` 승격 스킬. 노션 항목에 검증법을 붙여 실행 원장에 추가.
- `재발` 카운트 갱신. 재발률 리포트.

## 5. 각 단계에서 배우는 것

CLAUDE.md 2번(협업 학습)에 맞춰, 단계마다 "왜 이렇게 나눴는가"를 남긴다.

| 단계 | 개념 | 핵심 교훈 |
|---|---|---|
| 1 | 컨텍스트 | 검증 가능한 형태로 적어야 AI가 아니라 기계가 막는다 |
| 2 | 스킬 | 판정과 수정을 분리한다. 검사기는 고치지 않는다 |
| 3·4 | 에이전트 | 별도 컨텍스트 + 범위 규율 + 비대칭 역할. 같은 모델의 맹점을 역할로 보정한다 |
| 5 | 루프 | 상한 없는 루프는 발산한다. 상태 파일이 있어야 중단·재개가 된다 |
| 6 | 하네스 | 원장이 두꺼워질수록 검사기가 자동으로 두꺼워진다 |

## 6. 미결 — Step 5 전에 확정할 것

- [ ] **실습 대상 코드베이스.** 노션 원장의 PR 링크는 전부 `CashwalkHomepageAstroWeb`. 회사 레포에서 직접 돌릴지, 별도 샘플을 둘지.
- [ ] **OS를 다른 레포에서 실행하는 방식.** `.claude/skills`는 이 레포 안에서만 로드된다. 후보: ① 이 레포를 로컬 플러그인으로 만들어 `~/.claude`에 설치 ② `~/.claude/skills/os → 이 레포` symlink(로컬 전용). 플러그인화가 정석이나 부품 단계에선 불필요.
- [ ] PR 분할 임계값 (OS.md 6절 그대로 미결).

## 7. 브랜치 전략

현재 `guesung` 브랜치는 base 대비 8개 파일이 쌓여 있다(모두 문서·스킬, 커밋 완료). 부품 작업은 단계마다 브랜치를 끊어 PR 단위를 작게 유지한다:

`feat/ledger-v0` → `feat/ledger-check` → `feat/reviewer-agents` → `feat/implement-loop`
