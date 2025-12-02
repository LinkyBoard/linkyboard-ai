# Topic Board 도메인 API 요구사항 정의서

## 1. 개요

Topic Board 도메인은 LinkyBoard 서비스의 보드 기반 콘텐츠 관리 및 AI 작업 기능을 담당합니다.
사용자가 토픽별로 구분된 피그마 라이크 보드에 콘텐츠를 배치하고, 콘텐츠 간 연결을 정의하며,
선택된 콘텐츠들을 기반으로 AI 질의 및 초안 작성을 수행합니다.

> **Note**:
> - 요약/검색/합성 등 핵심 AI 기능은 [AI 도메인](./ai-api-spec.md)을 참조하세요.
> - 콘텐츠 CRUD는 [Content 도메인](./content-api-spec.md)을 참조하세요.
> - **AI 오케스트레이션 상세**는 [오케스트레이션 스펙](./orchestration-spec.md)을 참조하세요.

### 1.1 관련 API 그룹

| API 그룹 | Prefix | 설명 |
| -------- | ------ | ---- |
| Topics API | `/api/v1/topics` | 토픽 보드 관리 및 AI 작업 |

### 1.2 도메인 관계

```
┌─────────────────┐                    ┌─────────────────┐
│    Contents     │◀───references─────│   Topic Board   │
│   (CRUD/동기화)  │                    │  (보드/연결/AI)  │
└─────────────────┘                    └────────┬────────┘
                                                │
                                                │ uses (Orchestrator)
                                                ▼
                                       ┌─────────────────┐
                                       │  Orchestrator   │
                                       │ (멀티 에이전트)   │
                                       └────────┬────────┘
                                                │
                                                ▼
                                       ┌─────────────────┐
                                       │    Core LLM     │
                                       │ (LiteLLM/모니터링)│
                                       └─────────────────┘
```

#### Topics ↔ 오케스트레이션 관계

| 구분 | Topics 도메인 | Orchestration |
|------|---------------|---------------|
| **역할** | API 엔드포인트, 요청 검증 | 에이전트 조율, 실행 관리 |
| **책임** | 콘텐츠 수집, 연결 정보 조합 | 계획 수립, 병렬 실행, 결과 통합 |
| **에이전트** | - | Planner, Summarizer, Analyzer, Researcher, Writer |

> **구현 예시**: Topics 도메인에서 Orchestrator를 호출합니다.
> ```python
> from app.domains.topics.orchestration import Orchestrator
>
> class TopicService:
>     def __init__(self, orchestrator: Orchestrator):
>         self.orchestrator = orchestrator
>
>     async def ask(self, request: AskRequest):
>         return await self.orchestrator.run(
>             request_type="ask",
>             contents=request.selected_contents,
>             prompt=request.prompt,
>             connections=request.connections
>         )
> ```

### 1.3 프로젝트 구조

```
app/domains/topics/
├── __init__.py
├── models.py           # TopicAIResult (Phase 2)
├── schemas.py          # 요청/응답 스키마
├── service.py          # 비즈니스 로직
├── router.py           # API 엔드포인트
├── exceptions.py       # 도메인 예외
│
├── orchestration/      # AI 오케스트레이션
│   ├── __init__.py
│   ├── orchestrator.py # 메인 오케스트레이터
│   ├── planner.py      # 실행 계획 수립
│   ├── executor.py     # 병렬/순차 실행
│   └── models.py       # ExecutionPlan, AgentResult
│
├── agents/             # 에이전트 구현
│   ├── __init__.py
│   ├── base.py         # BaseAgent 인터페이스
│   ├── summarizer.py
│   ├── analyzer.py
│   ├── researcher.py
│   └── writer.py
│
└── prompts/            # 프롬프트 템플릿
    ├── __init__.py
    ├── planner.py
    ├── summarizer.py
    ├── analyzer.py
    └── writer.py
```

> **Note**:
> - `ask`, `draft` 기능은 오케스트레이터를 통해 멀티 에이전트로 처리됩니다.
> - Core LLM 모듈(`app/core/llm/`)에서 LiteLLM, Fallback, LangFuse 모니터링을 제공합니다.

---

## 2. 비즈니스 요구사항

