# User 도메인 API 요구사항 정의서

## 1. 개요

User 도메인은 LinkyBoard AI 서비스의 사용자 정보 및 상태 관리를 담당합니다.
Spring Boot 메인 서버에서 전달되는 사용자 정보를 기반으로, AI 서비스 내부에서 사용하는 사용자 엔티티를 생성·갱신·비활성화합니다.

본 문서의 API는 Spring Boot – AI 서비스 간 사용자 연동의 기준 스펙입니다.

### 1.1 관련 API 그룹

| API 그룹  | Prefix          | 설명                                   |
| --------- | --------------- | -------------------------------------- |
| Users API | `/api/v1/users` | 사용자 생성/조회/업데이트/비활성화/목록 조회 |

※ 과거에 사용하던 `/user-sync` 계열 레거시 엔드포인트는 폐기하며, 모든 연동은 `/api/v1/users`를 기준으로 합니다.

### 1.2 Spring Boot 연동 어댑터 개요

* Spring Boot 서버 내부에 `UserSyncClient`(가칭) 어댑터를 두고, 이 어댑터가 항상 `/api/v1/users`를 호출합니다.
* 역할
  * 사용자 정보가 없으면 생성
  * 이미 존재하면 변경된 내용을 업데이트
  * 탈퇴/복구 시 활성 상태 변경
* API 레벨에서는 이를 **Upsert 동작**으로 정의합니다.

### 1.3 프로젝트 구조 참조

Users 도메인은 `app/domains/users/` 디렉토리에 위치하며, 아래 파일들로 구성됩니다:

| 파일             | 역할                            |
| ---------------- | ------------------------------- |
| `models.py`      | SQLAlchemy User 모델 정의       |
| `schemas.py`     | Pydantic 요청/응답 스키마 정의  |
| `repository.py`  | 데이터 접근 계층 (CRUD 로직)    |
| `service.py`     | 비즈니스 로직 (Upsert, 조회 등) |
| `router.py`      | API 엔드포인트 정의             |
| `exceptions.py`  | 도메인 예외 정의                |

---

## 2. 비즈니스 요구사항

### 2.1 기능 요구사항

| ID      | 요구사항                                                 | 우선순위 | 구현 대상 API               |
| ------- | -------------------------------------------------------- | -------- | --------------------------- |
| USR-001 | Spring Boot 서버에서 사용자 생성 시 AI 서비스로 자동 동기화 | 필수     | `POST /api/v1/users`        |
| USR-002 | 사용자 Soft Delete (`deleted_at` 방식)                   | 필수     | `DELETE /api/v1/users/{id}` |
| USR-003 | 특정 사용자의 동기화 상태 조회                           | 필수     | `GET /api/v1/users/{id}`    |
| USR-004 | 사용자 정보는 물리 삭제 대신 Soft Delete로 관리          | 필수     | Users 도메인 전체           |
| USR-005 | 다수 사용자 일괄 동기화 지원                             | 필수     | `POST /api/v1/users/bulk`   |

### 2.2 비기능 요구사항

| ID         | 요구사항           | 목표값                       |
| ---------- | ------------------ | ---------------------------- |
| USR-NF-001 | API 응답 시간      | < 200ms                      |
| USR-NF-002 | 동시 동기화 처리량 | 100 req/s                    |
| USR-NF-003 | 데이터 일관성      | Spring Boot 기준 최종 일관성 |

---

## 3. 데이터 모델

### 3.1 Users 테이블

```sql
users (
    id           BIGINT      PRIMARY KEY,   -- Spring Boot 사용자 ID (자동 증가 아님!)
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at   TIMESTAMP WITH TIME ZONE,
    deleted_at   TIMESTAMP WITH TIME ZONE,  -- Soft Delete용 (NULL이면 활성)
    last_sync_at TIMESTAMP WITH TIME ZONE
);

-- Soft Delete 쿼리 최적화를 위한 부분 인덱스
CREATE INDEX idx_users_active ON users (id) WHERE deleted_at IS NULL;
```

### 3.2 모델 구현 지시사항

`app/domains/users/models.py` 파일을 새로 작성합니다:

* **id 컬럼**: `autoincrement` 없이 Spring Boot에서 제공하는 PK 사용
* **타임스탬프 컬럼**:
  * `created_at`: `DateTime(timezone=True)`, `server_default=func.now()`, NOT NULL
  * `updated_at`: `DateTime(timezone=True)`, `onupdate=func.now()`, nullable
  * `deleted_at`: `DateTime(timezone=True)`, nullable - Soft Delete용
  * `last_sync_at`: `DateTime(timezone=True)`, nullable

