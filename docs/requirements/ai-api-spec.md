# AI 도메인 API 요구사항 정의서

## 1. 개요

AI 도메인은 LinkyBoard AI 서비스의 기본 인공지능 기능을 담당합니다.
임베딩 생성, 요약, 태그/카테고리 추천, 벡터 검색 기능을 제공합니다.

> **Note**: 다중 콘텐츠 합성 기능은 Topics 도메인의 오케스트레이션(`/ask`, `/draft`)으로 구현됩니다.
> 자세한 내용은 `topic-board-api-spec.md` 및 `orchestration-spec.md`를 참조하세요.

### 1.1 관련 API 그룹

| API 그룹 | Prefix | 설명 |
| -------- | ------ | ---- |
| AI API | `/api/v1/ai` | 요약/검색 |

### 1.2 도메인 관계

```
┌─────────────────┐     uses      ┌─────────────────┐
│    Contents     │ ────────────▶ │       AI        │
│   (CRUD/동기화)  │               │   (요약/검색)    │
└─────────────────┘               └─────────────────┘
                                          ▲
┌─────────────────┐     uses              │
│     Topics      │ ──────────────────────┘
│  (보드/오케스트레이션) │
└─────────────────┘
```

### 1.3 프로젝트 구조

```
app/domains/ai/
├── __init__.py
├── models.py           # SummaryCache, ChunkStrategy, Tag, Category 등
├── schemas.py          # 요청/응답 스키마
├── exceptions.py       # AI 도메인 예외
├── router.py           # API 엔드포인트
│
├── embedding/
│   ├── __init__.py
│   └── service.py      # 임베딩 생성
│
├── summarization/
│   ├── __init__.py
│   ├── service.py      # 요약 생성
│   └── prompts.py      # 프롬프트 템플릿
│
├── search/
│   ├── __init__.py
│   ├── service.py      # 벡터/하이브리드 검색
│   └── repository.py   # 검색 쿼리
│
├── personalization/
│   ├── __init__.py
│   └── service.py      # 태그/카테고리 개인화
│
└── evaluation/         # Phase 2
    ├── __init__.py
    ├── citation.py     # 출처 추적
    └── confidence.py   # 신뢰도 평가
```

---

## 2. 비즈니스 요구사항

### 2.1 기능 요구사항

| ID | 요구사항 | 우선순위 | 구현 대상 API | Phase |
| -- | -------- | -------- | ------------- | ----- |
| AI-001 | 사용 가능한 AI 모델 목록 조회 | 필수 | `GET /models/available` | 1 |
| AI-002 | 웹페이지 AI 요약 및 태그/카테고리 추천 | 필수 | `POST /summarize/webpage` | 1 |
| AI-003 | YouTube URL 기반 자동 분석 및 요약 | 필수 | `POST /summarize/youtube` | 1 |
| AI-004 | PDF 텍스트 추출 및 요약 | 필수 | `POST /summarize/pdf` | 1 |
| AI-005 | 벡터 + 키워드 하이브리드 검색 | 필수 | `POST /search` | 1 |
| AI-006 | 사용자별 태그/카테고리 개인화 추천 | 필수 | Summarize API 내 | 1 |
| AI-007 | 요약 출처 추적 (Citation) | 선택 | Topics 오케스트레이션 연동 | 2 |
| AI-008 | 할루시네이션 감지 및 신뢰도 평가 | 선택 | `POST /evaluate` | 2 |

> **Note**: 다중 콘텐츠 합성은 Topics 도메인의 `/ask`, `/draft` API로 구현됩니다.

### 2.2 비기능 요구사항

| ID | 요구사항 | 목표값 |
| -- | -------- | ------ |
| AI-NF-001 | Summarize API 응답 시간 | < 10s (AI 포함) |
| AI-NF-002 | Search API 응답 시간 | < 500ms |
| AI-NF-003 | 요약 캐시 TTL | 30일 |
| AI-NF-004 | 임베딩 모델 | text-embedding-3-large (3072차원) |
| AI-NF-005 | LLM 모델 | gpt-4o-mini (요약) |