### 2.1 기능 요구사항

| ID | 요구사항 | 우선순위 | 구현 대상 API | Phase |
| -- | -------- | -------- | ------------- | ----- |
| TPB-001 | 선택된 콘텐츠 기반 AI 질의 | 필수 | `POST /ask` | 1 |
| TPB-002 | 선택된 콘텐츠 기반 초안 작성 | 필수 | `POST /draft` | 1 |
| TPB-003 | 작업 비용 추정 | 권장 | `POST /estimate-cost` | 2 |
| TPB-004 | 보드 기반 콘텐츠 추천 | 권장 | `POST /recommendations` | 2 |

> **Note**:
> - 토픽 보드 CRUD, 콘텐츠 배치(좌표), 콘텐츠 연결 관리는 **Spring Boot 서버**에서 담당합니다.
> - AI 모델 목록 조회는 **AI 도메인** (`GET /api/v1/ai/models/available`)을 사용합니다.

### 2.2 비기능 요구사항

| ID | 요구사항 | 목표값 |
| -- | -------- | ------ |
| TPB-NF-001 | AI 질의 응답 시간 | < 30s |
| TPB-NF-002 | 초안 작성 응답 시간 | < 60s |
| TPB-NF-003 | 최대 선택 가능 콘텐츠 수 | 20개 |
| TPB-NF-004 | 최대 입력 토큰 수 | 100,000 tokens |
| TPB-NF-005 | 보드당 최대 콘텐츠 수 | 100개 |

---

## 3. 데이터 모델

