"""
Board AI 서비스 - 선택된 아이템 기반 AI 작업
"""

from typing import Optional, Dict, Any, List
# from uuid import UUID - 더 이상 UUID 사용하지 않음
from datetime import date

from app.metrics.model_catalog_service import model_catalog_service
from app.core.logging import get_logger
from app.metrics import count_tokens
from app.ai.providers.router import ai_router
from app.core.database import AsyncSessionLocal
from app.core.models import Item
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.board_ai.schemas import SelectedItem

logger = get_logger(__name__)


class BoardAIService:
    """Board AI 서비스 - 선택된 아이템 기반 AI 작업"""

    async def get_available_models(self) -> Dict[str, Any]:
        """
        사용 가능한 모델 목록과 비용 정보 반환 (AI Router 통합)
        """
        try:
            # AI Router를 통해 사용 가능한 모델들 조회
            models = await ai_router.get_available_models("llm")
            
            default_model = None
            
            for model in models:
                # 기본 추천 모델 설정 (가장 저렴한 모델 우선)
                is_default = model["alias"] in ["GPT-4o Mini", "Gemini 1.5 Flash", "Claude 3 Haiku"]
                model["is_default"] = is_default
                
                if is_default and not default_model:
                    default_model = model["alias"]
            
            # 비용 순으로 정렬 (입력+출력 평균 비용 기준)
            models.sort(key=lambda x: (x["input_cost_per_1k"] + x["output_cost_per_1k"]) / 2)
            
            return {
                "models": models,
                "total_count": len(models),
                "default_model": default_model,
                "available_providers": ai_router.get_available_providers()
            }
            
        except Exception as e:
            logger.error(f"Failed to get available models: {str(e)}")
            raise

    async def estimate_task_cost(
        self,
        selected_items: List[int],
        task_description: str,
        board_id: int,
        user_id: int,
        estimated_output_tokens: int = 1500,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        선택된 아이템들을 기반으로 작업 비용 추정
        """
        close_session = False
        if session is None:
            session = AsyncSessionLocal()
            close_session = True
            
        try:
            # 선택된 아이템들의 내용 조회
            if selected_items:
                stmt = select(Item).where(Item.id.in_(selected_items))
                result = await session.execute(stmt)
                items = result.scalars().all()
            else:
                items = []
            
            # 전체 콘텐츠 길이 계산
            total_content = ""
            for item in items:
                if item.summary:
                    total_content += f"{item.title}: {item.summary}\n"
                if item.raw_content:
                    # raw_content는 원본 콘텐츠이므로 길이 제한
                    content_preview = item.raw_content[:500] if len(item.raw_content) > 500 else item.raw_content
                    total_content += f"Content: {content_preview}\n"
            
            # 작업 설명 추가
            total_content += f"\nTask: {task_description}\n"
            
            # 활성 LLM 모델들 조회
            active_models = await model_catalog_service.get_active_models("llm")
            
            estimates = []
            for model in active_models:
                # 입력 토큰 계산
                input_tokens = count_tokens(total_content, model.model_name)
                
                # WTU 비용 계산
                estimated_wtu = int(
                    input_tokens * (model.weight_input or 1.0) + 
                    estimated_output_tokens * (model.weight_output or 4.0)
                )
                
                # GPT-4o Mini를 추천 모델로 설정
                is_recommended = model.alias == "GPT-4o Mini"
                
                estimates.append({
                    "model_alias": model.alias,
                    "model_name": model.model_name,
                    "provider": model.provider,
                    "estimated_input_tokens": input_tokens,
                    "estimated_output_tokens": estimated_output_tokens,
                    "estimated_wtu_cost": estimated_wtu,
                    "is_recommended": is_recommended
                })
            
            # 비용 순으로 정렬
            estimates.sort(key=lambda x: x["estimated_wtu_cost"])
            
            return {
                "estimates": estimates,
                "total_selected_items": len(selected_items),
                "total_content_length": len(total_content)
            }
            
        except Exception as e:
            logger.error(f"Failed to estimate task cost: {str(e)}")
            raise
        finally:
            if close_session:
                await session.close()

    async def ask_with_selected_items(
        self,
        query: str,
        instruction: str,
        selected_items: List[SelectedItem],
        board_id: int,
        user_id: int,
        model_alias: str,
        max_output_tokens: int = 1500,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        선택된 아이템들을 기반으로 한 AI 질의
        """
        close_session = False
        if session is None:
            session = AsyncSessionLocal()
            close_session = True
            
        try:
            # 모델 정보 조회
            model = await model_catalog_service.get_model_by_alias(model_alias)
            if not model:
                raise ValueError(f"Model '{model_alias}' not found")
            
            # 선택된 아이템들의 내용 조회
            item_ids = [item.item_id for item in selected_items]
            if item_ids:
                stmt = select(Item).where(Item.id.in_(item_ids))
                result = await session.execute(stmt)
                items = result.scalars().all()
                items_dict = {item.id: item for item in items}
            else:
                items_dict = {}
            
            # 아이템 내용 구성
            context_parts = []
            used_items = []
            
            for selected_item in selected_items:
                item = items_dict.get(selected_item.item_id)
                if not item:
                    continue
                
                item_context = f"## {item.title}\n"
                
                if selected_item.include_summary and item.summary:
                    item_context += f"**요약:** {item.summary}\n\n"
                
                if selected_item.include_content and item.raw_content:
                    # raw_content는 원본 콘텐츠이므로 길이 제한 (5000자)
                    content = item.raw_content[:5000] if len(item.raw_content) > 5000 else item.raw_content
                    item_context += f"**내용:** {content}\n\n"
                
                context_parts.append(item_context)
                used_items.append({
                    "item_id": item.id,
                    "title": item.title,
                    "url": item.source_url,
                    "included_summary": selected_item.include_summary,
                    "included_content": selected_item.include_content
                })
            
            # 전체 컨텍스트 구성
            full_context = "\n".join(context_parts)
            
            # AI 프롬프트 구성
            system_prompt = f"""당신은 도움이 되는 AI 어시스턴트입니다. 
사용자가 제공한 아이템들의 내용을 바탕으로 질의에 답변해주세요.

**작업 지시사항:**
{instruction}

**제공된 자료들:**
{full_context}

답변은 마크다운 형식으로 작성하고, 제공된 자료를 참고했음을 명시해주세요.
최대 {max_output_tokens} 토큰 내에서 답변하세요."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
            
            # AI Router를 통해 AI 호출
            ai_response = await ai_router.generate_chat_completion(
                messages=messages,
                model=model.model_name,
                max_tokens=max_output_tokens,
                temperature=0.7,
                user_id=user_id,
                board_id=board_id,
                session=session
            )
            
            return {
                "answer_md": ai_response.content,
                "used_items": used_items,
                "usage": {
                    "input_tokens": ai_response.input_tokens,
                    "output_tokens": ai_response.output_tokens,
                    "total_tokens": ai_response.input_tokens + ai_response.output_tokens
                },
                "model_info": {
                    "alias": model.alias,
                    "model_name": ai_response.model_used,
                    "provider": ai_response.provider
                }
            }
            
        except Exception as e:
            logger.error(f"Ask with items failed: {str(e)}")
            raise
        finally:
            if close_session:
                await session.close()

    async def draft_with_selected_items(
        self,
        requirements: str,
        selected_items: List[int],
        board_id: int,
        user_id: int,
        model_alias: str,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        선택된 아이템들을 기반으로 한 초안 작성
        """
        close_session = False
        if session is None:
            session = AsyncSessionLocal()
            close_session = True
            
        try:
            # 모델 정보 조회
            model = await model_catalog_service.get_model_by_alias(model_alias)
            if not model:
                raise ValueError(f"Model '{model_alias}' not found")
            
            # 선택된 아이템들의 내용 조회
            if selected_items:
                stmt = select(Item).where(Item.id.in_(selected_items))
                result = await session.execute(stmt)
                items = result.scalars().all()
                items_dict = {item.id: item for item in items}
            else:
                items_dict = {}
            
            # 아이템 내용 구성 (모든 summary와 content 포함)
            source_materials = []
            used_items = []
            
            for item_id in selected_items:
                item = items_dict.get(item_id)
                if not item:
                    continue
                
                material = f"## {item.title}\n"
                material += f"**출처:** {item.source_url}\n"
                
                # 기본적으로 summary 포함
                if item.summary:
                    material += f"**요약:** {item.summary}\n\n"
                
                # 기본적으로 content 포함
                if item.raw_content:
                    # raw_content는 원본 콘텐츠이므로 길이 제한 (3000자)
                    content = item.raw_content[:3000] if len(item.raw_content) > 3000 else item.raw_content
                    material += f"**내용:** {content}\n\n"
                
                source_materials.append(material)
                used_items.append({
                    "item_id": item.id,
                    "title": item.title,
                    "url": item.source_url,
                    "included_summary": True,  # 항상 True
                    "included_content": True   # 항상 True
                })
            
            # AI 프롬프트 구성 (제목과 초안을 함께 생성)
            system_prompt = f"""당신은 전문적인 콘텐츠 작성자입니다. 
제공된 자료들을 바탕으로 적절한 제목과 초안을 작성해주세요.

**작성 요구사항:**
{requirements}

**참고 자료들:**
{chr(10).join(source_materials)}

다음 JSON 형식으로 정확히 응답해주세요:
{{
  "title": "작성 요구사항과 참고 자료를 바탕으로 한 적절한 제목 (한 줄로 작성)",
  "content": "마크다운 형식의 초안 내용"
}}

지침:
1. 제목은 간결하고 내용을 잘 요약해야 함
2. 초안은 마크다운 형식으로 작성
3. 제공된 자료들의 내용을 적절히 활용
4. 논리적이고 일관된 구조로 구성
5. 참고한 자료의 출처를 명시
6. 반드시 정확한 JSON 형식으로 응답"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "제목과 초안을 JSON 형식으로 작성해주세요."}
            ]
            
            # AI Router를 통해 AI 호출
            ai_result = await ai_router.generate_chat_completion(
                messages=messages,
                model=model.model_name,
                max_tokens=2500,  # 제목과 내용을 위해 증가
                temperature=0.3,  
                user_id=user_id,
                board_id=board_id,
                session=session
            )
            
            # JSON 응답 파싱 시도
            title = "초안"  # 기본 제목
            draft_content = ai_result.content
            
            try:
                import json
                import re
                
                # JSON 부분만 추출 (```json ... ``` 형태 또는 직접 JSON)
                content = ai_result.content.strip()
                
                # 코드 블록 제거
                if content.startswith("```"):
                    # ```json ... ``` 형태에서 JSON 부분 추출
                    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
                    if json_match:
                        content = json_match.group(1)
                
                # JSON 파싱
                parsed_result = json.loads(content)
                
                if isinstance(parsed_result, dict) and "title" in parsed_result and "content" in parsed_result:
                    title = parsed_result["title"].strip()
                    draft_content = parsed_result["content"].strip()
                    logger.info("Successfully parsed structured response with title and content")
                else:
                    logger.warning("JSON response missing required fields, using fallback")
                    
            except (json.JSONDecodeError, KeyError, AttributeError) as e:
                logger.warning(f"Failed to parse JSON response, using fallback: {str(e)}")
                # 제목을 요구사항에서 추출하려 시도
                if requirements and len(requirements) > 10:
                    # 요구사항의 첫 문장이나 핵심 키워드를 제목으로 사용
                    title_candidate = requirements.split('.')[0].split('\n')[0][:50]
                    if title_candidate:
                        title = title_candidate.strip()
            
            # 빈 제목 방지
            if not title or len(title.strip()) == 0:
                title = "생성된 초안"
            
            return {
                "title": title,
                "draft_md": draft_content,
                "used_items": used_items,
                "usage": {
                    "input_tokens": ai_result.input_tokens,
                    "output_tokens": ai_result.output_tokens,
                    "total_tokens": ai_result.input_tokens + ai_result.output_tokens
                },
                "model_info": {
                    "alias": model.alias,
                    "model_name": model.model_name,
                    "provider": model.provider
                }
            }
            
        except Exception as e:
            logger.error(f"Draft with items failed: {str(e)}")
            raise
        finally:
            if close_session:
                await session.close()

    async def _trigger_board_analytics_update(self, board_id: int, user_id: int):
        """
        보드 AI 작업 후 분석 데이터 업데이트 트리거
        """
        try:
            from app.board_analytics.service import board_analytics_service
            
            # 비동기로 분석 업데이트 (stale 마킹)
            await board_analytics_service.mark_analytics_stale(board_id)
            logger.info(f"Marked analytics as stale for board {board_id} after AI operation")
            
        except Exception as e:
            logger.warning(f"Failed to trigger analytics update for board {board_id}: {str(e)}")

    async def get_board_recommendations(
        self,
        board_id: int,
        user_id: int,
        recommendation_type: str = "content_gaps"
    ) -> Dict[str, Any]:
        """
        보드 기반 추천 제안 생성
        """
        try:
            from app.board_analytics.service import board_analytics_service
            
            # 보드 인사이트 조회
            insights = await board_analytics_service.get_board_insights(board_id)
            
            if not insights:
                return {
                    "recommendations": [],
                    "message": "분석 데이터가 부족하여 추천을 생성할 수 없습니다."
                }
            
            recommendations = []
            
            if recommendation_type == "content_gaps":
                # 콘텐츠 부족 영역 기반 추천
                content_gaps = insights.get("content_gaps", [])
                for gap in content_gaps:
                    recommendations.append({
                        "type": "content_improvement",
                        "priority": "medium",
                        "suggestion": gap,
                        "action": "add_content"
                    })
            
            elif recommendation_type == "organization":
                # 조직화 제안 기반 추천
                org_suggestions = insights.get("organization_suggestions", [])
                for suggestion in org_suggestions:
                    recommendations.append({
                        "type": "organization",
                        "priority": "high",
                        "suggestion": suggestion,
                        "action": "reorganize"
                    })
            
            elif recommendation_type == "quality":
                # 품질 개선 추천
                quality_info = insights.get("content_quality", {})
                if quality_info.get("level") == "낮음":
                    recommendations.append({
                        "type": "quality_improvement",
                        "priority": "high",
                        "suggestion": "콘텐츠 품질을 높이기 위해 주제 일관성과 다양성을 개선해보세요.",
                        "action": "improve_quality",
                        "current_score": quality_info.get("score", 0)
                    })
            
            return {
                "board_id": board_id,
                "recommendation_type": recommendation_type,
                "recommendations": recommendations,
                "total_count": len(recommendations),
                "insights_summary": {
                    "content_quality": insights.get("content_quality", {}),
                    "engagement_potential": insights.get("engagement_potential", {})
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to generate board recommendations: {str(e)}")
            return {
                "recommendations": [],
                "error": str(e)
            }


# 전역 서비스 인스턴스
board_ai_service = BoardAIService()


def get_board_ai_service() -> BoardAIService:
    """BoardAIService 인스턴스 반환"""
    return board_ai_service