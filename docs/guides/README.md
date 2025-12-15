# 개발 가이드

## docs/guides/

프로젝트의 구조와 코드 작성 규칙을 정리한 개발 가이드 문서입니다.

### 목차

| 번호 | 파일명 | 설명 |
|------|--------|------|
| 01 | [프로젝트 구조](./01-project-structure.md) | 디렉토리 구조, 레이어 아키텍처, API 버저닝 |
| 02 | [코딩 컨벤션](./02-coding-conventions.md) | 코드 스타일, 네이밍 규칙, 타입 힌트 |
| 03 | [API 응답 규칙](./03-api-response.md) | 응답 스키마, 상태 코드, Request ID |
| 04 | [예외 처리](./04-exception-handling.md) | 예외 계층 구조, 에러 응답 형식 |
| 05 | [데이터베이스](./05-database.md) | SQLAlchemy 모델, Repository 패턴, 마이그레이션 |
| 06 | [테스트](./06-testing.md) | 테스트 구조, Fixture, 테스트 레벨 |
| 07 | [Docker 및 배포](./07-deployment.md) | Docker 설정, 환경 변수, 배포 가이드 |
| 08 | [신규 도메인 추가 가이드](./08-new-domain-guide.md) | 새 도메인 추가 단계별 가이드 |
| 09 | [커밋 메시지 규칙](./09-commit-message.md) | Conventional Commits, 메시지 형식, Git Hooks |
| 10 | [브랜치 네이밍 규칙](./10-branch-naming.md) | Git Flow, 브랜치 타입, 워크플로우 |

### 빠른 시작

1. **프로젝트 설정**
   ```bash
   poetry install
   cp .env.example .env
   ```

2. **개발 서버 실행**
   ```bash
   make docker-up
   ```

3. **API 문서 확인**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

4. **테스트 실행**
   ```bash
   make test
   ```

### 기술 스택

- **언어**: Python 3.13
- **프레임워크**: FastAPI
- **패키지 관리**: Poetry
- **데이터베이스**: PostgreSQL + SQLAlchemy 2.0 (async)
- **마이그레이션**: Alembic
- **테스트**: pytest + pytest-asyncio
- **컨테이너**: Docker + Docker Compose
- **코드 품질**: black, isort, flake8, mypy, pre-commit
- **커밋 규칙**: Conventional Commits, commitizen