### 3.3 스키마 구현 지시사항

`app/domains/users/schemas.py` 파일을 새로 작성합니다:

* **UserSync**: Upsert 요청용 스키마 (id: int)
* **UserBulkSync**: 벌크 Upsert 요청용 스키마 (users: list[UserSync])
* **UserResponse**: 응답용 스키마 (id, created_at, updated_at, deleted_at, last_sync_at)
* **BulkSyncResponse**: 벌크 동기화 응답용 스키마 (total, created, updated, restored)

### 3.4 Soft Delete 데이터 관리

| 항목        | 정책                                                     |
| ----------- | -------------------------------------------------------- |
| 데이터 보관 | `deleted_at` 기준 90일 경과 후 물리 삭제 배치            |
| 인덱스      | `deleted_at IS NULL` 조건 쿼리 최적화를 위한 부분 인덱스 |
| 복구 정책   | 계정 복구 시 `deleted_at`을 `NULL`로 초기화              |

### 3.5 마이그레이션 지시사항

기존 `migrations/versions/` 디렉토리의 users 테이블 관련 마이그레이션 파일을 삭제하고 새로 생성합니다:

```bash
# 기존 마이그레이션 삭제
rm migrations/versions/*_create_users_table.py

# 새 마이그레이션 생성
make migrate-create msg="create_users_table_v2"
make migrate
```

---

## 4. API 명세

* Prefix: `/api/v1/users`
* Tags: `users`
* Router 파일: `app/domains/users/router.py`

AI 서비스에서 관리하는 사용자 리소스에 대한 표준 REST API입니다.

---

### 4.1 사용자 조회

특정 사용자 정보를 조회합니다.

#### Request

```http
GET /api/v1/users/{user_id}
```

| Parameter | Type    | Required | Description                      |
| --------- | ------- | -------- | -------------------------------- |
| user_id   | integer | ✅       | 조회할 사용자 ID (Spring Boot PK) |

#### Response

`APIResponse[UserResponse]` 형태로 응답합니다.

| Field        | Type           | Description                    |
| ------------ | -------------- | ------------------------------ |
| id           | integer        | 사용자 ID                      |
| created_at   | datetime       | 생성 시간                      |
| updated_at   | datetime\|null | 수정 시간                      |
| deleted_at   | datetime\|null | 삭제 시간 (NULL이면 활성 상태) |
| last_sync_at | datetime\|null | 마지막 동기화 시간             |

```json
{
  "success": true,
  "message": "사용자 정보를 조회했습니다.",
  "data": {
    "id": 123,
    "created_at": "2025-08-18T07:06:48.215149+00:00",
    "updated_at": null,
    "deleted_at": null,
    "last_sync_at": "2025-08-18T07:06:48.222178+00:00"
  }
}
```

#### Error

* `404 Not Found` : 사용자가 존재하지 않는 경우

```json
{
  "success": false,
  "message": "사용자를 찾을 수 없습니다.",
  "error": {
    "code": "USER_NOT_FOUND",
    "message": "사용자를 찾을 수 없습니다.",
    "detail": {
      "user_id": 123
    }
  }
}
```

#### 구현 지시사항

* **Router**: `@router.get("/{user_id}", response_model=APIResponse[UserResponse])`
* **Service**: `get_user(user_id: int) -> User` - 존재하지 않으면 `UserNotFoundException` 발생
* **Repository**: `get_by_id(user_id: int) -> Optional[User]`

---

### 4.2 사용자 생성/수정 (Upsert / 동기화용)

Spring Boot에서 가입, 정보 변경, 계정 복구 등 모든 "사용자 정보 변경" 상황에서 호출하는 동기화 엔드포인트입니다.
존재하지 않으면 생성하고, 존재하면 업데이트합니다.

#### Request

```http
POST /api/v1/users
Content-Type: application/json
```

| Field | Type    | Required | Description                |
| ----- | ------- | -------- | -------------------------- |
| id    | integer | ✅       | 사용자 ID (Spring Boot PK) |

```json
{
  "id": 123
}
```

#### 동작 규칙

* 존재하지 않는 ID:
  * 새 사용자 레코드를 생성
  * `created_at`, `last_sync_at` 설정