---

## 3. 데이터 모델

### 3.1 Content Embedding Metadatas 테이블

```sql
content_embedding_metadatas (
    id               BIGINT       PRIMARY KEY AUTOINCREMENT,
    content_id       BIGINT       NOT NULL REFERENCES contents(id),
    strategy_id      BIGINT       REFERENCES chunk_strategies(id),
    chunk_index      INTEGER      NOT NULL,
    chunk_content    TEXT         NOT NULL,
    start_position   INTEGER,
    end_position     INTEGER,
    embedding_vector VECTOR(3072),
    embedding_model  VARCHAR(100) DEFAULT 'text-embedding-3-large',
    is_user_summary  BOOLEAN      DEFAULT FALSE,
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_embedding_content_id ON content_embedding_metadatas (content_id);
CREATE INDEX idx_embedding_vector ON content_embedding_metadatas USING ivfflat (embedding_vector vector_cosine_ops);
```

### 3.2 Chunk Strategies 테이블

```sql
chunk_strategies (
    id              BIGINT       PRIMARY KEY AUTOINCREMENT,
    name            VARCHAR(100) UNIQUE NOT NULL,
    content_type    VARCHAR(50),
    domain          VARCHAR(100),
    chunk_size      INTEGER      DEFAULT 500,
    chunk_overlap   INTEGER      DEFAULT 50,
    split_method    VARCHAR(50)  DEFAULT 'token',
    is_active       BOOLEAN      DEFAULT TRUE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at      TIMESTAMP WITH TIME ZONE
);
```

### 3.3 Summary Cache 테이블

```sql
summary_cache (
    id                   BIGINT       PRIMARY KEY AUTOINCREMENT,
    cache_key            VARCHAR(64)  UNIQUE NOT NULL,
    cache_type           VARCHAR(20)  NOT NULL,
    content_hash         VARCHAR(64),
    extracted_text       TEXT,
    summary              TEXT,
    candidate_tags       TEXT[],
    candidate_categories TEXT[],
    chunk_embeddings     JSONB,
    wtu_cost             INTEGER,                          -- 원본 생성 시 사용된 WTU (캐시 히트 시 동일 부과)
    created_at           TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at           TIMESTAMP WITH TIME ZONE,
    expires_at           TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_cache_key ON summary_cache (cache_key);
CREATE INDEX idx_cache_expires ON summary_cache (expires_at);
```

### 3.4 Tags 테이블 (공유 마스터)

```sql
tags (
    id               BIGINT       PRIMARY KEY AUTOINCREMENT,
    tag_name         VARCHAR(100) UNIQUE NOT NULL,
    embedding_vector VECTOR(1536),
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL
);

user_tag_usage (
    id           BIGINT       PRIMARY KEY AUTOINCREMENT,
    user_id      BIGINT       NOT NULL,
    tag_id       BIGINT       NOT NULL REFERENCES tags(id),
    use_count    INTEGER      DEFAULT 1,
    last_used_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(user_id, tag_id)
);

CREATE INDEX idx_user_tag_usage ON user_tag_usage (user_id, use_count DESC);
```

### 3.5 Categories 테이블 (공유 마스터)

```sql
categories (
    id               BIGINT       PRIMARY KEY AUTOINCREMENT,
    category_name    VARCHAR(100) UNIQUE NOT NULL,
    embedding_vector VECTOR(1536),
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL
);

user_category_usage (
    id           BIGINT       PRIMARY KEY AUTOINCREMENT,
    user_id      BIGINT       NOT NULL,
    category_id  BIGINT       NOT NULL REFERENCES categories(id),
    use_count    INTEGER      DEFAULT 1,
    last_used_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(user_id, category_id)
);

CREATE INDEX idx_user_category_usage ON user_category_usage (user_id, use_count DESC);
```

### 3.6 Model Catalog 테이블

AI 모델 정보와 가격, WTU 가중치를 관리합니다.

