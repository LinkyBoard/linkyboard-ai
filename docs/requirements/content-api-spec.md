# Content 도메인 API 요구사항 정의서

## 1. 개요

Content 도메인은 LinkyBoard 서비스의 콘텐츠 저장 및 관리를 담당합니다.
웹페이지, YouTube 동영상, PDF 파일의 메타데이터와 원본 데이터를 저장하고 관리합니다.

> **Note**: AI 관련 기능(요약, 검색, 개인화 추천)은 [AI 도메인](./ai-api-spec.md)을 참조하세요.

### 1.1 관련 API 그룹

| API 그룹 | Prefix | 설명 |
| -------- | ------ | ---- |
| Contents API | `/api/v1/contents` | 콘텐츠 동기화/삭제/조회 |

### 1.2 도메인 관계

```
┌─────────────────┐     uses      ┌─────────────────┐
│    Contents     │ ────────────▶ │       AI        │
│   (CRUD/동기화)  │               │   (요약/검색)    │
└─────────────────┘               └─────────────────┘
        │
        │ Sync 시점에 AI 도메인 호출
        │ - 캐시에서 임베딩 복사
        │ - 태그/카테고리 사용 빈도 업데이트
        ▼
```

### 1.3 지원 콘텐츠 타입

| 타입 | 설명 | 원본 저장 |
| ---- | ---- | --------- |
| `webpage` | 웹페이지 | HTML (DB) |
| `youtube` | YouTube 동영상 | 자막 (DB) |
| `pdf` | PDF 문서 | 파일 (S3) |

### 1.4 프로젝트 구조

```
app/domains/contents/
├── __init__.py
├── models.py           # Content 모델
├── schemas.py          # 요청/응답 스키마
├── repository.py       # CRUD 로직
├── service.py          # 비즈니스 로직
├── router.py           # API 엔드포인트
├── exceptions.py       # 도메인 예외
└── utils.py            # 유틸리티 (S3 업로드 등)
```

---

## 2. 비즈니스 요구사항

### 2.1 기능 요구사항

| ID | 요구사항 | 우선순위 | 구현 대상 API |
| -- | -------- | -------- | ------------- |
| CNT-001 | 웹페이지 콘텐츠 동기화 및 저장 | 필수 | `POST /webpage/sync` |
| CNT-002 | YouTube 동영상 메타데이터 동기화 | 필수 | `POST /youtube/sync` |
| CNT-003 | PDF 파일 업로드 및 동기화 | 필수 | `POST /pdf/sync` |
| CNT-004 | 다중 콘텐츠 삭제 (Soft Delete) | 필수 | `DELETE /` |
| CNT-005 | 단일 콘텐츠 조회 | 필수 | `GET /{content_id}` |
| CNT-006 | 콘텐츠 목록 조회 | 필수 | `GET /` |

### 2.2 비기능 요구사항

| ID | 요구사항 | 목표값 |
| -- | -------- | ------ |
| CNT-NF-001 | Sync API 응답 시간 | < 2s |
| CNT-NF-002 | 최대 HTML 파일 크기 | 10MB |
| CNT-NF-003 | 최대 PDF 파일 크기 | 50MB |

---

## 3. 데이터 모델

### 3.1 Contents 테이블

