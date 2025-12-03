# 브랜치 네이밍 규칙

## 브랜치 전략

이 프로젝트는 **Git Flow** 기반의 브랜치 전략을 사용합니다.

## 메인 브랜치

| 브랜치 | 용도 | 보호 |
|--------|------|------|
| `main` | 프로덕션 배포 브랜치 | ✅ Protected |
| `dev` | 개발 통합 브랜치 | ✅ Protected |

## 작업 브랜치 네이밍

### 형식

```
<type>/<issue-number>-<short-description>
```

### 구성 요소

| 요소 | 필수 | 설명 |
|------|------|------|
| `type` | ✅ | 브랜치 종류 (아래 타입 참조) |
| `issue-number` | ✅ | GitHub Issue 번호 |
| `short-description` | ✅ | 간단한 설명 (kebab-case) |

## 브랜치 타입

| 타입 | 설명 | 예시 |
|------|------|------|
| `feature` | 새로운 기능 개발 | `feature/1-user-domain` |
| `fix` | 버그 수정 | `fix/23-login-error` |
| `hotfix` | 긴급 프로덕션 버그 수정 | `hotfix/45-critical-auth-bug` |
| `refactor` | 코드 리팩토링 | `refactor/12-service-layer` |
| `docs` | 문서 작업 | `docs/34-api-docs` |
| `test` | 테스트 추가/수정 | `test/56-unit-tests` |
| `chore` | 기타 작업 (설정, 빌드 등) | `chore/78-docker-setup` |
| `release` | 릴리즈 준비 | `release/1.0.0` |

## 네이밍 규칙

### ✅ 올바른 예시

```bash
feature/1-user-domain
feature/15-add-login-api
fix/23-token-expiry-bug
hotfix/99-security-patch
refactor/42-repository-pattern
docs/7-readme-update
release/1.2.0
```

### ❌ 잘못된 예시

```bash
feature/userDomain          # Issue 번호 없음, camelCase 사용
Feature/1-user-domain       # 대문자 사용
feature/1_user_domain       # underscore 사용
feature/1                   # 설명 없음
user-domain                 # 타입 없음
```

## 브랜치 워크플로우

```
main ─────────────────────────────────────────────► (production)
  │                                        ▲
  │                                        │ merge (release)
  ▼                                        │
dev ──────┬──────────────────────┬─────────┴──────► (development)
          │                      │
          │ branch               │ merge (PR)
          ▼                      │
    feature/1-user-domain ───────┘
```

### 작업 순서

1. **Issue 생성**: GitHub에서 작업할 Issue 생성
2. **브랜치 생성**: `dev`에서 작업 브랜치 생성
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/1-user-domain
   ```
3. **작업 및 커밋**: [커밋 메시지 규칙](./09-commit-message.md) 준수
4. **Push**: 원격 저장소에 Push
   ```bash
   git push -u origin feature/1-user-domain
   ```
5. **PR 생성**: `dev` 브랜치로 Pull Request 생성
6. **코드 리뷰**: 리뷰 후 Merge
7. **브랜치 삭제**: Merge 후 작업 브랜치 삭제

## 릴리즈 브랜치

릴리즈 브랜치는 [Semantic Versioning](https://semver.org/)을 따릅니다.

```
release/<major>.<minor>.<patch>
```

예시:
- `release/1.0.0` - 첫 번째 메이저 릴리즈
- `release/1.1.0` - 기능 추가
- `release/1.1.1` - 버그 수정

## 핫픽스 워크플로우

긴급한 프로덕션 버그는 `main`에서 직접 분기합니다.

```bash
git checkout main
git pull origin main
git checkout -b hotfix/99-critical-bug
# 수정 후
git push -u origin hotfix/99-critical-bug
# main과 dev 모두에 PR 생성
```

## 관련 문서

- [커밋 메시지 규칙](./09-commit-message.md)
- [프로젝트 구조](./01-project-structure.md)