```sql
model_catalog (
    id                  BIGINT       PRIMARY KEY AUTOINCREMENT,
    alias               VARCHAR(50)  UNIQUE NOT NULL,     -- 'gpt-4.1', 'claude-4.5-haiku'
    provider            VARCHAR(20)  NOT NULL,            -- 'openai', 'anthropic', 'google', 'perplexity'
    model_name          VARCHAR(100) NOT NULL,            -- 실제 모델명
    model_type          VARCHAR(50)  DEFAULT 'llm',       -- 'llm', 'embedding', 'search'
    description         TEXT,

    -- 실제 가격 (1M tokens 기준 USD)
    input_price_per_1m  DECIMAL(10, 4) NOT NULL,
    output_price_per_1m DECIMAL(10, 4) NOT NULL,

    -- 자동 계산 가중치 (기준 모델 대비)
    wtu_multiplier      DECIMAL(6, 2),

    max_context_tokens  INTEGER      DEFAULT 128000,
    is_default          BOOLEAN      DEFAULT FALSE,
    is_available        BOOLEAN      DEFAULT TRUE,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at          TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_model_catalog_available ON model_catalog (is_available) WHERE is_available = TRUE;
CREATE INDEX idx_model_catalog_provider ON model_catalog (provider);
```

### 3.7 AI 사용량 로그 테이블

```sql
ai_usage_logs (
    id                  BIGINT PRIMARY KEY AUTOINCREMENT,
    user_id             BIGINT NOT NULL,
    request_id          UUID NOT NULL,
    request_type        VARCHAR(20),             -- 'ask', 'draft', 'summarize', 'search'

    -- 에이전트별 사용량 (오케스트레이션 사용 시)
    agent_usage         JSONB,
    /*
    {
      "planner": {"model": "claude-4.5-haiku", "input_tokens": 150, "output_tokens": 50, "wtu": 1},
      "summarizer": {"model": "claude-4.5-haiku", "input_tokens": 500, "output_tokens": 200, "wtu": 2},
      ...
    }
    */

    -- 합계
    total_input_tokens  INTEGER NOT NULL,
    total_output_tokens INTEGER NOT NULL,
    total_cost_usd      DECIMAL(10, 6),
    total_wtu           INTEGER NOT NULL,

    created_at          TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_usage_user_date ON ai_usage_logs (user_id, created_at);
CREATE INDEX idx_usage_request ON ai_usage_logs (request_id);
```

### 3.8 WTU (Weighted Token Unit) 시스템

#### 개요

WTU는 모델별 비용 차이를 반영한 표준화된 사용량 단위입니다.
가장 저렴한 모델을 기준(1.0)으로 하여 자동으로 가중치를 계산합니다.

#### 가중치 자동 계산

```python
# 기준 모델 (가장 저렴한 모델 = 1.0)
BASE_MODEL = "claude-4.5-haiku"

async def recalculate_wtu_multipliers():
    """모델 가격 변경 시 전체 가중치 재계산"""
    models = await model_catalog_repo.get_all()
    base = next(m for m in models if m.alias == BASE_MODEL)

    # 기준 비용 (input:output = 1:3 가정)
    base_cost = (base.input_price_per_1m + base.output_price_per_1m * 3) / 4

    for model in models:
        model_cost = (model.input_price_per_1m + model.output_price_per_1m * 3) / 4
        model.wtu_multiplier = round(model_cost / base_cost, 2)
        await model_catalog_repo.update(model)
```

#### WTU 계산

```python
async def calculate_wtu(model_alias: str, input_tokens: int, output_tokens: int) -> int:
    model = await model_catalog_repo.get(model_alias)
    base_wtu = (input_tokens + output_tokens) / 1000  # 1000 토큰당 1 WTU 기준
    return int(base_wtu * model.wtu_multiplier)
```

#### 모델별 가격 및 가중치 예시