```sql
contents (
    id                 BIGINT       PRIMARY KEY,      -- Spring Boot Content ID
    user_id            BIGINT       NOT NULL,
    content_type       VARCHAR(50)  NOT NULL,         -- webpage / youtube / pdf
    source_url         TEXT,                          -- URL (PDF는 NULL 가능)
    title              VARCHAR(500) NOT NULL,
    summary            TEXT,                          -- 사용자 확정 요약

    -- 원본 데이터
    raw_source         TEXT,                          -- HTML 원본 (웹), 자막 (유튜브), NULL (PDF)
    raw_content        TEXT,                          -- 추출된 텍스트
    extraction_method  VARCHAR(50) DEFAULT 'v1',      -- 추출 방법 버전

    -- PDF 전용
    file_hash          VARCHAR(64),                   -- S3 파일 참조용

    thumbnail          TEXT,
    memo               TEXT,
    tags               TEXT[],                        -- 사용자 확정 태그
    category           VARCHAR(100),                  -- 사용자 확정 카테고리
    processing_status  VARCHAR(50) DEFAULT 'raw',     -- raw / processed / embedded / failed
    created_at         TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at         TIMESTAMP WITH TIME ZONE,
    deleted_at         TIMESTAMP WITH TIME ZONE       -- Soft Delete
);

-- 인덱스
CREATE INDEX idx_contents_user_active ON contents (user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_contents_source_url ON contents (source_url) WHERE source_url IS NOT NULL;
CREATE INDEX idx_contents_type ON contents (user_id, content_type) WHERE deleted_at IS NULL;

-- Full-Text Search용 (AI 도메인에서 사용)
ALTER TABLE contents ADD COLUMN search_vector tsvector;
CREATE INDEX idx_contents_search ON contents USING gin(search_vector);
```

### 3.2 모델 구현 지시사항

`app/domains/contents/models.py`:

* **Content**:
  * `content_type` Enum: `webpage`, `youtube`, `pdf`
  * `processing_status` Enum: `raw`, `processed`, `embedded`, `failed`
  * `deleted_at` Soft Delete

---

## 4. API 명세

* Prefix: `/api/v1/contents`
* Tags: `contents`
* 인증: 모든 API에 `X-Internal-Api-Key` 헤더 필수

---

### 4.1 웹페이지 동기화

사용자가 확정한 메타데이터를 저장합니다.

#### Request

```http
POST /api/v1/contents/webpage/sync
Content-Type: application/json
```

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| content_id | integer | ✅ | Content ID (Spring Boot PK) |
| user_id | integer | ✅ | 사용자 ID |
| url | string | ✅ | 웹페이지 URL |
| content_hash | string | ✅ | HTML 해시 (캐시 조회용) |
| title | string | ✅ | 페이지 제목 |
| summary | string | ❌ | 사용자 확정 요약 |
| tags | list[string] | ❌ | 사용자 확정 태그 |
| category | string | ❌ | 사용자 확정 카테고리 |
| thumbnail | string | ❌ | 썸네일 URL |
| memo | string | ❌ | 사용자 메모 |

#### Response

```json
{
  "success": true,
  "message": "웹페이지가 성공적으로 동기화되었습니다.",
  "data": {
    "content_id": 123
  }
}
```

#### 동작 로직

1. AI 도메인 캐시에서 `extracted_text`, `chunk_embeddings` 가져오기
2. `contents` 테이블에 저장 (Upsert)
3. AI 도메인의 `content_embedding_metadatas`에 임베딩 복사
4. 사용자 요약이 있으면 AI 도메인에 추가 임베딩 생성 요청 (`is_user_summary=true`)
5. AI 도메인의 `user_tag_usage`, `user_category_usage` 업데이트 호출

---

### 4.2 YouTube 동기화

#### Request

```http
POST /api/v1/contents/youtube/sync
Content-Type: application/json
```

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| content_id | integer | ✅ | Content ID |
| user_id | integer | ✅ | 사용자 ID |
| url | string | ✅ | YouTube URL |
| title | string | ✅ | 동영상 제목 |
| summary | string | ❌ | 사용자 확정 요약 |
| tags | list[string] | ❌ | 사용자 확정 태그 |
| category | string | ❌ | 사용자 확정 카테고리 |
| thumbnail | string | ❌ | 썸네일 URL |
| memo | string | ❌ | 사용자 메모 |

#### Response

```json
{
  "success": true,
  "message": "YouTube 동영상이 성공적으로 동기화되었습니다.",
  "data": {
    "content_id": 123
  }
}
```

---

### 4.3 PDF 동기화

#### Request

