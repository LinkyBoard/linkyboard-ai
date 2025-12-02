# AI 오케스트레이션 요구사항 정의서

## 1. 개요

AI 오케스트레이션은 사용자 요청을 분석하여 여러 AI 에이전트를 조율하고,
최적의 결과를 생성하는 시스템입니다.

### 1.1 범위

| Phase | 범위 |
|-------|------|
| **Phase 1** | Topics 도메인 전용 (`ask`, `draft`) |
| **Phase 2+** | AI 도메인 통합 검토 (복잡한 요청 시 오케스트레이터 사용) |

### 1.2 도메인 관계

```
┌─────────────────────────────────────────────────────────┐
│                    Topics 도메인                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Orchestrator                        │   │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐       │   │
│  │  │ Planner │→ │ Executor │→ │ Agents   │       │   │
│  │  └─────────┘  └──────────┘  └──────────┘       │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                     Core LLM                            │
│  ┌───────────┐  ┌───────────┐  ┌─────────────────┐    │
│  │  LiteLLM  │  │ Fallback  │  │ Observability   │    │
│  │ (Provider)│  │  Logic    │  │  (LangFuse)     │    │
│  └───────────┘  └───────────┘  └─────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 에이전트 구성

### 2.1 Phase 1 에이전트

| 에이전트 | 역할 | 기본 모델 | 티어 |
|----------|------|----------|------|
| **PlannerAgent** | 요청 분석, 실행 계획 수립 | Claude 4.5 Haiku | light |
| **SummarizerAgent** | 콘텐츠 요약 | Claude 4.5 Haiku | light |
| **AnalyzerAgent** | 비교/분석/패턴 추출 | GPT-5 mini | standard |
| **ResearcherAgent** | 웹 검색 + 콘텐츠 변환 | pplx-70b-online | search |
| **WriterAgent** | 글 작성/초안 생성 | GPT-5 mini | standard |

### 2.2 에이전트별 책임

```python
class PlannerAgent:
    """요청을 분석하여 실행 계획 수립"""
    # - 어떤 에이전트가 필요한지 결정
    # - 병렬/순차 실행 순서 결정
    # - 각 에이전트에 전달할 컨텍스트 정의

class SummarizerAgent:
    """긴 콘텐츠를 핵심 내용으로 압축"""
    # - 선택된 콘텐츠 요약
    # - 토큰 수 최적화

class AnalyzerAgent:
    """콘텐츠 간 관계 분석"""
    # - 공통점/차이점 분석
    # - 패턴 추출
    # - 인사이트 도출

class ResearcherAgent:
    """외부 정보 검색 및 수집"""
    # - 웹 검색 수행
    # - 검색 결과를 임시 콘텐츠로 변환
    # - 사용자 저장 시 자동 요약 제공

class WriterAgent:
    """최종 결과물 작성"""
    # - 분석 결과 기반 글 작성
    # - 사용자 요구 스타일 반영
```

---

## 3. 실행 방식

### 3.1 API별 실행 방식

| API | 실행 방식 | 설명 |
|-----|----------|------|
| **ask** | 동적 (Planner 기반) | Planner가 필요한 에이전트 선택 |
| **draft** | 고정 파이프라인 | Summarizer → (Researcher) → Writer |

### 3.2 병렬 실행

의존성이 없는 에이전트는 병렬 실행합니다.

```
ask 요청: "선택한 콘텐츠 + 최신 트렌드로 분석해줘"

Stage 1 (병렬):
├── SummarizerAgent: 콘텐츠 요약
└── ResearcherAgent: 웹 검색

Stage 2 (순차):
└── AnalyzerAgent: 요약 + 검색 결과 분석

