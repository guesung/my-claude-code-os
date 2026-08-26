---
name: gh-commit
description: 이 레포(my-claude-code-os)의 변경사항을 작업 단위로 쪼개 커밋하고 origin(내 포크)의 내 브랜치로 push한다. "커밋해줘", "커밋하고 올려줘", "github에 올려줘", "push해줘" 같은 표현이 나오면 이 스킬을 사용한다. co-author 는 절대 붙이지 않는다.
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git branch:*), Bash(git remote:*), Bash(git rev-parse:*), Read, Glob, Grep
---

# /gh-commit — 작업 단위 커밋 + 내 포크로 push

이 레포 전용 커밋 스킬. 전역 `/commit`과 달리 **이 레포의 fork·브랜치 구조를 알고 있고, push까지 책임진다.**

## 이 레포의 전제 (매번 다시 확인하지 말 것, 대신 어긋나면 멈출 것)

| 항목 | 값 |
|---|---|
| `origin` | `https://github.com/guesung/my-claude-code-os.git` — **내 포크. push는 항상 여기로** |
| `upstream` | `https://github.com/next-step/my-claude-code-os.git` — **원본. push 권한 없음** |
| 작업 브랜치 | `guesung` (= 내 github 아이디). 미션 규칙상 PR도 이 브랜치 대상 |
| 커밋 메시지 | 한국어 + conventional prefix (`docs:`, `feat:`, `fix:`, `chore:`) |

## 동작

### 1. 사전 점검 (하나라도 걸리면 커밋하지 말고 사용자에게 물을 것)

```bash
git status --short
git branch --show-current
git remote -v
git log --oneline -5
git diff            # unstaged
git diff --staged   # staged
```

- **현재 브랜치가 `main`이면 커밋하지 않는다.** `guesung` 브랜치로 옮길지 먼저 묻는다.
- **`origin`이 `guesung/my-claude-code-os`가 아니면 멈춘다.** 포크가 아닌 원본을 origin으로 잡고 있다는 뜻이고, 그대로 push하면 실패하거나 다른 수강생 브랜치를 건드린다.
- 커밋할 변경이 없으면 그 사실만 보고하고 종료한다.

### 2. 작업 단위로 분리

- 파일/디렉터리 단위가 아니라 **의도 단위**로 묶는다.
- 이 레포 기준 흔한 경계: `docs/` 설계 문서 변경 / `.claude/` OS 자산(스킬·에이전트) 추가 / `CLAUDE.md` 지침 변경 — 셋이 섞여 있으면 나눈다.
- 변경이 단일 주제면 커밋 하나로 끝낸다. 억지로 쪼개지 않는다.
- 사용자가 `$ARGUMENTS`로 "하나로 묶어줘" 같은 지시를 줬으면 그것을 우선한다.

### 3. 커밋

각 단위마다:

- 해당 단위의 파일만 **명시적으로** 스테이징한다. `git add -A`, `git add .` **금지**.
- 메시지는 HEREDOC으로 전달한다.
- 형식:

```
<타입>: <무엇을 왜 바꿨는지 한 줄>

(선택) 보충 설명 1–2 문장
```

타입은 기존 로그를 따른다 — `docs`(설계/기록 문서), `feat`(OS 기능·스킬·에이전트 추가), `fix`, `chore`, `refactor`.

### 4. push

```bash
git push origin HEAD        # upstream이 이미 설정된 경우
git push -u origin HEAD     # 이 브랜치의 첫 push인 경우
```

- **반드시 `origin`.** `git push upstream ...` 은 어떤 경우에도 실행하지 않는다.
- 리모트가 앞서 있어 거절되면 **force하지 말고** 멈춘 뒤, 사용자에게 `git pull --rebase` 여부를 묻는다.

### 5. 보고

커밋 해시 + 메시지 목록, push된 브랜치, 그리고 **다음 액션 한 줄**(예: "PR은 `/guesung:pr`로 올리면 됩니다")을 요약한다.

## 엄격한 금지 사항

- **co-author / `Co-Authored-By` trailer 추가 금지.**
- `Generated with Claude Code`, `🤖` 같은 생성 표식 추가 금지.
- `--force`, `--force-with-lease` 금지 (사용자가 명시적으로 요청한 경우 제외).
- `--no-verify`, `--no-gpg-sign` 등 훅 우회 금지.
- `--amend`는 사용자가 명시적으로 요청했을 때만. 기본은 항상 새 커밋.
- `.env`, 자격증명, 대용량 바이너리 커밋 금지.
- `upstream`으로의 push 금지.

## 설계 의도 (이 레포는 OS 실습 레포이므로 남겨둔다)

- **push까지 한 스킬에 넣고 PR은 뺐다.** 커밋·push는 되돌리기 쉽지만 PR은 사람에게 노출되는 경계다. 자동화 범위를 "되돌릴 수 있는 데까지"로 끊었다.
- **fork 구조를 스킬에 하드코딩했다.** 매번 탐색시키면 토큰도 쓰고 판단도 흔들린다. 대신 전제가 깨졌을 때 멈추는 가드를 넣어, 하드코딩이 틀렸을 때 조용히 사고 치는 대신 소리 나게 만들었다.
- **`git add -A`를 금지했다.** 작업 단위 분리가 이 스킬의 존재 이유인데, 전체 add는 그 의도를 한 줄로 무너뜨린다.

## 인자

`$ARGUMENTS` — 커밋 분할 방식·메시지 톤에 대한 추가 지시 (선택).
예: `/gh-commit 하나로 묶어줘`, `/gh-commit docs만 먼저`
