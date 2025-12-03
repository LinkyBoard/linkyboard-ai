# Core LLM 통합 가이드

## 개요

이 문서는 Topics/AI 도메인에서 Core LLM 인프라를 사용하는 방법을 설명합니다.

Core LLM 모듈([app/core/llm/](../../app/core/llm/))은 LiteLLM 기반의 멀티 프로바이더 LLM 호출을 제공하며, 티어별 자동 fallback과 LangFuse 옵저버빌리티를 포함합니다.

## 기본 사용법

### 1. 티어 선택

에이전트의 작업 복잡도에 따라 티어를 선택합니다:

- `LLMTier.LIGHT`: 간단한 요약, 분류
- `LLMTier.STANDARD`: 비교 분석, 글 작성
- `LLMTier.PREMIUM`: 복잡한 추론, 논리 구조화
- `LLMTier.SEARCH`: 웹 검색 (Perplexity)
- `LLMTier.EMBEDDING`: 임베딩 생성

### 2. 기본 호출

```python
from app.core.llm import (
    LLMTier,
    LLMMessage,
    call_with_fallback
)

messages = [
    LLMMessage(role="system", content="You are a helpful assistant."),
    LLMMessage(role="user", content="Summarize this content...")
]

result = await call_with_fallback(
    tier=LLMTier.LIGHT,
    messages=messages,
    temperature=0.7
)

print(result.content)
print(f"Used model: {result.model}")
print(f"Tokens: {result.input_tokens} in, {result.output_tokens} out")
```

### 3. 스트리밍

```python
from app.core.llm import stream_with_fallback

async for chunk in stream_with_fallback(
    tier=LLMTier.STANDARD,
    messages=messages
):
    print(chunk, end="", flush=True)
```

### 4. 임베딩

```python
from app.core.llm import create_embedding

vector = await create_embedding("Text to embed")
# vector: list[float] with 3072 dimensions (text-embedding-3-large)
```

## 에이전트 구현 패턴

[app/domains/topics/agents/summarizer.py](../../app/domains/topics/agents/summarizer.py)를 참고하세요.

### BaseAgent 인터페이스

모든 에이전트는 [BaseAgent](../../app/domains/topics/agents/base.py)를 상속합니다:

```python
from app.domains.topics.agents.base import BaseAgent, AgentContext, AgentResult
from app.core.llm import LLMTier, LLMMessage, call_with_fallback

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(tier=LLMTier.STANDARD)

    @property
    def name(self) -> str:
        return "my_agent"

    def build_messages(self, context: AgentContext) -> list[LLMMessage]:
        return [
            LLMMessage(role="system", content="System prompt..."),
            LLMMessage(role="user", content=context.prompt)
        ]

    async def run(self, context: AgentContext) -> AgentResult:
        messages = self.build_messages(context)
        result = await call_with_fallback(tier=self.tier, messages=messages)

        return AgentResult(
            agent_name=self.name,
            success=True,
            content=result.content,
            model_used=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens
        )
```

## 옵저버빌리티

### LangFuse 트레이싱

함수/메서드에 `@observe()` 데코레이터를 추가하면 자동으로 트레이싱됩니다:

```python
from app.core.llm import get_observe_decorator

observe = get_observe_decorator()

@observe()
async def my_function():
    result = await call_with_fallback(...)
    return result
```

LangFuse 대시보드에서 다음 정보를 확인할 수 있습니다:
- 실행 시간
- 토큰 사용량
- 모델 선택
- 에러 발생

## 에러 처리

### 자동 Fallback

첫 번째 모델 실패 시 자동으로 다음 모델로 재시도됩니다:

```
light tier:
claude-4.5-haiku (실패) → gpt-4.1-mini (실패) → gemini-2.0-flash (성공)
```

### 모든 모델 실패 시

```python
from app.core.llm.types import AllProvidersFailedError

try:
    result = await call_with_fallback(tier=LLMTier.LIGHT, messages=messages)
except AllProvidersFailedError as e:
    logger.error(f"All providers failed: {e.detail_info}")
    # 사용자에게 에러 응답 반환
```

## 환경 설정

[.env.example](../../.env.example) 파일을 참고하여 최소 1개 이상의 API 키를 설정해야 합니다:

```bash
# LLM Provider API Keys (최소 1개 필요)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
PERPLEXITY_API_KEY=pplx-...

# LangFuse (선택사항)
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

## Fallback 순서

티어별 fallback 순서는 [fallback.py](../../app/core/llm/fallback.py)의 `FALLBACK_ORDER`에 정의되어 있습니다:

- **LIGHT**: claude-4.5-haiku → gpt-4.1-mini → gemini-2.0-flash
- **STANDARD**: gpt-5-mini → gpt-4.1 → claude-4.5-sonnet
- **PREMIUM**: gpt-5 → claude-4.5-opus
- **SEARCH**: pplx-70b-online → pplx-online-mini
- **EMBEDDING**: text-embedding-3-large (fallback 없음)

## 관련 문서

- [AI Orchestration 명세서](../requirements/orchestration-spec.md)
- [AI 모델 카탈로그 2025](../memo/ai-model-catalog-2025.md)
- [Core LLM 구현 계획](../memo/core-llm-implementation-plan.md)
- [프로젝트 구조 가이드](01-project-structure.md)
- [예외 처리 가이드](04-exception-handling.md)