Stage 3 (순차):
└── WriterAgent: 최종 응답 작성
```

### 3.3 실행 계획 예시

```json
{
  "plan_id": "plan_abc123",
  "stages": [
    {
      "stage": 1,
      "parallel": true,
      "agents": [
        {"agent": "summarizer", "reason": "3개 콘텐츠 요약 필요"},
        {"agent": "researcher", "reason": "최신 트렌드 검색 요청"}
      ]
    },
    {
      "stage": 2,
      "parallel": false,
      "agents": [
        {"agent": "analyzer", "reason": "비교 분석 요청"}
      ]
    },
    {
      "stage": 3,
      "parallel": false,
      "agents": [
        {"agent": "writer", "reason": "최종 응답 작성"}
      ]
    }
  ]
}
```

---

## 4. 모델 선택 전략

### 4.1 기본 전략

- **에이전트별 기본 모델 고정** (서비스 설정)
- **사용자 오버라이드 가능** (`model_preferences` 옵션)
- **동적 선택은 Phase 2**로 연기

### 4.2 사용자 오버라이드

```json
{
  "prompt": "분석해줘",
  "selected_contents": [...],
  "model_preferences": {
    "analyzer": "claude-4.5-sonnet",
    "writer": "gpt-4.1"
  }
}
```

### 4.3 Fallback 순서

| 티어 | 1순위 | 2순위 | 3순위 |
|------|-------|-------|-------|
| **light** | Claude 4.5 Haiku | GPT-4.1-mini | Gemini 2.0 Flash |
| **standard** | GPT-5 mini | GPT-4.1 | Claude 4.5 Sonnet |
| **premium** | GPT-5 | Claude 4.5 Opus | - |
| **search** | pplx-70b-online | pplx-online-mini | - |
| **embedding** | text-embedding-3-large | - | - |

> **Note**: 임베딩은 모델별로 벡터 공간이 다르므로 Fallback 불가. 장애 시 에러 반환 또는 키워드 검색으로 대체.

### 4.4 Fallback 로직

```python
async def call_with_fallback(tier: str, messages: list, **kwargs):
    models = FALLBACK_ORDER[tier]

    for model in models:
        try:
            return await litellm.acompletion(model=model, messages=messages, **kwargs)
        except ProviderError as e:
            logger.warning(f"{model} 실패: {e}, 다음 모델로 시도")
            continue

    raise AllProvidersFailedError("모든 프로바이더 실패")
```

---

## 5. SSE 스트리밍

### 5.1 스트리밍 옵션

| 옵션 | 설명 |
|------|------|
| `stream: false` | 동기 응답 (기본) |
| `stream: true` | SSE 스트리밍 |
| `verbose: false` | 간단한 진행 상황 (기본) |
| `verbose: true` | 상세한 에이전트별 진행 상황 |

### 5.2 verbose: false (기본)

```
event: status
data: {"stage": "planning", "message": "작업을 계획하고 있어요..."}

event: status
data: {"stage": "processing", "message": "콘텐츠를 분석하고 있어요...", "progress": 50}

event: status
data: {"stage": "writing", "message": "글을 작성하고 있어요...", "progress": 80}

event: chunk
data: {"content": "# 분석 결과\n\n"}

event: chunk
data: {"content": "선택된 콘텐츠들은..."}

event: done
data: {"usage": {...}}
```

### 5.3 verbose: true (상세)

```
event: plan
data: {
  "stages": [
    {"agent": "summarizer", "reason": "3개 콘텐츠 요약"},
    {"agent": "researcher", "reason": "최신 트렌드 검색"},
    {"agent": "analyzer", "reason": "비교 분석"},
    {"agent": "writer", "reason": "블로그 형식 작성"}
  ]
}

event: agent_start
data: {"agent": "summarizer", "message": "콘텐츠를 요약하고 있어요..."}

event: agent_start
data: {"agent": "researcher", "message": "관련 자료를 검색하고 있어요..."}

event: agent_done
data: {"agent": "researcher", "result_preview": "3개 결과 발견"}

event: agent_done
data: {"agent": "summarizer", "result_preview": "핵심 내용은..."}

event: agent_start
data: {"agent": "analyzer", "message": "분석하고 있어요..."}

event: agent_done
data: {"agent": "analyzer"}

event: agent_start
data: {"agent": "writer", "message": "글을 작성하고 있어요..."}

event: chunk
data: {"content": "# 분석 결과\n\n"}

event: chunk
data: {"content": "선택된 콘텐츠들은..."}

