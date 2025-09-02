"""
태그 추출 노드

콘텐츠 요약으로부터 관련 태그를 추출합니다.
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.ai.providers.router import ai_router
from app.monitoring.langsmith.tracer import trace_ai_operation
from ..state import AgentState
from .base_node import BaseNode

logger = get_logger(__name__)


class TagExtractionNode(BaseNode):
    """태그 추출 노드"""
    
    def __init__(self):
        super().__init__("tag_extraction")
    
    def get_node_type(self) -> str:
        return "tag_extraction"
    
    @trace_ai_operation("tag_extraction")
    async def process(self, state: AgentState, session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        태그 추출 처리
        
        Args:
            state: 에이전트 상태
            session: 데이터베이스 세션
            
        Returns:
            추출된 태그 결과
        """
        # 이전 노드(content_analysis)의 결과에서 요약 가져오기
        content_analysis_result = state["results"].get("content_analysis")
        if not content_analysis_result:
            raise ValueError("콘텐츠 분석 결과가 없습니다. content_analysis 노드를 먼저 실행해야 합니다.")
        
        summary = content_analysis_result.get("summary", "")
        if not summary:
            raise ValueError("요약 정보가 없습니다.")
        
        user_preferences = state["user_preferences"]
        input_data = state["input_data"]
        
        try:
            # 기존 유사 태그 가져오기 (옵션)
            similar_tags = input_data.get("similar_tags", [])
            tag_count = input_data.get("tag_count", 5)
            
            # 모델 선택
            model_name = await self._select_model(user_preferences)
            
            # 콘텐츠 타입에 따른 태그 생성
            content_type = content_analysis_result.get("content_type", "webpage")
            
            if content_type == "youtube":
                tags = await self._extract_youtube_tags(
                    title=input_data.get("title", ""),
                    summary=summary,
                    model_name=model_name,
                    tag_count=tag_count,
                    user_id=state["user_id"],
                    session=session
                )
            else:
                tags = await self._extract_webpage_tags(
                    summary=summary,
                    similar_tags=similar_tags,
                    model_name=model_name,
                    tag_count=tag_count,
                    user_id=state["user_id"],
                    session=session
                )
            
            # 태그 정제 및 중복 제거
            refined_tags = self._refine_tags(tags, tag_count)
            
            # 토큰 사용량 추정
            estimated_input_tokens = len(summary) // 4
            estimated_output_tokens = sum(len(tag) for tag in refined_tags) // 4
            total_tokens = estimated_input_tokens + estimated_output_tokens
            
            result = {
                "tags": refined_tags,
                "tag_count": len(refined_tags),
                "model_used": model_name,
                "tokens_used": total_tokens,
                "wtu_consumed": total_tokens * 0.001,
                "cost_usd": total_tokens * 0.0001,
                "extraction_metadata": {
                    "summary_length": len(summary),
                    "requested_tag_count": tag_count,
                    "actual_tag_count": len(refined_tags),
                    "content_type": content_type
                }
            }
            
            logger.info(f"Tag extraction completed: {len(refined_tags)} tags generated")
            return result
            
        except Exception as e:
            logger.error(f"Tag extraction failed: {e}")
            raise
    
    async def _extract_webpage_tags(self,
                                   summary: str,
                                   similar_tags: List[str],
                                   model_name: str,
                                   tag_count: int,
                                   user_id: int,
                                   session: Optional[AsyncSession]) -> List[str]:
        """웹페이지 태그 추출"""
        return await ai_router.generate_webpage_tags(
            summary=summary,
            similar_tags=similar_tags,
            tag_count=tag_count,
            model=model_name,
            user_id=user_id,
            session=session
        )
    
    async def _extract_youtube_tags(self,
                                   title: str,
                                   summary: str,
                                   model_name: str,
                                   tag_count: int,
                                   user_id: int,
                                   session: Optional[AsyncSession]) -> List[str]:
        """YouTube 태그 추출"""
        return await ai_router.generate_youtube_tags(
            title=title,
            summary=summary,
            tag_count=tag_count,
            model=model_name,
            user_id=user_id,
            session=session
        )
    
    def _refine_tags(self, tags: List[str], max_count: int) -> List[str]:
        """태그 정제 및 중복 제거"""
        if not tags:
            return []
        
        # 태그 정제: 공백 제거, 소문자 변환, 빈 태그 제거
        refined_tags = []
        seen_tags = set()
        
        for tag in tags:
            if not tag:
                continue
                
            # 태그 정제
            clean_tag = tag.strip()
            if not clean_tag:
                continue
            
            # 중복 체크 (대소문자 구분 안함)
            tag_lower = clean_tag.lower()
            if tag_lower not in seen_tags:
                refined_tags.append(clean_tag)
                seen_tags.add(tag_lower)
                
                # 최대 개수 제한
                if len(refined_tags) >= max_count:
                    break
        
        return refined_tags
    
    async def _select_model(self, user_preferences) -> str:
        """사용자 선호도에 따른 모델 선택"""
        # 태그 추출은 상대적으로 단순한 작업이므로 빠른 모델 우선
        default_model = "gpt-4o-mini"
        
        if user_preferences.default_llm_model:
            return user_preferences.default_llm_model
        
        # 비용 민감도가 높으면 더 저렴한 모델 사용
        if user_preferences.cost_sensitivity == "high":
            return "gpt-4o-mini"
        
        # 품질 선호도가 높으면 더 좋은 모델 사용
        if user_preferences.quality_preference == "quality":
            return "gpt-4o"
        
        return default_model