| Model | Provider | Input $/1M | Output $/1M | 가중치 |
| ----- | -------- | ---------- | ----------- | ------ |
| claude-4.5-haiku | Anthropic | $0.10 | $0.40 | 1.00 |
| gpt-4.1-mini | OpenAI | $0.15 | $0.60 | 1.50 |
| gemini-2.0-flash | Google | $0.10 | $0.30 | 0.77 |
| **gpt-5-mini** | OpenAI | **$0.25** | **$2.00** | **5.19** |
| gpt-4.1 | OpenAI | $1.00 | $3.00 | 7.69 |
| claude-4.5-sonnet | Anthropic | $3.00 | $15.00 | 36.92 |
| pplx-70b-online | Perplexity | - | - | 요청당 |

> **Note**:
> - Perplexity는 토큰 기반이 아닌 요청당 과금이므로 별도 계산
> - GPT-5 mini는 GPT-4.1보다 저렴하면서 품질이 향상되어 standard 티어 기본 모델로 사용

#### 관리자 가격 수정 API

```http
PUT /api/v1/admin/models/{alias}/pricing
{
  "input_price_per_1m": 0.15,
  "output_price_per_1m": 0.60
}
```

가격 수정 시 전체 모델의 가중치가 자동 재계산됩니다.

---

## 4. API 명세

* Prefix: `/api/v1/ai`
* Tags: `ai`
* 인증: 모든 API에 `X-Internal-Api-Key` 헤더 필수

---

### 4.1 사용 가능한 AI 모델 목록

#### Request

```http
GET /api/v1/ai/models/available
```

#### Response

```json
{
  "success": true,
  "message": "사용 가능한 모델 목록",
  "data": {
    "models": [
      {
        "alias": "gpt-4o",
        "model_name": "gpt-4o-2024-08-06",
        "provider": "openai",
        "model_type": "llm",
        "description": "가장 강력한 GPT 모델",
        "input_cost_per_1k": 2.5,
        "output_cost_per_1k": 10.0,
        "is_default": false
      },
      {
        "alias": "gpt-4o-mini",
        "model_name": "gpt-4o-mini-2024-07-18",
        "provider": "openai",
        "model_type": "llm",
        "description": "빠르고 효율적인 GPT 모델",
        "input_cost_per_1k": 0.15,
        "output_cost_per_1k": 0.6,
        "is_default": true
      }
    ],
    "total_count": 2,
    "default_model": "gpt-4o-mini"
  }
}
```

---

### 4.2 웹페이지 요약 생성

HTML을 분석하여 요약과 개인화된 태그/카테고리를 추천합니다.

#### Request

```http
POST /api/v1/ai/summarize/webpage
Content-Type: multipart/form-data
```

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| url | string | ✅ | 웹페이지 URL |
| html_file | file | ✅ | HTML 파일 |
| user_id | integer | ✅ | 사용자 ID |
| tag_count | integer | ❌ | 추천 태그 수 (기본값: 5) |
| refresh | boolean | ❌ | 캐시 무시하고 재생성 (기본값: false) |

#### Response

```json
{
  "success": true,
  "message": "요약이 생성되었습니다.",
  "data": {
    "content_hash": "sha256...",
    "extracted_text": "추출된 텍스트...",
    "summary": "이 글은 인공지능 기술의 최신 동향에 대해 설명합니다...",
    "tags": ["AI", "기술", "트렌드", "머신러닝", "딥러닝"],
    "category": "tech",
    "candidate_tags": ["AI", "기술", "트렌드", "머신러닝", "딥러닝", "자연어처리", "..."],
    "candidate_categories": ["tech", "science", "education"],
    "cached": false
  }
}
```

#### 동작 로직

1. `cache_key = SHA256(url)`로 캐시 조회
2. 캐시 있고 `content_hash` 동일 → 캐시 사용
3. 캐시 없거나 변경됨:
   - HTML 파싱 (BeautifulSoup)
   - 텍스트 추출 및 청크 분할
   - 청크별 임베딩 생성
   - LLM 요약 생성
   - 후보 태그/카테고리 추출
   - 캐시 저장
4. 개인화 추천 적용 (임베딩 유사도 × 빈도 가중치)

---

### 4.2 YouTube 요약 생성

URL만으로 메타데이터 추출 및 요약을 생성합니다.