event: done
data: {"usage": {...}, "agents_used": ["summarizer", "researcher", "analyzer", "writer"]}
```

### 5.4 이벤트 타입

| Event | Description |
|-------|-------------|
| `plan` | 실행 계획 (verbose) |
| `status` | 진행 상황 |
| `agent_start` | 에이전트 시작 (verbose) |
| `agent_chunk` | 에이전트 중간 출력 (verbose) |
| `agent_done` | 에이전트 완료 (verbose) |
| `search_result` | 검색 결과 (verbose) |
| `chunk` | 최종 출력 텍스트 조각 |
| `done` | 완료 |
| `error` | 에러 |

---

## 6. 에러 핸들링

### 6.1 전략: Fallback + 부분 진행

```
실패 → 같은 티어 다른 모델로 재시도 → 실패 → 스킵 + 경고
```

### 6.2 에러 처리 플로우

```python
async def execute_agent(agent: BaseAgent, context: dict) -> AgentResult:
    try:
        return await agent.run(context)
    except ProviderError:
        # Fallback 시도
        try:
            return await agent.run_with_fallback(context)
        except AllProvidersFailedError:
            # 스킵하고 경고 반환
            return AgentResult(
                success=False,
                skipped=True,
                warning=f"{agent.name} 실행 실패, 스킵됨"
            )
```

### 6.3 SSE 에러 이벤트

```
event: agent_error
data: {"agent": "researcher", "error": "검색 서비스 오류", "action": "skipped"}

event: agent_start
data: {"agent": "analyzer", "message": "검색 결과 없이 분석을 진행합니다..."}
```

### 6.4 최종 응답에 경고 포함

```json
{
  "success": true,
  "data": {
    "answer_md": "...",
    "warnings": [
      {"agent": "researcher", "message": "웹 검색을 수행하지 못했습니다"}
    ],
    "usage": {...}
  }
}
```

---

## 7. 웹 검색 콘텐츠

### 7.1 개요

ResearcherAgent가 웹 검색한 결과를 사용자가 저장할 수 있습니다.
**기존 API를 활용**하며, 별도의 API는 필요하지 않습니다.

### 7.2 플로우

```
[오케스트레이션 중]
ResearcherAgent
├── 1. 웹 검색 (Perplexity)
├── 2. 결과를 임시 콘텐츠로 변환
└── 3. SSE로 클라이언트에 전달

[사용자가 "저장" 클릭 시 - 클라이언트 → Spring → AI 서버]
├── 4. Spring: URL 크롤링하여 HTML 획득
├── 5. AI 서버: POST /api/v1/ai/summarize/webpage 호출
│       → 요약, 태그, 카테고리 후보 생성
├── 6. 클라이언트: 사용자에게 편집 UI 제공
│       → 요약/태그/카테고리 수정 가능
├── 7. 사용자가 "확정" 클릭
└── 8. Spring → AI 서버: POST /api/v1/contents/webpage/sync 호출
        → 최종 저장
```

### 7.3 임시 콘텐츠 구조 (SSE 전달용)

```json
{
  "content_id": null,
  "is_temporary": true,
  "source_type": "web_search",
  "title": "2025 AI 트렌드 전망",
  "url": "https://example.com/ai-trends",
  "snippet": "검색 결과 미리보기...",
  "searched_at": "2025-12-03T10:00:00Z"
}
```

### 7.4 사용하는 기존 API

| 단계 | API | 설명 |
|------|-----|------|
| 요약 생성 | `POST /api/v1/ai/summarize/webpage` | URL + HTML로 요약/태그/카테고리 생성 |
| 콘텐츠 저장 | `POST /api/v1/contents/webpage/sync` | 사용자 확정 내용 저장 |

> **Note**: 별도의 `/contents/from-search` API 없이 기존 플로우를 재사용합니다.

---

## 8. 구현 스택

### 8.1 기술 선택

| 구성 요소 | 선택 | 이유 |
|----------|------|------|
| **오케스트레이션** | 직접 구현 | 완전 제어, 요구사항 명확 |
| **LLM 호출** | LiteLLM | 멀티 프로바이더 통합 |
| **모니터링** | LangFuse | 오픈소스, 셀프호스팅 가능 |
| **모델 테스트** | Promptfoo | CLI 기반 A/B 테스트 |
| **병렬 실행** | asyncio | Python 기본 |

### 8.2 확장 계획

| 상황 | 대응 |
|------|------|
| 워크플로우가 복잡해지면 | LangGraph 도입 검토 |
| 에이전트 간 대화 필요 | CrewAI 또는 직접 구현 |

### 8.3 마이그레이션 고려 설계

```python
# 인터페이스 분리로 나중에 교체 가능
class Executor(ABC):
    @abstractmethod
    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        pass

class AsyncioExecutor(Executor):    # Phase 1
    ...

class LangGraphExecutor(Executor):  # 필요 시
    ...