```http
POST /api/v1/contents/pdf/sync
Content-Type: multipart/form-data
```

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| content_id | integer | ✅ | Content ID |
| user_id | integer | ✅ | 사용자 ID |
| pdf_file | file | ✅ | PDF 파일 |
| title | string | ✅ | PDF 제목 |
| summary | string | ❌ | 사용자 확정 요약 |
| tags | list[string] | ❌ | 사용자 확정 태그 |
| category | string | ❌ | 사용자 확정 카테고리 |
| memo | string | ❌ | 사용자 메모 |

#### Response

```json
{
  "success": true,
  "message": "PDF가 성공적으로 동기화되었습니다.",
  "data": {
    "content_id": 123,
    "file_hash": "abc123..."
  }
}
```

#### 동작 로직

* PDF 파일을 S3에 업로드 (`s3://{bucket}/pdfs/{file_hash}.pdf`)
* `file_hash`로 중복 저장 방지

---

### 4.4 콘텐츠 삭제

#### Request

```http
DELETE /api/v1/contents
Content-Type: application/json
```

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| content_ids | list[integer] | ✅ | 삭제할 Content ID 목록 (최대 100개) |
| user_id | integer | ✅ | 사용자 ID |

#### Response

```json
{
  "success": true,
  "message": "3개의 콘텐츠가 성공적으로 삭제되었습니다.",
  "data": {
    "deleted_count": 3,
    "failed_items": [],
    "total_requested": 3
  }
}
```

#### 동작 로직

* `deleted_at = NOW()`로 Soft Delete
* 소유권 확인 후 삭제
* 최대 100개까지 일괄 삭제

---

### 4.5 단일 콘텐츠 조회

#### Request

```http
GET /api/v1/contents/{content_id}
```

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| content_id | integer | ✅ | Content ID |
| user_id | integer | ✅ | 사용자 ID (Query) |

#### Response

```json
{
  "success": true,
  "message": "콘텐츠 조회 성공",
  "data": {
    "content_id": 123,
    "content_type": "webpage",
    "source_url": "https://example.com/article",
    "title": "AI 기술 동향",
    "summary": "인공지능 기술의 최신 동향...",
    "thumbnail": "https://...",
    "tags": ["AI", "기술"],
    "category": "tech",
    "memo": "나중에 다시 읽기",
    "processing_status": "embedded",
    "created_at": "2024-06-15T10:00:00Z",
    "updated_at": "2024-06-15T12:00:00Z"
  }
}
```

---

### 4.6 콘텐츠 목록 조회

#### Request

```http
GET /api/v1/contents
```

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| user_id | integer | ✅ | 사용자 ID |
| content_type | string | ❌ | 콘텐츠 타입 필터 |
| category | string | ❌ | 카테고리 필터 |
| tags | list[string] | ❌ | 태그 필터 (OR) |
| sort_by | string | ❌ | 정렬 기준: created_at / updated_at (기본: created_at) |
| sort_order | string | ❌ | 정렬 순서: asc / desc (기본: desc) |
| page | integer | ❌ | 페이지 번호 (기본: 1) |
| size | integer | ❌ | 페이지 크기 (기본: 20, 최대: 100) |

#### Response

```json
{
  "success": true,
  "message": "콘텐츠 목록 조회 성공",
  "data": [
    {
      "content_id": 123,
      "content_type": "webpage",
      "source_url": "https://...",
      "title": "AI 기술 동향",
      "summary": "인공지능 기술의...",
      "thumbnail": "https://...",
      "tags": ["AI", "기술"],
      "category": "tech",
      "created_at": "2024-06-15T10:00:00Z"
    }
  ],
  "meta": {
    "total": 45,
    "page": 1,
    "size": 20,
    "total_pages": 3,
    "has_next": true,
    "has_prev": false
  }
}
```

---

## 5. AI 도메인 연동

### 5.1 Sync 시 AI 도메인 호출