#### Request

```http
POST /api/v1/ai/summarize/youtube
Content-Type: application/json
```

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| url | string | ✅ | YouTube 동영상 URL |
| user_id | integer | ✅ | 사용자 ID |
| tag_count | integer | ❌ | 추천 태그 수 (기본값: 5) |
| refresh | boolean | ❌ | 캐시 무시하고 재생성 |

#### Response

```json
{
  "success": true,
  "message": "YouTube 요약이 생성되었습니다.",
  "data": {
    "video_id": "abc123",
    "title": "AI 기술의 미래",
    "thumbnail": "https://i.ytimg.com/vi/abc123/maxresdefault.jpg",
    "transcript": "자막 텍스트...",
    "summary": "이 동영상은 AI 기술의 미래 발전 방향에 대해 논의합니다...",
    "tags": ["AI", "미래기술", "트렌드"],
    "category": "tech",
    "candidate_tags": ["AI", "미래기술", "트렌드", "..."],
    "candidate_categories": ["tech", "science"],
    "cached": false
  }
}
```

#### 구현 지시사항

* `youtube-transcript-api`로 자막 추출
* YouTube Data API로 메타데이터 추출 (선택적)
* 웹페이지와 동일한 캐싱/개인화 로직

---

### 4.3 PDF 요약 생성

#### Request

```http
POST /api/v1/ai/summarize/pdf
Content-Type: multipart/form-data
```

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| pdf_file | file | ✅ | PDF 파일 |
| user_id | integer | ✅ | 사용자 ID |
| tag_count | integer | ❌ | 추천 태그 수 (기본값: 5) |
| refresh | boolean | ❌ | 캐시 무시하고 재생성 |

#### Response

```json
{
  "success": true,
  "message": "PDF 요약이 생성되었습니다.",
  "data": {
    "file_hash": "sha256...",
    "extracted_text": "추출된 텍스트...",
    "summary": "이 문서는 머신러닝 알고리즘의 기초 개념을 설명합니다...",
    "tags": ["머신러닝", "알고리즘", "AI"],
    "category": "tech",
    "candidate_tags": ["머신러닝", "알고리즘", "AI", "..."],
    "candidate_categories": ["tech", "education"],
    "cached": false
  }
}
```

#### 동작 로직

* `cache_key = SHA256(file_content)`로 파일 해시 기반 캐싱
* PyPDF2 또는 pdfplumber로 텍스트 추출

---

### 4.4 콘텐츠 검색

벡터 + 키워드 하이브리드 검색을 지원합니다.

#### Request

```http
POST /api/v1/ai/search
Content-Type: application/json
```

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| user_id | integer | ✅ | 사용자 ID |
| query | string | ✅ | 검색 쿼리 (프롬프트) |
| filters | object | ❌ | 필터 조건 |
| filters.content_type | list[string] | ❌ | 콘텐츠 타입 필터 |
| filters.category | string | ❌ | 카테고리 필터 |
| filters.tags | list[string] | ❌ | 태그 필터 (OR) |
| filters.date_from | string | ❌ | 시작일 (YYYY-MM-DD) |
| filters.date_to | string | ❌ | 종료일 (YYYY-MM-DD) |
| search_mode | string | ❌ | 검색 모드: vector / keyword / hybrid (기본: hybrid) |
| threshold | float | ❌ | 최소 유사도 (기본: 0.5) |
| sort_by | string | ❌ | 정렬 기준: relevance / similarity / created_at / updated_at |
| sort_order | string | ❌ | 정렬 순서: asc / desc (기본: desc) |
| include_chunks | boolean | ❌ | 매칭된 청크 포함 여부 (기본: false) |
| page | integer | ❌ | 페이지 번호 (기본: 1) |
| size | integer | ❌ | 페이지 크기 (기본: 20, 최대: 100) |

#### Response

