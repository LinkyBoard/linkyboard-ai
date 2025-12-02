# 서비스 요구사항

서비스 기능 요구사항 및 API 스펙 문서를 관리하는 폴더입니다.

---

## 문서 목록

| 문서 | 설명 | 상태 |
| ---- | ---- | ---- |
| [user-api-spec.md](./user-api-spec.md) | User 도메인 API 요구사항 정의서 | ✅ 완료 |
| [content-api-spec.md](./content-api-spec.md) | Content 도메인 API 요구사항 정의서 (CRUD/동기화) | ✅ 완료 |
| [ai-api-spec.md](./ai-api-spec.md) | AI 도메인 API 요구사항 정의서 (요약/검색/임베딩/사용량) | ✅ 완료 |
| [topic-board-api-spec.md](./topic-board-api-spec.md) | Topic Board 도메인 API 요구사항 정의서 (오케스트레이션) | ✅ 완료 |
| [orchestration-spec.md](./orchestration-spec.md) | AI 오케스트레이션 요구사항 정의서 (멀티에이전트) | ✅ 완료 |

---

## 도메인 관계도

```
┌─────────────────┐                    ┌─────────────────┐
│    Contents     │◀───references─────│   Topic Board   │
│   (CRUD/동기화)  │                    │ (오케스트레이션)  │
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         │ uses                                 │ uses
         ▼                                      ▼
┌─────────────────────────────────────────────────────────┐
│                          AI                              │
│                (요약/검색/임베딩/개인화)                   │
└─────────────────────────────────────────────────────────┘
```

---

## API 스펙 문서 작성 가이드

### 문서 구조

API 스펙 문서는 다음 구조를 따릅니다:

```
1. 개요
   - 도메인 설명
   - 관련 API 그룹
   - 연동 시스템 개요
   - 프로젝트 구조 참조

2. 비즈니스 요구사항
   - 기능 요구사항 (ID, 요구사항, 우선순위, 구현 대상 API)
   - 비기능 요구사항 (응답 시간, 처리량, 일관성 등)

3. 데이터 모델
   - 테이블 스키마 (SQL)
   - 모델 구현 지시사항
   - 스키마 구현 지시사항
   - 마이그레이션 지시사항

4. API 명세
   - 각 엔드포인트별:
     - Request (HTTP Method, URL, Parameters/Body)
     - Response (성공/에러 응답 예시)
     - 동작 규칙
     - 구현 지시사항 (Router, Service, Repository)

5. 에러 처리
   - HTTP 상태 코드
   - 에러 코드 정의
   - 에러 응답 형식

6. 도메인 정책
   - 필수/권장 동작 시점
   - 재시도 정책

7. 보안
   - 인증 방식
   - 구현 지시사항

8. 로깅
   - 구현 지시사항
   - 로깅 대상

9. 테스트
   - 테스트 파일 구조
   - 테스트 시나리오

10. 추가 고려사항
    - 데이터 정합성 (멱등성, 동시성)
    - 확장성

11. 구현 체크리스트
    - 사전 작업
    - 필수 구현
    - 테스트
    - 권장 구현

12. 버전 히스토리
```

### 필수 포함 내용

| 섹션 | 필수 내용 |
| ---- | --------- |
| API 명세 | Request/Response 예시, 에러 케이스, 구현 지시사항 |
| 데이터 모델 | SQL 스키마, SQLAlchemy 모델 지시사항 |
| 에러 처리 | 에러 코드 Enum, 예외 클래스 정의 |
| 보안 | 인증 방식 및 적용 범위 |
| 구현 체크리스트 | 구현해야 할 파일 및 메서드 목록 |

### 작성 원칙

1. **코드 예시 없음**: 구현 지시사항만 제공, 실제 코드는 작성하지 않음
2. **구체적인 지시**: Router/Service/Repository 각 계층별 메서드 시그니처 명시
3. **프로젝트 가이드 참조**: `docs/guides/` 문서와 일관성 유지
4. **응답 형식 통일**: `APIResponse[T]`, `ListAPIResponse[T]` 사용

### 파일 네이밍

```
{domain}-api-spec.md
```

예시:
- `user-api-spec.md`
- `bookmark-api-spec.md`
- `recommendation-api-spec.md`

---

## 관련 문서

- [프로젝트 구조](../guides/01-project-structure.md)
- [코딩 컨벤션](../guides/02-coding-conventions.md)
- [API 응답 형식](../guides/03-api-response.md)
- [예외 처리](../guides/04-exception-handling.md)
- [새 도메인 추가 가이드](../guides/08-new-domain-guide.md)