* 이미 존재하는 ID (삭제되지 않은 경우):
  * `updated_at`, `last_sync_at` 갱신
* 삭제된 사용자 복구 (`deleted_at`이 NOT NULL인 경우):
  * `deleted_at`을 `NULL`로 초기화
  * `updated_at`, `last_sync_at` 갱신

#### Response

`APIResponse[UserResponse]` 형태로 응답합니다. (HTTP 201 Created)

```json
{
  "success": true,
  "message": "사용자가 동기화되었습니다.",
  "data": {
    "id": 123,
    "created_at": "2025-08-18T07:06:48.215149+00:00",
    "updated_at": null,
    "deleted_at": null,
    "last_sync_at": "2025-08-18T07:06:48.222178+00:00"
  }
}
```

#### 구현 지시사항

* **Router**: `@router.post("", response_model=APIResponse[UserResponse], status_code=201)`
* **Service**: `upsert_user(user_data: UserSync) -> User` - Upsert 로직 구현
  * 내부에서 `repository.get_by_id()` 호출하여 존재 여부 확인
  * 존재하면 `repository.update()`, 없으면 `repository.create()` 호출
  * `last_sync_at`은 `func.now()` 또는 `datetime.now(timezone.utc)`로 설정
* **Repository**:
  * `get_by_id(user_id: int) -> Optional[User]`
  * `create(user: User) -> User`
  * `update(user: User) -> User`
* **Schema**: `UserSync` 스키마 정의 필요 (id: int)

---

### 4.3 사용자 비활성화 (Soft Delete)

사용자 탈퇴, 차단 등으로 더 이상 AI 서비스에서 사용하지 않는 상태로 변경합니다.
물리 삭제는 하지 않고 `deleted_at` 타임스탬프를 설정하는 Soft Delete로 처리합니다.

#### Request

```http
DELETE /api/v1/users/{user_id}
```

| Parameter | Type    | Required | Description    |
| --------- | ------- | -------- | -------------- |
| user_id   | integer | ✅       | 삭제할 사용자 ID |

#### 내부 처리

* `deleted_at` 값을 현재 시간으로 설정
* `updated_at` 갱신

#### Response

* `204 No Content` : 성공적으로 삭제됨 (응답 본문 없음)

#### Error

* `404 Not Found` : 사용자가 존재하지 않는 경우

#### 구현 지시사항

* **Router**: `@router.delete("/{user_id}", status_code=204)` - `return None`
* **Service**: `delete_user(user_id: int) -> None`
  * 사용자 조회 후 존재하지 않으면 `UserNotFoundException` 발생
  * `deleted_at = datetime.now(timezone.utc)` 설정 후 저장
* **Repository**: `soft_delete(user: User) -> User`

※ 계정 복구 시에는 `POST /api/v1/users`로 `{"id": 123}` 요청을 보내면 `deleted_at`이 `NULL`로 초기화됩니다.

---

### 4.4 사용자 리스트 조회 (관리자/내부용)

관리자 대시보드 및 운영/배치 작업을 위한 내부용 API입니다.
일반 비즈니스 로직에서는 사용하지 않도록 문서 및 코드 레벨에서 명시합니다.

#### Request

```http
GET /api/v1/users
```

| Query           | Type    | Required | Description                           |
| --------------- | ------- | -------- | ------------------------------------- |
| include_deleted | boolean | ❌       | 삭제된 사용자 포함 여부 (기본값: false) |
| page            | integer | ❌       | 페이지 번호 (기본값: 1)               |
| size            | integer | ❌       | 페이지 크기 (기본값: 20, 최대: 100)   |

예시:

```http
GET /api/v1/users?include_deleted=false&page=1&size=50
```

#### Response

`ListAPIResponse[UserResponse]` 형태로 응답합니다.