```json
{
  "success": true,
  "message": "검색 결과입니다.",
  "data": [
    {
      "content_id": 456,
      "title": "2024 AI 기술 동향 분석",
      "summary": "인공지능 기술의 최신 트렌드를...",
      "content_type": "webpage",
      "source_url": "https://...",
      "thumbnail": "https://...",
      "tags": ["AI", "기술"],
      "category": "tech",
      "created_at": "2024-06-15T10:00:00Z",
      "scores": {
        "relevance": 0.88,
        "vector_similarity": 0.92,
        "keyword_score": 0.75
      },
      "matched_chunks": []
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

#### include_chunks=true 응답

```json
{
  "matched_chunks": [
    {
      "chunk_index": 2,
      "snippet": "...인공지능 기술의 발전으로...",
      "similarity": 0.92
    }
  ]
}
```

#### 하이브리드 검색 로직

```python
final_score = (vector_score * 0.7) + (keyword_score * 0.3)
```

---

### 4.5 신뢰도 평가 (Phase 2)

생성된 요약(Topics 오케스트레이션 결과)의 신뢰도와 할루시네이션 위험을 평가합니다.

#### Request

```http
POST /api/v1/ai/evaluate
Content-Type: application/json
```

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| request_id | string | ✅ | 평가할 오케스트레이션 결과 ID |
| content | string | ✅ | 평가할 생성된 텍스트 |
| source_content_ids | list[integer] | ✅ | 원본 소스 콘텐츠 ID 목록 |
| evaluation_type | string | ❌ | 평가 유형: full / quick (기본: quick) |

#### Response

```json
{
  "success": true,
  "message": "신뢰도 평가가 완료되었습니다.",
  "data": {
    "request_id": "req_abc123",
    "overall_confidence": 0.85,
    "hallucination_risk": 0.15,
    "factual_accuracy": 0.88,
    "source_coverage": 0.92,
    "citations": [
      {
        "text": "AI 기술의 발전으로",
        "source_content_id": 456,
        "source_title": "2024 AI 기술 동향",
        "confidence": 0.92
      }
    ],
    "warnings": [
      {
        "claim": "2025년까지 모든 산업에 적용될 것이다",
        "confidence": 0.35,
        "reason": "원본 소스에서 확인되지 않은 주장"
      }
    ]
  }
}
```

---

## 5. 개인화 추천 로직

### 5.1 태그/카테고리 추천

```python
async def personalize_tags(candidate_tags: list[str], user_id: int) -> list[str]:
    # 1. 사용자 기존 태그 + 임베딩 조회
    user_tags = await get_user_tag_stats(user_id)

    # 2. 각 후보 태그에 대해 점수 계산
    scored = []
    for candidate in candidate_tags:
        candidate_embedding = await get_tag_embedding(candidate)
        max_score = 0

        for user_tag in user_tags:
            similarity = cosine_similarity(candidate_embedding, user_tag.embedding)
            score = similarity * log(user_tag.use_count + 1)
            max_score = max(max_score, score)

        scored.append((candidate, max_score))

    # 3. 정렬 후 상위 N개 반환
    scored.sort(key=lambda x: -x[1])
    return [tag for tag, _ in scored[:5]]
```

### 5.2 태그/카테고리 마스터 업데이트

Contents 도메인 Sync 시점에 AI 도메인 호출:

```python
async def update_tag_usage(user_id: int, tags: list[str]):
    for tag_name in tags:
        # 마스터에 없으면 생성 (임베딩 포함)
        tag = await get_or_create_tag(tag_name)

        # 사용자 빈도 업데이트
        await upsert_user_tag_usage(user_id, tag.id)
