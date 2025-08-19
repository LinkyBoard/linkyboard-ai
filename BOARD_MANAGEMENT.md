# Board Management System

AI 서버의 보드 관리 및 분석 시스템 문서입니다.

## 개요

사용자의 토픽 보드에 대한 정보를 AI 서버에서 관리하여 추천 및 인사이트 기능을 제공합니다.

## 주요 기능

### 1. 보드 동기화 (`/v1/boards/`)
- 스프링 서버와 보드 정보 실시간 동기화
- 보드 생성/수정/삭제 이벤트 처리
- 보드-아이템 관계 관리

### 2. 보드 분석 (`board_analytics`)
- 보드 콘텐츠 전체 분석
- 주제 일관성, 다양성 점수 계산
- OpenAI 임베딩을 활용한 토픽 분석
- 카테고리 및 태그 분석

### 3. 인사이트 생성 (`/v1/boards/{board_id}/insights`)
- 콘텐츠 품질 평가
- 조직화 제안
- 콘텐츠 부족 영역 식별
- 참여 가능성 평가

### 4. 추천 시스템 (`/board-ai/{board_id}/recommendations`)
- 콘텐츠 개선 제안
- 조직화 가이드
- 품질 향상 추천

## 데이터베이스 스키마

### Tables
1. **boards** - 보드 기본 정보 (스프링 서버와 동기화)
2. **board_items** - 보드-아이템 관계
3. **board_analytics** - 분석 결과 저장 (벡터 임베딩 포함)
4. **board_recommendation_cache** - 추천 결과 캐시

### Key Features
- PostgreSQL + pgvector for semantic search
- Auto-updating statistics with triggers
- Vector similarity search for related boards
- Cached recommendations with expiration

## API 엔드포인트

### Board Sync API
```
POST /v1/boards/sync                    # 보드 동기화
POST /v1/boards/{board_id}/items/sync   # 아이템 관계 동기화
DELETE /v1/boards/{board_id}            # 보드 삭제
GET /v1/boards/{board_id}/analytics     # 분석 결과 조회
POST /v1/boards/{board_id}/analyze      # 분석 트리거
GET /v1/boards/{board_id}/insights      # 인사이트 조회
GET /v1/boards/user/{user_id}           # 사용자 보드 목록
```

### Board AI API
```
GET /board-ai/{board_id}/recommendations  # AI 추천 조회
```

## 분석 지표

### Content Quality Score
- **Topic Coherence** (40%): 주제 일관성
- **Content Diversity** (30%): 콘텐츠 다양성  
- **Item Relevance** (30%): 아이템 관련도

### Diversity Metrics
- Category diversity across items
- Domain diversity (different sources)
- Content length variance

### Engagement Potential
- Optimal item count (10-20 items)
- Topic coherence
- Content variety

## 설치 및 실행

### 1. 데이터베이스 마이그레이션
```bash
# 마이그레이션 실행
python migrations/run_migration.py

# 상태 확인
python migrations/run_migration.py check
```

### 2. 의존성
- PostgreSQL with pgvector extension
- OpenAI API for embeddings and analysis
- SQLAlchemy for async database operations

### 3. 환경 변수
```bash
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
```

## 사용 예시

### 1. 스프링 서버에서 보드 동기화
```python
# 보드 생성 시
POST /v1/boards/sync
{
    "board_id": 123,
    "user_id": 456,
    "title": "AI 학습 자료",
    "description": "인공지능 관련 아티클 모음",
    "is_active": true
}

# 아이템 추가 시  
POST /v1/boards/123/items/sync
{
    "board_id": 123,
    "item_ids": [1, 2, 3, 4, 5],
    "item_orders": {"1": 0, "2": 1, "3": 2}
}
```

### 2. 보드 분석 및 인사이트 조회
```python
# 분석 트리거
POST /v1/boards/123/analyze
{
    "board_id": 123,
    "force_refresh": false
}

# 인사이트 조회
GET /v1/boards/123/insights
# Response:
{
    "board_id": 123,
    "content_quality": {
        "score": 0.75,
        "level": "높음",
        "coherence": 0.8,
        "diversity": 0.6,
        "relevance": 0.8
    },
    "organization_suggestions": [
        "유사한 카테고리들을 그룹핑하여 정리해보세요."
    ],
    "content_gaps": [
        "실습 예제나 코드 샘플이 부족합니다."
    ],
    "engagement_potential": {
        "score": 0.82,
        "level": "높음"
    }
}
```

### 3. AI 추천 조회
```python
GET /board-ai/123/recommendations?user_id=456&recommendation_type=content_gaps
# Response:
{
    "board_id": 123,
    "recommendation_type": "content_gaps",
    "recommendations": [
        {
            "type": "content_improvement",
            "priority": "medium",
            "suggestion": "실습 예제나 코드 샘플이 부족합니다.",
            "action": "add_content"
        }
    ],
    "total_count": 1,
    "insights_summary": {
        "content_quality": {"score": 0.75, "level": "높음"},
        "engagement_potential": {"score": 0.82, "level": "높음"}
    }
}
```

## 개발자 가이드

### 새로운 분석 지표 추가
1. `BoardAnalyticsService`에 계산 메서드 추가
2. 데이터베이스 스키마에 필드 추가 (마이그레이션)
3. API 스키마 업데이트

### 새로운 추천 타입 추가
1. `BoardAIService.get_board_recommendations()`에 로직 추가
2. 추천 타입 문서화

### 성능 최적화
- 분석 결과 캐싱 (`is_stale` 플래그 활용)
- 백그라운드 작업으로 무거운 분석 실행
- 벡터 인덱스를 활용한 유사 보드 검색

## 모니터링 및 로깅

모든 API 호출과 분석 작업은 구조화된 로그로 기록됩니다:
- 보드 동기화 이벤트
- 분석 실행 시간 및 결과
- 추천 생성 통계
- 오류 및 예외 상황

## 향후 계획

- [ ] 보드 간 유사도 기반 추천
- [ ] 사용자 맞춤형 인사이트
- [ ] 실시간 분석 결과 업데이트
- [ ] 보드 품질 점수 기반 랭킹 시스템