```json
{
  "success": true,
  "message": "사용자 목록을 조회했습니다.",
  "data": [
    {
      "id": 123,
      "created_at": "2025-08-18T07:06:48.215149+00:00",
      "updated_at": null,
      "last_sync_at": "2025-08-18T07:06:48.222178+00:00",
      "deleted_at": null
    }
  ],
  "meta": {
    "total": 1,
    "page": 1,
    "size": 50,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

#### 구현 지시사항

* **Router**: `@router.get("", response_model=ListAPIResponse[UserResponse])`
  * `PageParams = Depends()`를 통해 페이지네이션 파라미터 주입
  * `include_deleted: bool = False` 쿼리 파라미터 추가
* **Service**: `get_users(page: int, size: int, include_deleted: bool) -> tuple[Sequence[User], int]`
* **Repository**:
  * `get_list(skip: int, limit: int, include_deleted: bool) -> Sequence[User]`
  * `count(include_deleted: bool) -> int`
  * 기본적으로 `deleted_at IS NULL` 조건 적용, `include_deleted=True`면 전체 조회
* 응답 생성 시 `create_list_response()` 팩토리 함수 사용

---

### 4.5 벌크 사용자 동기화

다수의 사용자를 한 번에 동기화하는 API입니다. 정기 배치 동기화 또는 서비스 재시작 후 전체 사용자 동기화에 사용됩니다.

#### Request

```http
POST /api/v1/users/bulk
Content-Type: application/json
```

| Field | Type         | Required | Description                     |
| ----- | ------------ | -------- | ------------------------------- |
| users | list[object] | ✅       | 동기화할 사용자 목록 (최대 1000건) |

```json
{
  "users": [
    { "id": 123 },
    { "id": 456 },
    { "id": 789 }
  ]
}
```

#### 동작 규칙

* 각 사용자에 대해 개별 Upsert와 동일한 로직 적용
* 트랜잭션 단위로 처리 (전체 성공 또는 전체 실패)
* 최대 1000건까지 허용, 초과 시 `400 Bad Request`

#### Response

`APIResponse[BulkSyncResponse]` 형태로 응답합니다. (HTTP 201 Created)

```json
{
  "success": true,
  "message": "벌크 동기화가 완료되었습니다.",
  "data": {
    "total": 3,
    "created": 1,
    "updated": 2,
    "restored": 0
  }
}
```

#### 구현 지시사항

* **Router**: `@router.post("/bulk", response_model=APIResponse[BulkSyncResponse], status_code=201)`
* **Service**: `bulk_upsert_users(users: list[UserSync]) -> BulkSyncResult`
  * 트랜잭션 내에서 각 사용자에 대해 upsert 로직 수행
  * 생성/수정/복구 건수를 카운트하여 반환
* **Repository**: `bulk_upsert(users: list[User]) -> list[User]`
* **Schema**:
  * `UserBulkSync`: 요청용 스키마 (users: list[UserSync], max 1000)
  * `BulkSyncResponse`: 응답용 스키마 (total, created, updated, restored)

---

## 5. 에러 처리

### 5.1 HTTP 상태 코드

| Status Code | Description                              |
| ----------- | ---------------------------------------- |
| 200         | 조회/수정 성공                           |
| 201         | 생성 성공                                |
| 204         | 삭제 성공 (본문 없음)                    |
| 400         | 잘못된 요청 (필수 필드 누락, 잘못된 데이터) |
| 401         | 인증 실패 (API Key 오류)                 |
| 404         | 사용자를 찾을 수 없음                    |
| 422         | 유효성 검증 실패                         |
| 500         | 서버 내부 오류                           |

### 5.2 에러 코드 정의

`app/domains/users/exceptions.py`에 에러 코드 Enum 및 예외 클래스를 정의합니다.

| Error Code             | Description        | HTTP Status |
| ---------------------- | ------------------ | ----------- |
| `USER_NOT_FOUND`       | 사용자를 찾을 수 없음 | 404         |
| `USER_ALREADY_DELETED` | 이미 삭제된 사용자 | 409         |

### 5.3 에러 응답 형식

프로젝트 표준 에러 응답 형식을 따릅니다:

```json
{
  "success": false,
  "message": "사용자를 찾을 수 없습니다.",
  "error": {
    "code": "USER_NOT_FOUND",
    "message": "사용자를 찾을 수 없습니다.",
    "detail": {
      "user_id": 123
    }
  }
}
```

#### 구현 지시사항

* **exceptions.py**: `UserErrorCode` Enum 정의
* **exceptions.py**: `UserNotFoundException` 클래스 정의 (`NotFoundException` 상속)
* Service 계층에서 예외 발생, Router에서는 별도 예외 처리 불필요 (전역 핸들러 사용)

---

## 6. 동기화 정책

### 6.1 필수 동기화 시점

| 시점        | 설명                   | 호출 API                    |
| ----------- | ---------------------- | --------------------------- |
| 사용자 가입 | 새로운 사용자가 생성될 때 | `POST /api/v1/users`        |
| 사용자 탈퇴 | 탈퇴 시                | `DELETE /api/v1/users/{id}` |
| 계정 복구   | 탈퇴 계정 복구 시      | `POST /api/v1/users`        |

Spring Boot 측 어댑터에서 위 API들을 래핑하여 "동기화" 기능으로 제공합니다.

### 6.2 권장 동기화 시점

| 시점          | 설명                                                          |
| ------------- | ------------------------------------------------------------- |
| 정기 배치     | 일 1회 전체 사용자 정보를 스캔하여 누락/불일치 사용자에 대해 재동기화 |
| 서비스 재시작 | AI 서비스 재배포/재시작 후, Spring Boot에서 활성 사용자 재동기화 |

### 6.3 재시도 정책 권장사항

| 오류 유형            | 정책                              |
| -------------------- | --------------------------------- |
| 네트워크 오류(5xx)   | 지수 백오프로 최대 3회 재시도     |
| 클라이언트 오류(4xx) | 재시도하지 않고 로그 기록 및 모니터링 |
| 타임아웃             | API 호출 타임아웃 30초 설정 권장  |

---

## 7. 보안

Private subnet 환경이지만 Defense in Depth 원칙에 따라 **API Key 인증**을 적용합니다.

### 7.1 인증 방식

| 항목        | 내용                             |
| ----------- | -------------------------------- |
| 인증 방식   | API Key (Header 기반)            |
| Header 이름 | `X-Internal-Api-Key`             |
| 환경변수    | `INTERNAL_API_KEY`               |
| 적용 범위   | 모든 `/api/v1/users` 엔드포인트 |

### 7.2 구현 지시사항

* **환경변수**: `.env`에 `INTERNAL_API_KEY` 추가 (32자 이상 랜덤 문자열)
* **Config**: `app/core/config.py`의 `Settings`에 `internal_api_key: str` 필드 추가
* **Dependency**: `app/core/dependencies.py`에 API Key 검증 함수 구현
* **Router**: 각 엔드포인트에 `Depends(verify_internal_api_key)` 적용
* **Spring Boot**: `UserSyncClient`에서 요청 시 `X-Internal-Api-Key` 헤더 포함

### 7.3 키 관리

| 항목        | 권장사항                                |
| ----------- | --------------------------------------- |
| 키 생성     | `openssl rand -hex 32` 또는 동등한 방법 |
| 키 저장     | 환경변수 또는 AWS Secrets Manager 등    |
| 키 로테이션 | 정기적 로테이션 시 서비스 재시작으로 적용 |

---

## 8. 로깅

프로젝트에 구현된 로깅 미들웨어(`app/core/middlewares/logging.py`)와 요청 ID 컨텍스트(`app/core/middlewares/context.py`)를 활용합니다.

### 8.1 구현 지시사항

* **요청 추적**: `LoggingMiddleware`가 자동으로 `X-Request-ID` 헤더를 처리
  * 클라이언트가 전송한 `X-Request-ID`가 있으면 해당 값 사용
  * 없으면 UUID 자동 생성
  * 응답 헤더에 `X-Request-ID`, `X-Process-Time` 자동 포함
* **Service 계층 로깅**: `get_logger(__name__)`을 통해 로거 획득 후 주요 이벤트 로깅
  * `get_request_id()` 함수로 현재 요청 ID를 로그에 포함
  * 사용자 생성/삭제/복구 시 INFO 레벨 로깅
  * 예외 발생 시 ERROR 레벨 로깅

### 8.2 로깅 대상

| 로깅 대상   | 로그 레벨 | 포함 정보                                    |
| ----------- | --------- | -------------------------------------------- |
| 사용자 생성 | INFO      | request_id, user_id, action="created"        |
| 사용자 삭제 | INFO      | request_id, user_id, action="deleted"        |
| 사용자 복구 | INFO      | request_id, user_id, action="restored"       |
| 벌크 동기화 | INFO      | request_id, user_count, action="bulk_synced" |
| 예외 발생   | ERROR     | request_id, user_id, error_code, error_message |

---

## 9. 테스트

### 9.1 테스트 파일 구조

| 테스트 유형 | 파일 위치                               | 범위                                                         |
| ----------- | --------------------------------------- | ------------------------------------------------------------ |
| 단위 테스트 | `tests/unit/domains/test_users.py`      | Service 계층의 비즈니스 로직 (Upsert 조건 분기, Soft Delete 등) |
| 통합 테스트 | `tests/integration/test_users_api.py`   | API 엔드포인트 + DB 연동 테스트                              |
| E2E 테스트  | `tests/e2e/test_user_sync_scenarios.py` | Spring Boot-AI 서비스 간 실제 동기화 시나리오                |

### 9.2 E2E 테스트 시나리오

1. **사용자 생성 → 조회**: Spring Boot에서 사용자 생성 후 AI 서비스에서 조회 가능 확인
2. **사용자 삭제 → 복구**: 삭제 후 `deleted_at` 설정 확인, 복구 후 `deleted_at` NULL 확인
3. **동시 요청 처리**: 동일 사용자에 대한 동시 Upsert 요청 시 데이터 정합성 확인
4. **목록 조회 필터링**: `include_deleted` 파라미터에 따른 필터링 동작 확인
5. **벌크 동기화**: 다수 사용자 일괄 동기화 후 각 사용자 상태 확인

---

## 10. 추가 고려사항

### 10.1 데이터 정합성

#### 멱등성

Upsert API는 **설계상 자연스럽게 멱등성이 보장**됩니다:

| 요청            | 1차 결과           | 2차 결과 (동일 요청)   |
| --------------- | ------------------ | ---------------------- |
| POST (id=123)   | 생성 또는 업데이트 | 업데이트 (결과 동일)   |
| DELETE (id=123) | deleted_at 설정    | 이미 삭제됨 (결과 동일) |

* PK(`id`) 기준으로 존재 여부를 판단하므로 동일 요청은 동일 결과
* `updated_at`은 갱신되지만 비즈니스 로직에 영향 없음

**Kafka 연동 시 주의사항**: 향후 이벤트 발행 기능 추가 시, **실제 변경이 발생한 경우에만** 이벤트를 발행해야 멱등성이 유지됩니다. 동일 요청에 중복 이벤트가 발행되지 않도록 변경 감지 로직 필요.

#### 동시성

동일 사용자에 대한 동시 요청은 **PostgreSQL UPSERT 구문**으로 처리합니다:

* `INSERT ... ON CONFLICT (id) DO UPDATE` 사용
* DB가 원자적으로 처리하므로 애플리케이션 레벨 락 불필요
* Race condition 없이 안전하게 동작

#### 정합성 검사

| 항목        | 권장사항                                     |
| ----------- | -------------------------------------------- |
| 정기 배치   | Spring Boot-AI 서비스 간 사용자 수 비교 검사 |
| 불일치 처리 | 벌크 동기화 API를 통한 재동기화              |

### 10.2 확장성

| 항목        | 권장사항                                                  |
| ----------- | --------------------------------------------------------- |
| 이벤트 기반 | 향후 메시지 큐(Kafka, RabbitMQ) 기반 비동기 동기화 전환 고려 |
| 캐싱        | 사용자 조회 API에 대한 캐싱 레이어 추가 고려 (Redis)      |

---

## 11. 구현 체크리스트

### 11.1 사전 작업

- [ ] 기존 users 도메인 파일 삭제 (`app/domains/users/` 전체)
- [ ] 기존 마이그레이션 삭제 (`migrations/versions/*_create_users_table.py`)

### 11.2 필수 구현

- [ ] `models.py` - User 모델 새로 작성 (3.2 지시사항 참고)
- [ ] `schemas.py` - UserSync, UserBulkSync, UserResponse, BulkSyncResponse 스키마 정의
- [ ] `exceptions.py` - UserErrorCode, UserNotFoundException 정의
- [ ] `repository.py` - get_by_id, create, update, soft_delete, get_list, count, bulk_upsert 메서드
- [ ] `service.py` - get_user, upsert_user, delete_user, get_users, bulk_upsert_users 메서드
- [ ] `router.py` - 5개 엔드포인트 구현
- [ ] 마이그레이션 - 새 users 테이블 마이그레이션 생성
- [ ] API Key 인증 - `app/core/dependencies.py`에 검증 함수 추가

### 11.3 테스트

- [ ] 단위 테스트 (`tests/unit/domains/test_users.py`)
- [ ] 통합 테스트 (`tests/integration/test_users_api.py`)
- [ ] E2E 테스트 (`tests/e2e/test_user_sync_scenarios.py`)

### 11.4 권장 구현

- [ ] API 문서 확인 (`/docs` 엔드포인트)

---

## 12. 버전 히스토리

| 버전 | 날짜       | 변경 내용       |
| ---- | ---------- | --------------- |
| 1.0  | 2025-12-02 | 최초 문서 작성  |