```

---

## 6. 캐싱 전략

### 6.1 요약 캐시

| 항목 | 값 |
| ---- | -- |
| 캐시 키 | `SHA256(url)` 또는 `SHA256(file)` |
| TTL | 30일 |
| 변경 감지 | `content_hash` 비교 |
| 재생성 | `refresh=true` 파라미터 |
| 저장 내용 | 추출 텍스트, 요약, 후보 태그/카테고리, 청크 임베딩 |

### 6.2 캐시 갱신 시나리오

1. **Summarize 호출 시**: 캐시 없거나 `refresh=true` → 새로 생성
2. **Sync 호출 시 (Contents 도메인)**: `content_hash` 다르면 → 백그라운드 갱신 트리거
3. **TTL 만료**: 다음 요청 시 재생성

### 6.3 캐싱과 과금 정책

**원칙: 요청 기준 과금 (캐시 여부 무관)**

```
사용자 A: URL X 요약 요청 → AI 호출 → WTU 차감
사용자 B: URL X 요약 요청 → 캐시 히트 → WTU 차감 (동일)
```

| 항목 | 정책 |
| ---- | ---- |
| 캐시 미스 | 실제 AI 호출 비용 기준 WTU 차감 |
| 캐시 히트 | 원본 생성 시 사용된 WTU와 동일하게 차감 |
| 근거 | 사용자 입장에서 동일한 서비스 제공 |

**이유:**
- **단순함**: 사용자가 이해하기 쉬움 ("요약 1회 = N WTU")
- **공정함**: 모든 사용자 동일 기준
- **수익성**: 캐시 히트 시 마진 발생 (서비스 운영 비용 충당)

**구현:**
```python
# 캐시에 원본 생성 시 WTU 저장
summary_cache (
    ...
    wtu_cost    INTEGER,  -- 원본 생성 시 사용된 WTU
    ...
)
```

---

## 7. 에러 처리

### 7.1 에러 코드 정의

| Error Code | Description | HTTP Status |
| ---------- | ----------- | ----------- |
| `AI_SERVICE_UNAVAILABLE` | AI 서비스 일시 불가 | 503 |
| `EMBEDDING_FAILED` | 임베딩 생성 실패 | 500 |
| `SUMMARIZATION_FAILED` | 요약 생성 실패 | 500 |
| `INVALID_URL_FORMAT` | 잘못된 URL 형식 | 400 |
| `INVALID_YOUTUBE_URL` | 잘못된 YouTube URL | 400 |
| `YOUTUBE_VIDEO_NOT_FOUND` | YouTube 동영상 없음 | 404 |
| `TRANSCRIPT_NOT_AVAILABLE` | 자막 가져오기 실패 | 422 |
| `HTML_PARSE_ERROR` | HTML 파싱 실패 | 400 |
| `PDF_PARSE_ERROR` | PDF 파싱 실패 | 400 |
| `FILE_SIZE_EXCEEDED` | 파일 크기 제한 초과 | 400 |
| `CONTENT_NOT_FOUND` | 콘텐츠를 찾을 수 없음 | 404 |
| `EVALUATION_FAILED` | 신뢰도 평가 실패 | 500 |
| `RATE_LIMIT_EXCEEDED` | API 호출 한도 초과 | 429 |

---

## 8. 보안

### 8.1 인증

| 항목 | 내용 |
| ---- | ---- |
| 인증 방식 | API Key (Header 기반) |
| Header 이름 | `X-Internal-Api-Key` |
| 환경변수 | `INTERNAL_API_KEY` |
| 적용 범위 | 모든 `/api/v1/ai` 엔드포인트 |

### 8.2 외부 API 키 관리

| 서비스 | 환경변수 | 용도 |
| ------ | -------- | ---- |
| OpenAI | `OPENAI_API_KEY` | 임베딩, 요약 (GPT-4.1, GPT-5 mini 등) |
| Anthropic | `ANTHROPIC_API_KEY` | 에이전트 (Claude 4.5 Haiku/Sonnet) |
| Google | `GOOGLE_API_KEY` | Gemini 모델 (Fallback) |
| Perplexity | `PERPLEXITY_API_KEY` | 웹 검색 (Researcher 에이전트) |
| YouTube | `YOUTUBE_API_KEY` | 메타데이터 조회 (선택적) |

---

## 9. 테스트

### 9.1 테스트 파일 구조

| 테스트 유형 | 파일 위치 |
| ----------- | --------- |
| 단위 테스트 | `tests/unit/domains/test_ai.py` |
| 통합 테스트 | `tests/integration/test_ai_api.py` |
| E2E 테스트 | `tests/e2e/test_ai_scenarios.py` |

### 9.2 주요 테스트 시나리오

**Phase 1:**
1. 웹페이지 요약 생성 + 캐시 히트/미스
2. YouTube URL 분석 + 자막 추출
3. PDF 텍스트 추출 + 요약
4. 하이브리드 검색 결과 검증
5. 태그/카테고리 개인화 추천
6. 에러 케이스 (파일 크기 초과, 잘못된 URL 등)

**Phase 2:**
7. 출처 추적 정확도
8. 할루시네이션 감지
9. 신뢰도 평가

---

## 10. 구현 체크리스트

### 10.1 사전 작업

- [ ] `app/domains/ai/` 디렉토리 생성
- [ ] 패키지 설치: `openai`, `tiktoken`, `youtube-transcript-api`, `beautifulsoup4`, `pgvector`, `PyPDF2`
- [ ] OpenAI API 키 설정

### 10.2 Phase 1 구현

- [ ] `models.py` - 모델 정의
- [ ] `schemas.py` - 요청/응답 스키마
- [ ] `exceptions.py` - 에러 코드 및 예외 클래스
- [ ] `embedding/service.py` - 임베딩 생성
- [ ] `summarization/service.py` - 요약 생성
- [ ] `summarization/prompts.py` - 프롬프트 템플릿
- [ ] `search/service.py` - 검색 로직
- [ ] `search/repository.py` - 검색 쿼리
- [ ] `personalization/service.py` - 개인화 로직
- [ ] `router.py` - 4개 엔드포인트
- [ ] 마이그레이션 생성

### 10.3 Phase 2 구현 (선택)

- [ ] `evaluation/citation.py` - 출처 추적
- [ ] `evaluation/confidence.py` - 신뢰도 평가
- [ ] `router.py` - evaluate 엔드포인트 추가

### 10.4 테스트

- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] E2E 테스트

---

## 11. 향후 고려 사항

### 11.1 Graph RAG 확장

현재는 Classic RAG (벡터 기반)로 구현하며, 향후 필요 시 Graph RAG로 확장을 고려합니다.

**Graph RAG가 필요해지는 시점:**
- "이 기술 블로그에서 언급된 회사들의 다른 기사도 보여줘"
- "A 개념과 B 개념이 함께 등장하는 콘텐츠 + 관련 개념들"
- 사용자의 지식 그래프 시각화
- 멀티홉 질문 답변

**확장 시 추가 구조:**
```
app/domains/ai/
└── knowledge/          # Graph RAG 확장 시 추가
    ├── __init__.py
    ├── entity_extraction.py   # 엔티티 추출
    ├── graph_builder.py       # 지식 그래프 구축
    └── graph_retriever.py     # 그래프 기반 검색