```

---

## 9. 프로젝트 구조

```
app/domains/topics/
├── orchestration/
│   ├── __init__.py
│   ├── orchestrator.py      # 메인 오케스트레이터
│   ├── planner.py           # 실행 계획 수립
│   ├── executor.py          # 병렬/순차 실행
│   └── models.py            # ExecutionPlan, AgentResult 등
├── agents/
│   ├── __init__.py
│   ├── base.py              # BaseAgent 인터페이스
│   ├── summarizer.py
│   ├── analyzer.py
│   ├── researcher.py
│   └── writer.py
├── prompts/
│   ├── __init__.py
│   ├── planner.py           # Planner 프롬프트
│   ├── summarizer.py
│   ├── analyzer.py
│   └── writer.py
└── ...

app/core/
├── llm/
│   ├── __init__.py
│   ├── provider.py          # LiteLLM 래퍼
│   ├── fallback.py          # Fallback 로직
│   └── observability.py     # LangFuse 연동
└── ...
```

---

## 10. 사용량 추적

### 10.1 역할 분담

| 기능 | Spring 서버 | AI 서버 |
|------|------------|---------|
| 사용자 플랜/결제 | ✅ | ❌ |
| 잔여량 관리 (quota) | ✅ | ❌ |
| 월간 리셋 | ✅ | ❌ |
| 한도 체크 | ✅ (요청 전) | ❌ |
| **사용량 계산** | ❌ | ✅ |
| **사용량 로그** | ❌ | ✅ |
| **WTU 리포트** | ❌ | ✅ |

### 10.2 플로우

```
1. 클라이언트 → Spring: "ask 요청"
2. Spring: 한도 체크
   └── 부족하면 → "충전 필요" 응답
3. Spring → AI 서버: 요청 전달
4. AI 서버: 작업 수행 + 사용량 계산
5. AI 서버 → Spring: 응답 + 사용량 리포트
6. Spring: quota 차감
7. Spring → 클라이언트: 최종 응답
```

### 10.3 사용량 로그

> **테이블 정의**: [ai-api-spec.md - ai_usage_logs 테이블](./ai-api-spec.md#37-ai-사용량-로그-테이블) 참조

오케스트레이션에서는 에이전트별 사용량을 `agent_usage` JSONB 필드에 기록합니다:

```json
{
  "planner": {"model": "claude-4.5-haiku", "input_tokens": 150, "output_tokens": 50, "wtu": 1},
  "summarizer": {"model": "claude-4.5-haiku", "input_tokens": 500, "output_tokens": 200, "wtu": 2},
  "analyzer": {"model": "gpt-5-mini", "input_tokens": 800, "output_tokens": 400, "wtu": 9},
  "writer": {"model": "gpt-5-mini", "input_tokens": 1200, "output_tokens": 800, "wtu": 15}
}
```

### 10.4 응답에 사용량 포함

```json
{
  "success": true,
  "data": {
    "answer_md": "...",
    "usage": {
      "total_wtu": 27,
      "total_input_tokens": 2650,
      "total_output_tokens": 1450,
      "agents": {
        "planner": {"wtu": 1},
        "summarizer": {"wtu": 2},
        "analyzer": {"wtu": 9},
        "writer": {"wtu": 15}
      }
    }
  }
}
```

---

## 11. WTU 시스템

> **상세 정의**: [ai-api-spec.md - WTU 시스템](./ai-api-spec.md#38-wtu-weighted-token-unit-시스템) 참조

### 11.1 개요

WTU(Weighted Token Unit)는 모델별 비용 차이를 반영한 표준화된 사용량 단위입니다.
기준 모델(Claude 4.5 Haiku)을 1.0으로 하여 자동으로 가중치를 계산합니다.

### 11.2 오케스트레이션 WTU 계산

```python
async def calculate_orchestration_wtu(agent_results: list[AgentResult]) -> int:
    """오케스트레이션 전체 WTU 계산"""
    total_wtu = 0
    for result in agent_results:
        wtu = await calculate_wtu(
            model_alias=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens
        )
        total_wtu += wtu
    return total_wtu
