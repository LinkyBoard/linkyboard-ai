"""
콘텐츠 분석 노드

웹페이지, YouTube 등의 콘텐츠를 분석하여 요약을 생성합니다.
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.ai.providers.router import ai_router
from app.monitoring.langsmith.tracer import trace_ai_operation
from ..state import AgentState
from .base_node import BaseNode

logger = get_logger(__name__)


class ContentAnalysisNode(BaseNode):
    """콘텐츠 분석 노드"""
    
    def __init__(self):
        super().__init__("content_analysis")
    
    def get_node_type(self) -> str:
        return "content_analysis"
    
    @trace_ai_operation("content_analysis")
    async def process(self, state: AgentState, session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        콘텐츠 분석 처리
        
        Args:
            state: 에이전트 상태
            session: 데이터베이스 세션
            
        Returns:
            분석 결과
        """
        input_data = state["input_data"]
        user_preferences = state["user_preferences"]
        
        # 콘텐츠 타입 확인
        content_type = input_data.get("content_type", "webpage")
        
        try:
            if content_type == "webpage":
                return await self._analyze_webpage(input_data, user_preferences, state["user_id"], state["board_id"], session)
            elif content_type == "youtube":
                return await self._analyze_youtube(input_data, user_preferences, state["user_id"], state["board_id"], session)
            else:
                return await self._analyze_generic_content(input_data, user_preferences, state["user_id"], state["board_id"], session)
                
        except Exception as e:
            logger.error(f"Content analysis failed: {e}")
            raise
    
    async def _analyze_webpage(self, 
                              input_data: Dict[str, Any],
                              user_preferences,
                              user_id: int,
                              board_id: Optional[int],
                              session: Optional[AsyncSession]) -> Dict[str, Any]:
        """웹페이지 분석"""
        url = input_data.get("url", "")
        html_content = input_data.get("html_content", "")
        title = input_data.get("title", "")
        
        if not html_content:
            raise ValueError("HTML 콘텐츠가 제공되지 않았습니다.")
        
        # 선택된 모델 결정
        model_name = await self._select_model(user_preferences)
        
        # 웹페이지 요약 생성
        summary = await ai_router.generate_webpage_summary(
            url=url,
            html_content=html_content,
            model=model_name,
            max_tokens=500,
            user_id=user_id,
            session=session
        )
        
        # 토큰 사용량 추정 (실제로는 AI Router에서 반환되어야 함)
        estimated_tokens = len(html_content) // 4  # 대략적인 추정
        
        result = {
            "content_type": "webpage",
            "url": url,
            "title": title,
            "summary": summary,
            "model_used": model_name,
            "tokens_used": estimated_tokens,
            "wtu_consumed": estimated_tokens * 0.001,  # 임시 계산
            "cost_usd": estimated_tokens * 0.0001,  # 임시 계산
            "analysis_metadata": {
                "content_length": len(html_content),
                "summary_length": len(summary),
                "analysis_type": "webpage_summary"
            }
        }
        
        logger.info(f"Webpage analysis completed: {len(summary)} chars summary generated")
        return result
    
    async def _analyze_youtube(self,
                              input_data: Dict[str, Any], 
                              user_preferences,
                              user_id: int,
                              board_id: Optional[int],
                              session: Optional[AsyncSession]) -> Dict[str, Any]:
        """YouTube 콘텐츠 분석"""
        title = input_data.get("title", "")
        transcript = input_data.get("transcript", "")
        url = input_data.get("url", "")
        
        if not transcript:
            raise ValueError("YouTube 트랜스크립트가 제공되지 않았습니다.")
        
        # 선택된 모델 결정
        model_name = await self._select_model(user_preferences)
        
        # YouTube 요약 생성
        summary = await ai_router.generate_youtube_summary(
            title=title,
            transcript=transcript,
            model=model_name,
            user_id=user_id,
            session=session
        )
        
        # 토큰 사용량 추정
        estimated_tokens = (len(title) + len(transcript)) // 4
        
        result = {
            "content_type": "youtube",
            "url": url,
            "title": title,
            "summary": summary,
            "model_used": model_name,
            "tokens_used": estimated_tokens,
            "wtu_consumed": estimated_tokens * 0.001,
            "cost_usd": estimated_tokens * 0.0001,
            "analysis_metadata": {
                "transcript_length": len(transcript),
                "summary_length": len(summary),
                "analysis_type": "youtube_summary"
            }
        }
        
        logger.info(f"YouTube analysis completed: {len(summary)} chars summary generated")
        return result
    
    async def _analyze_generic_content(self,
                                     input_data: Dict[str, Any],
                                     user_preferences,
                                     user_id: int,
                                     board_id: Optional[int], 
                                     session: Optional[AsyncSession]) -> Dict[str, Any]:
        """일반 콘텐츠 분석"""
        content = input_data.get("content", "")
        content_type = input_data.get("content_type", "text")
        
        if not content:
            raise ValueError("분석할 콘텐츠가 제공되지 않았습니다.")
        
        # 선택된 모델 결정
        model_name = await self._select_model(user_preferences)
        
        # 간단한 요약 생성을 위한 프롬프트
        messages = [
            {"role": "system", "content": "당신은 콘텐츠 분석 전문가입니다. 주어진 텍스트를 간결하게 요약해주세요."},
            {"role": "user", "content": f"다음 콘텐츠를 한국어로 요약해주세요:\n\n{content}"}
        ]
        
        # AI 호출
        response = await ai_router.generate_chat_completion(
            messages=messages,
            model=model_name,
            max_tokens=400,
            temperature=0.3,
            user_id=user_id,
            board_id=board_id,
            session=session
        )
        
        summary = response.content
        
        result = {
            "content_type": content_type,
            "summary": summary,
            "model_used": model_name,
            "tokens_used": response.input_tokens + response.output_tokens,
            "wtu_consumed": (response.input_tokens + response.output_tokens) * 0.001,
            "cost_usd": (response.input_tokens + response.output_tokens) * 0.0001,
            "analysis_metadata": {
                "content_length": len(content),
                "summary_length": len(summary),
                "analysis_type": "generic_summary"
            }
        }
        
        logger.info(f"Generic content analysis completed: {len(summary)} chars summary generated")
        return result
    
    async def _select_model(self, user_preferences) -> str:
        """사용자 선호도에 따른 모델 선택"""
        # 기본 모델 설정
        default_model = "gpt-4o-mini"
        
        # 사용자 기본 모델이 있으면 사용
        if user_preferences.default_llm_model:
            return user_preferences.default_llm_model
        
        # 품질 선호도에 따른 모델 선택
        if user_preferences.quality_preference == "quality":
            return "gpt-4o"
        elif user_preferences.quality_preference == "speed":
            return "gpt-4o-mini"
        
        return default_model