```

**추가 데이터 모델:**
```sql
-- 엔티티
entities (
    id, name, type, embedding_vector, ...
)

-- 엔티티 간 관계
entity_relations (
    id, source_entity_id, target_entity_id, relation_type, ...
)

-- 콘텐츠-엔티티 연결
content_entities (
    content_id, entity_id, mention_count, ...
)
```

**결정 시점:** Topic Board의 "사용자 정의 연결"만으로 부족할 때

### 11.2 임베딩 모델 업그레이드

- 현재: `text-embedding-3-large` (3072 차원)
- 향후: 새 모델 출시 시 마이그레이션 계획 필요
- 고려사항: 기존 임베딩과의 호환성, 재임베딩 비용

### 11.3 LLM 모델 최적화

- 요약: `gpt-4o-mini` (비용 효율)
- 오케스트레이션: Topics 도메인 참조 (`orchestration-spec.md`)
- 향후: 로컬 모델 또는 fine-tuned 모델 검토

---

## 12. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
| ---- | ---- | --------- |
| 1.0 | 2025-12-02 | 초기 작성 - Contents에서 분리 |
| 1.1 | 2025-12-03 | synthesize API 제거 (Topics 오케스트레이션으로 이관), Phase 2에 출처/신뢰도 평가만 유지 |