> **Note**:
> - Topic Board의 핵심 데이터(topics, placements, connections)는 Spring Boot 서버에서 관리합니다.
> - AI 모델 카탈로그와 WTU 시스템은 [AI 도메인](./ai-api-spec.md#36-model-catalog-테이블)을 참조하세요.

### 3.1 Topic AI Results 테이블 (Phase 2)

```sql
topic_ai_results (
    id                  BIGINT       PRIMARY KEY AUTOINCREMENT,
    topic_id            BIGINT       NOT NULL,          -- Spring 서버의 topic ID (FK 아님)
    user_id             BIGINT       NOT NULL,
    result_type         VARCHAR(50)  NOT NULL,          -- 'ask', 'draft'
    selected_content_ids BIGINT[],
    prompt              TEXT         NOT NULL,
    result_md           TEXT         NOT NULL,
    model_alias         VARCHAR(50),
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    wtu_cost            INTEGER,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_topic_ai_results_topic ON topic_ai_results (topic_id);
CREATE INDEX idx_topic_ai_results_user ON topic_ai_results (user_id);
```

### 3.2 Spring Boot 서버에서 관리하는 데이터 (참조용)

아래 데이터는 Spring Boot 서버에서 관리되며, AI API 요청 시 필요한 정보만 전달받습니다:

| 테이블 | 설명 | AI 서버 역할 |
|--------|------|-------------|
| `topics` | 토픽 보드 메타데이터 | topic_id만 참조 |
| `content_placements` | 콘텐츠 배치 좌표 | 사용 안 함 |
| `content_connections` | 콘텐츠 간 연결 | 요청에 포함된 연결 정보 활용 |

### 3.3 모델 구현 지시사항

`app/domains/topics/models.py`:

* **TopicAIResult**: AI 작업 결과 저장 (Phase 2)

---

## 4. API 명세

* Prefix: `/api/v1/topics`
* Tags: `topics`
* 인증: 모든 API에 `X-Internal-Api-Key` 헤더 필수

> **Note**:
> - 토픽 보드 CRUD, 배치, 연결 관리 API는 Spring Boot 서버에서 제공합니다.
> - AI 모델 목록 조회는 [AI 도메인 API](./ai-api-spec.md#41-사용-가능한-ai-모델-목록)를 사용합니다.

---

### 4.1 선택된 콘텐츠 기반 AI 질의

#### Request

```http
POST /api/v1/topics/ask
Content-Type: application/json
Accept: text/event-stream
```

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| user_id | integer | ✅ | 사용자 ID |
| topic_id | integer | ✅ | 토픽 보드 ID (Spring 서버 참조용) |
| prompt | string | ✅ | AI에게 요청할 질의/지시사항 |
| selected_contents | list[SelectedContent] | ✅ | 선택된 콘텐츠 목록 (Spring에서 내용 포함하여 전달) |
| connections | list[Connection] | ❌ | 콘텐츠 간 연결 정보 (Spring에서 전달) |
| model_alias | string | ✅ | 사용할 AI 모델 별칭 |
| stream | boolean | ❌ | SSE 스트리밍 여부 (기본: false) |
| verbose | boolean | ❌ | 상세 진행 상황 표시 여부 (기본: false, stream=true일 때만 유효) |

**SelectedContent 구조:**
| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| content_id | integer | ✅ | 콘텐츠 ID |
| title | string | ✅ | 콘텐츠 제목 |
| summary | string | ✅ | 콘텐츠 요약 (Spring에서 전달) |
| full_content | string | ❌ | 전체 내용 (필요시 Spring에서 전달) |

> **Note**: 콘텐츠 내용은 Spring 서버가 함께 전달합니다. 이를 통해 데이터 일관성을 보장하고 동기화 문제를 방지합니다.

**Connection 구조 (선택적):**
| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| source_content_id | integer | ✅ | 시작 콘텐츠 ID |
| target_content_id | integer | ✅ | 대상 콘텐츠 ID |
| connection_type | string | ✅ | 연결 유형 (related/supports/contradicts/extends) |
| label | string | ❌ | 연결 라벨 |

```json
{
  "user_id": 123,
  "topic_id": 1,
  "prompt": "선택된 콘텐츠들의 공통점과 차이점을 비교 분석해서 정리해주세요",
  "selected_contents": [
    {"content_id": 1, "title": "AI 트렌드 2025", "summary": "2025년 AI 트렌드에 대한 분석..."},
    {"content_id": 2, "title": "머신러닝 입문", "summary": "머신러닝 기초 개념...", "full_content": "전체 내용..."},
    {"content_id": 3, "title": "딥러닝 활용", "summary": "딥러닝 활용 사례..."}
  ],
  "connections": [
    {"source_content_id": 1, "target_content_id": 2, "connection_type": "supports", "label": "기반 기술"}
  ],
  "model_alias": "gpt-4o-mini",
  "stream": true
}
```

#### Response (일반)

```json
{
  "success": true,
  "message": "AI 질의 완료",
  "data": {
    "answer_md": "# 분석 결과\n\n## 공통점\n선택된 3개의 콘텐츠는 모두 AI 기술에 대해 다루고 있습니다...\n\n## 차이점\n...",
    "used_contents": [
      {"content_id": 1, "title": "AI 트렌드 2025", "tokens_used": 500},
      {"content_id": 2, "title": "머신러닝 입문", "tokens_used": 1200},
      {"content_id": 3, "title": "딥러닝 활용", "tokens_used": 450}
    ],
    "usage": {
      "input_tokens": 2150,
      "output_tokens": 850,
      "total_tokens": 3000,
      "wtu_cost": 12
    },
    "model_info": {
      "alias": "gpt-4o-mini",
      "model_name": "gpt-4o-mini-2024-07-18",
      "provider": "openai"
    }
  }
}
```

#### Response (SSE 스트리밍)

`stream: true`인 경우 Server-Sent Events로 응답합니다.

```
event: chunk
data: {"content": "# 분석 결과\n\n"}

event: chunk
data: {"content": "## 공통점\n"}

event: chunk
data: {"content": "선택된 3개의 콘텐츠는..."}

event: done
data: {"used_contents": [...], "usage": {...}, "model_info": {...}}
```

| Event | Description |
| ----- | ----------- |
| `chunk` | 생성된 텍스트 조각 |
| `done` | 완료 (메타데이터 포함) |
| `error` | 에러 발생 |
```

---

### 4.3 선택된 콘텐츠 기반 초안 작성

#### Request

```http
POST /api/v1/topics/draft
Content-Type: application/json
Accept: text/event-stream
```

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| user_id | integer | ✅ | 사용자 ID |
| topic_id | integer | ✅ | 토픽 보드 ID (Spring 서버 참조용) |
| requirements | string | ✅ | 작성 요구사항 및 스타일 지시 |
| selected_contents | list[SelectedContent] | ✅ | 선택된 콘텐츠 목록 (Spring에서 내용 포함하여 전달) |
| connections | list[Connection] | ❌ | 콘텐츠 간 연결 정보 (Spring에서 전달) |
| model_alias | string | ✅ | 사용할 AI 모델 별칭 |
| stream | boolean | ❌ | SSE 스트리밍 여부 (기본: false) |
| verbose | boolean | ❌ | 상세 진행 상황 표시 여부 (기본: false, stream=true일 때만 유효) |

```json
{
  "user_id": 123,
  "topic_id": 1,
  "requirements": "전문적이면서도 친근한 톤으로 블로그 글 형식의 초안을 작성해주세요.",
  "selected_contents": [
    {"content_id": 1, "title": "AI 트렌드 2025", "summary": "2025년 AI 트렌드에 대한 분석..."},
    {"content_id": 2, "title": "머신러닝 입문", "summary": "머신러닝 기초 개념..."},
    {"content_id": 3, "title": "딥러닝 활용", "summary": "딥러닝 활용 사례..."}
  ],
  "connections": [
    {"source_content_id": 1, "target_content_id": 2, "connection_type": "supports"}
  ],
  "model_alias": "gpt-4o-mini",
  "stream": true
}
```

#### Response (일반)

```json
{
  "success": true,
  "message": "초안 작성 완료",
  "data": {
    "title": "AI 기술의 현재와 미래: 알아야 할 모든 것",
    "draft_md": "# AI 기술의 현재와 미래\n\n## 서론\n...",
    "used_contents": [
      {"content_id": 1, "title": "AI 트렌드 2025", "tokens_used": 500},
      {"content_id": 2, "title": "머신러닝 입문", "tokens_used": 1200},
      {"content_id": 3, "title": "딥러닝 활용", "tokens_used": 450}
    ],
    "usage": {
      "input_tokens": 2150,
      "output_tokens": 1500,
      "total_tokens": 3650,
      "wtu_cost": 18
    },
    "model_info": {
      "alias": "gpt-4o-mini",
      "model_name": "gpt-4o-mini-2024-07-18",
      "provider": "openai"
    }
  }
}
```

#### Response (SSE 스트리밍)

`stream: true`인 경우 Server-Sent Events로 응답합니다. (ask API와 동일한 형식)

---

### 4.4 작업 비용 추정 (Phase 2)

> **Note**: 출력 토큰 예측의 부정확성으로 인해 Phase 2로 연기.
> 실제 사용량 기반 과금이 더 정확하며, 필요 시 구현 검토.

#### Request

```http
POST /api/v1/topics/estimate-cost
Content-Type: application/json
```

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| user_id | integer | ✅ | 사용자 ID |
| selected_content_ids | list[integer] | ✅ | 선택된 콘텐츠 ID 목록 |
| estimated_output_tokens | integer | ❌ | 예상 출력 토큰 수 (기본: 1500) |

#### 추정 방식

```python
# 입력 토큰: 콘텐츠 길이 기반 (비교적 정확)
input_tokens = sum(len(content.summary) / 4 for content in contents)

# 출력 토큰: 사용자 입력 또는 기본값 (부정확)
output_tokens = request.estimated_output_tokens or 1500

# WTU 계산
wtu = (input_tokens * cost_per_1k / 1000) + (output_tokens * cost_per_1k / 1000)
```

#### 한계점

| 항목 | 정확도 | 비고 |
|------|--------|------|
| 입력 토큰 | ~90% | 콘텐츠 길이 기반 |
| 출력 토큰 | ~50% | 작업에 따라 크게 달라짐 |
| 총 비용 | ~70% | 출력 토큰 비중에 따라 |

---

### 4.5 보드 기반 콘텐츠 추천 (Phase 2)

#### Request

```http
POST /api/v1/topics/recommendations
Content-Type: application/json
```

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| user_id | integer | ✅ | 사용자 ID |
| topic_id | integer | ✅ | 토픽 보드 ID |
| content_ids | list[integer] | ✅ | 현재 보드의 콘텐츠 ID 목록 |
| recommendation_type | string | ❌ | 추천 유형 (기본: `content_gaps`) |

**recommendation_type 옵션:**
| Type | Description |
| ---- | ----------- |
| `content_gaps` | 보드에 부족한 콘텐츠 영역 분석 |
| `connections` | 콘텐츠 간 연결 추천 |

#### Response

```json
{
  "success": true,
  "message": "추천 조회 완료",
  "data": {
    "topic_id": 1,
    "recommendation_type": "content_gaps",
    "recommendations": [
      {
        "category": "missing_topic",
        "description": "AI 윤리에 대한 콘텐츠가 부족합니다",
        "priority": "high",
        "suggested_actions": ["AI 윤리 관련 기사 수집"]
      }
    ]
  }
}
```
---

## 5. AI 도메인 연동

### 5.1 연결 정보 활용

Spring 서버에서 전달받은 연결 정보를 프롬프트에 포함하여 더 맥락 있는 응답을 생성합니다.

```python
# topics/board_service.py
def build_context_with_connections(
    contents: list[Content],
    connections: list[dict]  # Spring에서 전달받은 연결 정보
) -> str:
    context = "## 콘텐츠 목록\n\n"
    for content in contents:
        context += f"### {content.title}\n{content.summary}\n\n"

    if connections:
        context += "## 콘텐츠 간 관계\n\n"
        for conn in connections:
            context += f"- [콘텐츠 {conn['source_content_id']}] --[{conn['connection_type']}]--> [콘텐츠 {conn['target_content_id']}]\n"
            if conn.get('label'):
                context += f"  라벨: {conn['label']}\n"

    return context
```

### 5.2 AI 도메인 서비스 호출

```python
# topics/board_service.py
from app.domains.ai.synthesis.service import SynthesisService

class BoardService:
    def __init__(self, synthesis_service: SynthesisService):
        self.synthesis = synthesis_service

    async def ask(self, request: AskRequest) -> AskResponse:
        # 1. 콘텐츠 조회 (Contents 도메인)
        contents = await self.content_repo.get_by_ids(
            [c.content_id for c in request.selected_contents]
        )

        # 2. 컨텍스트 구성 (연결 정보는 요청에 포함됨)
        context = build_context_with_connections(contents, request.connections)

        # 3. AI 도메인 호출
        return await self.synthesis.generate(
            model_alias=request.model_alias,
            system_prompt=ASK_SYSTEM_PROMPT,
            user_prompt=f"{request.prompt}\n\n---\n\n{context}"
        )
```

---

## 6. 에러 처리

### 6.1 에러 코드 정의

| Error Code | Description | HTTP Status |
| ---------- | ----------- | ----------- |
| `CONTENT_NOT_FOUND` | 콘텐츠를 찾을 수 없음 | 404 |
| `MAX_CONTENTS_EXCEEDED` | 최대 선택 콘텐츠 수 초과 | 400 |
| `MAX_TOKENS_EXCEEDED` | 최대 토큰 수 초과 | 400 |
| `MODEL_NOT_FOUND` | 모델을 찾을 수 없음 | 404 |
| `MODEL_NOT_AVAILABLE` | 모델 사용 불가 | 400 |
| `AI_SERVICE_ERROR` | AI 서비스 오류 | 503 |
| `PERMISSION_DENIED` | 접근 권한 없음 | 403 |

> **Note**: WTU 시스템 및 비용 계산은 [AI 도메인](./ai-api-spec.md#37-wtu-weighted-token-unit-시스템)을 참조하세요.

---

## 7. 보안

### 7.1 인증

| 항목 | 내용 |
| ---- | ---- |
| 인증 방식 | API Key (Header 기반) |
| Header 이름 | `X-Internal-Api-Key` |
| 환경변수 | `INTERNAL_API_KEY` |
| 적용 범위 | 모든 `/api/v1/topics` 엔드포인트 |

### 7.2 권한 검사

* Spring 서버에서 권한 검사 후 AI 서버 호출
* AI 서버는 user_id 기반으로 사용량 추적만 담당

---

## 8. 테스트

### 8.1 테스트 파일 구조

| 테스트 유형 | 파일 위치 |
| ----------- | --------- |
| 단위 테스트 | `tests/unit/domains/test_topics.py` |
| 통합 테스트 | `tests/integration/test_topics_api.py` |
| E2E 테스트 | `tests/e2e/test_topic_scenarios.py` |

### 8.2 주요 테스트 시나리오

**Phase 1:**
1. AI 질의 (연결 정보 포함/미포함)
2. 초안 작성
3. 에러 케이스 (최대 콘텐츠 수 초과, 모델 없음 등)

**Phase 2:**
4. 비용 추정
5. 보드 기반 추천
6. AI 결과 저장 및 조회

---

## 9. 구현 체크리스트

### 9.1 사전 작업

- [ ] `app/domains/topics/` 디렉토리 생성
- [ ] AI 도메인 모델 카탈로그 데이터 확인

### 9.2 Phase 1 구현

- [ ] `schemas.py` - 요청/응답 스키마
- [ ] `exceptions.py` - 에러 코드 및 예외 클래스
- [ ] `service.py` - 비즈니스 로직
- [ ] `board_service.py` - AI 질의, 초안 작성 (AI 도메인 활용)
- [ ] `prompts.py` - 프롬프트 템플릿
- [ ] `router.py` - 2개 엔드포인트 (ask, draft)

### 9.3 Phase 2 구현

- [ ] `models.py` - TopicAIResult 추가
- [ ] 비용 추정 기능
- [ ] 보드 추천 기능
- [ ] AI 결과 저장/조회
- [ ] 마이그레이션 생성

### 9.4 테스트

- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] E2E 테스트

---

## 10. 향후 고려 사항

### 10.1 Phase 2 고려사항

| 항목 | 설명 | 우선순위 |
|------|------|----------|
| 캐싱 전략 | `topic_ai_results` 테이블 또는 Redis 활용 | 중 |
| 연결 정보 활용 고도화 | 연결 유형별 가중치, 우선 참조 로직 | 낮 |
| Rate Limiting | 사용자별/시간별 API 호출 제한 | 중 |
| 동적 모델 선택 | 컨텍스트 길이, 작업 복잡도에 따라 자동 선택 | 중 |
| CriticAgent | 결과 검토/개선 에이전트 추가 | 낮 |
| LangGraph 도입 | 복잡한 워크플로우 시 검토 | 낮 |

### 10.2 AI 오케스트레이션 확장

현재 Topics 도메인 전용으로 구현된 오케스트레이션을
AI 도메인 통합 방식(옵션 C)으로 확장 가능합니다.

```
[Phase 1] Topics 전용 오케스트레이션
[Phase 2+] AI 도메인 통합 오케스트레이션 검토
```

### 10.3 Spring 서버와의 역할 분담

| 기능 | Spring 서버 | AI 서버 |
|------|------------|---------|
| 토픽 CRUD | ✅ | ❌ |
| 배치 관리 | ✅ | ❌ |
| 연결 관리 | ✅ | ❌ |
| 콘텐츠 내용 전달 | ✅ | ❌ (전달받아 사용) |
| 사용자 플랜/결제 | ✅ | ❌ |
| 잔여량 관리 (quota) | ✅ | ❌ |
| 한도 체크 | ✅ (요청 전) | ❌ |
| 모델 카탈로그 | ❌ | ✅ (AI 도메인) |
| WTU 계산/로그 | ❌ | ✅ (AI 도메인) |
| AI 질의/초안 | ❌ | ✅ (오케스트레이션) |
| 콘텐츠 추천 | ❌ | ✅ |

---

## 11. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
| ---- | ---- | --------- |
| 1.0 | 2025-12-02 | 초기 작성 - legacy-board-spec.md 기반 재구성 |
| 1.1 | 2025-12-02 | 역할 분담 명확화 - 토픽/배치/연결은 Spring 서버 담당 |
| 1.2 | 2025-12-02 | WTU 시스템 및 모델 카탈로그를 AI 도메인으로 이동 |
| 1.3 | 2025-12-02 | SSE 스트리밍 지원 추가, 콘텐츠 전달 방식 변경 |
| 2.0 | 2025-12-03 | AI 오케스트레이션 아키텍처 반영 (멀티 에이전트, 병렬 실행) |