```python
# contents/service.py
async def sync_webpage(data: WebpageSyncRequest) -> Content:
    # 1. AI 도메인 캐시에서 데이터 가져오기
    cache_data = await ai_service.get_cache_data(data.content_hash)

    # 2. Content 저장
    content = await repository.upsert_content(
        id=data.content_id,
        user_id=data.user_id,
        raw_content=cache_data.extracted_text,
        # ... 기타 필드
    )

    # 3. AI 도메인에 임베딩 복사 요청
    await ai_service.copy_embeddings_to_content(
        content_id=content.id,
        cache_key=data.content_hash
    )

    # 4. 사용자 요약이 있으면 추가 임베딩 생성
    if data.summary:
        await ai_service.create_user_summary_embedding(
            content_id=content.id,
            summary=data.summary
        )

    # 5. 태그/카테고리 사용 빈도 업데이트
    if data.tags:
        await ai_service.update_tag_usage(data.user_id, data.tags)
    if data.category:
        await ai_service.update_category_usage(data.user_id, data.category)

    return content
```

---

## 6. 에러 처리

### 6.1 에러 코드 정의

| Error Code | Description | HTTP Status |
| ---------- | ----------- | ----------- |
| `CONTENT_NOT_FOUND` | 콘텐츠를 찾을 수 없음 | 404 |
| `FILE_SIZE_EXCEEDED` | 파일 크기 제한 초과 | 400 |
| `DELETE_LIMIT_EXCEEDED` | 삭제 제한 초과 (100개) | 400 |
| `PERMISSION_DENIED` | 콘텐츠 접근 권한 없음 | 403 |
| `S3_UPLOAD_FAILED` | S3 업로드 실패 | 500 |
| `CACHE_NOT_FOUND` | AI 캐시 데이터 없음 (Summarize 먼저 호출 필요) | 400 |
| `INVALID_CONTENT_TYPE` | 잘못된 콘텐츠 타입 | 400 |

---

## 7. 보안

### 7.1 인증

| 항목 | 내용 |
| ---- | ---- |
| 인증 방식 | API Key (Header 기반) |
| Header 이름 | `X-Internal-Api-Key` |
| 환경변수 | `INTERNAL_API_KEY` |
| 적용 범위 | 모든 `/api/v1/contents` 엔드포인트 |

### 7.2 권한 검사

* 모든 API에서 `user_id` 기반 소유권 검사
* 다른 사용자의 콘텐츠 접근 시 `PERMISSION_DENIED`

---

## 8. 테스트

### 8.1 테스트 파일 구조

| 테스트 유형 | 파일 위치 |
| ----------- | --------- |
| 단위 테스트 | `tests/unit/domains/test_contents.py` |
| 통합 테스트 | `tests/integration/test_contents_api.py` |
| E2E 테스트 | `tests/e2e/test_content_scenarios.py` |

### 8.2 주요 테스트 시나리오

1. 웹페이지 Sync 성공
2. YouTube Sync 성공
3. PDF 업로드 및 S3 저장
4. 콘텐츠 목록 조회 + 필터링
5. 단일 콘텐츠 조회
6. Soft Delete
7. 소유권 검사 (다른 사용자 콘텐츠 접근 시도)
8. 에러 케이스 (파일 크기 초과, 캐시 없음 등)

---

## 9. 구현 체크리스트

### 9.1 사전 작업

- [ ] `app/domains/contents/` 디렉토리 생성
- [ ] 패키지 설치: `boto3`
- [ ] S3 버킷 설정

### 9.2 필수 구현

- [ ] `models.py` - Content 모델
- [ ] `schemas.py` - 요청/응답 스키마
- [ ] `exceptions.py` - 에러 코드 및 예외 클래스
- [ ] `repository.py` - CRUD 로직
- [ ] `service.py` - 비즈니스 로직 (AI 도메인 연동 포함)
- [ ] `router.py` - 6개 엔드포인트
- [ ] `utils.py` - S3 업로드 유틸리티
- [ ] 마이그레이션 생성

### 9.3 테스트

- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] E2E 테스트

---

## 10. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
| ---- | ---- | --------- |
| 1.0 | 2025-12-02 | 초기 작성 |
| 1.1 | 2025-12-02 | AI 기능 분리 (ai-api-spec.md로 이동) |