```

### 11.3 에이전트별 기본 모델 가중치

| 에이전트 | 기본 모델 | 가중치 |
|----------|----------|--------|
| Planner | Claude 4.5 Haiku | 1.00 |
| Summarizer | Claude 4.5 Haiku | 1.00 |
| Analyzer | GPT-5 mini | 5.19 |
| Researcher | pplx-70b-online | 요청당 |
| Writer | GPT-5 mini | 5.19 |

> **전체 모델 카탈로그**: [ai-api-spec.md - model_catalog 테이블](./ai-api-spec.md#36-model-catalog-테이블) 참조

---

## 12. 모니터링

### 12.1 LangFuse 연동

```python
import litellm
from langfuse.decorators import observe

# LiteLLM 자동 트레이싱
litellm.success_callback = ["langfuse"]

@observe()
async def ask(request: AskRequest):
    plan = await planner.run(request)
    results = await executor.run(plan)
    return results
```

### 12.2 대시보드에서 확인 가능한 것

- 각 에이전트별 실행 시간
- 토큰 사용량 / 비용
- 에러율
- 모델별 성능 비교

### 12.3 RAG 평가 (Phase 2)

LangFuse의 Evaluation 기능을 활용하여 RAG 품질을 측정합니다.

#### 평가 지표

| 지표 | 설명 | 측정 대상 |
|------|------|----------|
| **context_relevance** | 검색된 문서가 질문과 관련 있는가 | Retrieval |
| **context_recall** | 답변에 필요한 정보를 다 찾았는가 | Retrieval |
| **faithfulness** | 답변이 검색된 문서에 근거하는가 | Generation |
| **answer_relevance** | 답변이 질문에 적절한가 | Generation |

#### LangFuse Score 기록

```python
from langfuse import Langfuse

langfuse = Langfuse()

# 요청 완료 후 RAG 평가 점수 기록
async def record_rag_scores(trace_id: str, evaluation: dict):
    langfuse.score(
        trace_id=trace_id,
        name="context_relevance",
        value=evaluation["context_relevance"]
    )
    langfuse.score(
        trace_id=trace_id,
        name="faithfulness",
        value=evaluation["faithfulness"]
    )
    langfuse.score(
        trace_id=trace_id,
        name="answer_relevance",
        value=evaluation["answer_relevance"]
    )
```

#### Ragas 연동 (선택)

더 정교한 RAG 평가가 필요한 경우 **Ragas** 라이브러리와 연동합니다.

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    context_relevancy,
    answer_relevancy,
    context_recall
)

# 배치 평가 (샘플링)
async def evaluate_rag_batch(samples: list[dict]):
    result = evaluate(
        dataset=samples,
        metrics=[
            faithfulness,
            context_relevancy,
            answer_relevancy,
            context_recall
        ]
    )

    # LangFuse에 배치 결과 기록
    for sample, scores in zip(samples, result.scores):
        langfuse.score(
            trace_id=sample["trace_id"],
            name="ragas_faithfulness",
            value=scores["faithfulness"]
        )

    return result
```

#### 평가 실행 방식

| 방식 | 설명 | 실행 시점 |
|------|------|----------|
| **실시간** | 매 요청마다 간단한 점수 기록 | 요청 완료 후 |
| **배치** | 샘플링하여 상세 평가 | 일일/주간 배치 |
| **수동** | 어노테이션 UI에서 사람이 평가 | 품질 검증 시 |

### 12.4 모델 비교 테스트 (Promptfoo)

```yaml
# promptfoo.yaml
providers:
  - openai:gpt-4.1
  - anthropic:claude-4.5-sonnet

prompts:
  - "다음 콘텐츠를 분석해주세요: {{content}}"

tests:
  - vars:
      content: "AI 트렌드 기사..."
    assert:
      - type: llm-rubric
        value: "분석이 논리적이고 구조화되어 있는가?"
```

---

## 13. 향후 고려사항

### 13.1 Phase 2 검토 항목

| 항목 | 설명 |
|------|------|
| 동적 모델 선택 | 컨텍스트 길이, 작업 복잡도에 따라 자동 선택 |
| CriticAgent | 결과 검토/개선 에이전트 |
| 캐싱 | 동일 요청 결과 캐싱 |
| Rate Limiting | AI 서버 레벨 요청 제한 |

### 13.2 LangGraph 도입 기준

다음 상황이 되면 LangGraph 도입 검토:

- 복잡한 조건부 분기 필요
- 에이전트 간 반복적 대화 필요
- 체크포인트/복구 필요 (긴 작업)

---

## 14. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0 | 2025-12-03 | 초기 작성 |
| 1.1 | 2025-12-03 | RAG 평가 섹션 추가 (LangFuse + Ragas) |
