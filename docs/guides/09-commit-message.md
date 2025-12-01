# 커밋 메시지 규칙

## Conventional Commits

이 프로젝트는 [Conventional Commits](https://www.conventionalcommits.org/) 규칙을 따릅니다.

## 메시지 형식

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 구성 요소

| 요소 | 필수 | 설명 |
|------|------|------|
| `type` | ✅ | 커밋 종류 |
| `scope` | ❌ | 변경 범위 (도메인, 모듈 등) |
| `subject` | ✅ | 짧은 설명 |
| `body` | ❌ | 상세 설명 |
| `footer` | ❌ | GitHub Issue 참조, Breaking Changes 등 |

## 허용 타입

| 타입 | 설명 | 예시 |
|------|------|------|
| `feat` | 새로운 기능 | `feat(users): 사용자 생성 API 추가` |
| `fix` | 버그 수정 | `fix(auth): 토큰 만료 처리 버그 수정` |
| `docs` | 문서 변경 | `docs: README 업데이트` |
| `style` | 코드 포맷팅 (동작 변경 없음) | `style: black 포맷팅 적용` |
| `refactor` | 리팩토링 | `refactor(users): 서비스 레이어 분리` |
| `perf` | 성능 개선 | `perf(db): 쿼리 최적화` |
| `test` | 테스트 추가/수정 | `test(users): 사용자 생성 단위 테스트 추가` |
| `build` | 빌드 시스템/외부 의존성 변경 | `build: Poetry 의존성 업데이트` |
| `ci` | CI 설정 변경 | `ci: GitHub Actions 워크플로우 추가` |
| `chore` | 기타 변경 | `chore: .gitignore 업데이트` |
| `revert` | 커밋 되돌리기 | `revert: feat(users) 커밋 되돌리기` |

## 규칙

### 제목 (Subject)

| 규칙 | 제한 |
|------|------|
| 최대 길이 | 72자 |
| 끝 문자 | 마침표(.) 사용 금지 |
| 언어 | 한글 또는 영어 (프로젝트 내 일관성 유지) |

### 본문 (Body)

| 규칙 | 제한 |
|------|------|
| 줄당 최대 길이 | 100자 |
| 제목과의 구분 | 빈 줄 필수 |

## 예시

### 기본 (제목만)

```
feat(users): 사용자 목록 페이지네이션 추가
```

### 본문 포함

```
feat(users): 사용자 목록 페이지네이션 추가

- PageParams 의존성을 사용한 페이지네이션 구현
- 기본 페이지 크기 20으로 설정
- 총 개수와 함께 응답
```

### Breaking Change

```
feat(api)!: API 응답 형식 변경

기존 응답 형식에서 통일된 APIResponse 형식으로 변경

BREAKING CHANGE: 모든 API 응답이 {code, message, data} 형식으로 변경됨
```

### Issue 참조

```
fix(auth): 로그인 실패 시 에러 메시지 수정

Closes #123
```

### 여러 Issue 참조

```
feat(users): 사용자 프로필 기능 추가

- 프로필 조회 API
- 프로필 수정 API

Closes #45
Refs #12, #34
```

### Footer 키워드

GitHub Issue와 연동할 때 사용하는 키워드입니다.

| 키워드 | 설명 |
|--------|------|
| `Closes #123` | 이슈 자동 종료 |
| `Fixes #123` | 버그 이슈 자동 종료 |
| `Resolves #123` | 이슈 자동 종료 |
| `Refs #123` | 이슈 참조 (종료하지 않음) |
| `Related to #123` | 관련 이슈 참조 |

## 잘못된 예시

```bash
# ❌ 타입 없음
사용자 기능 추가

# ❌ 마침표 사용
feat: 사용자 생성 API 추가.

# ❌ 제목 너무 김
feat(users): 사용자 생성, 수정, 삭제, 조회 API를 추가하고 관련 테스트 코드도 함께 작성함

# ❌ 제목과 본문 사이 빈 줄 없음
feat(users): 사용자 생성 API 추가
상세 설명입니다.
```

## Git Hooks

커밋 시 자동으로 메시지 형식이 검증됩니다.

### 훅 설치

```bash
poetry run pre-commit install --hook-type commit-msg
```

### 검증 실패 시

```
❌ 커밋 메시지 검증 실패:

  • 제목 형식이 올바르지 않습니다.
  현재: 잘못된 커밋 메시지
  형식: <type>(<scope>): <subject>
  허용 타입: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert
  예시: feat(users): 사용자 생성 API 추가

──────────────────────────────────────────────────
📝 Conventional Commits 형식을 따라주세요:
   <type>(<scope>): <subject>

   [optional body]
──────────────────────────────────────────────────
```

## Commitizen 사용 (선택)

대화형으로 커밋 메시지를 작성할 수 있습니다.

```bash
# 대화형 커밋
poetry run cz commit

# 또는
poetry run cz c
```
