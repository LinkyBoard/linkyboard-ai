"""
Board AI 서비스 - 선택된 아이템 기반 AI 작업
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date

from app.metrics.model_catalog_service import model_catalog_service
from app.core.logging import get_logger
from app.metrics import count_tokens
from app.ai.openai_service import openai_service
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
        사용 가능한 모델 목록과 비용 정보 반환
        """
        try:
            # 활성 LLM 모델들 조회
            active_models = await model_catalog_service.get_active_models("llm")
            
            models = []
            default_model = None
            
            for model in active_models:
                # WTU 비용 계산 (1K 토큰 기준)
                input_cost_per_1k = (model.weight_input or 1.0) * 1000
                output_cost_per_1k = (model.weight_output or 4.0) * 1000
                
                is_default = model.alias == "GPT-4o Mini"  # 기본 추천 모델
                if is_default and not default_model:
                    default_model = model.alias
                
                models.append({
                    "alias": model.alias,
                    "model_name": model.model_name,
                    "provider": model.provider,
                    "description": getattr(model, 'description', None),
                    "input_cost_per_1k": input_cost_per_1k,
                    "output_cost_per_1k": output_cost_per_1k,
                    "is_default": is_default
                })
            
            # 비용 순으로 정렬 (입력+출력 평균 비용 기준)
            models.sort(key=lambda x: (x["input_cost_per_1k"] + x["output_cost_per_1k"]) / 2)
            
            return {
                "models": models,
                "total_count": len(models),
                "default_model": default_model
            }
            
        except Exception as e:
            logger.error(f"Failed to get available models: {str(e)}")
            raise

    async def estimate_task_cost(
        self,
        selected_items: List[int],
        task_description: str,
        board_id: UUID,
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
        board_id: UUID,
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
            
            # AI 호출
            ai_result = await openai_service.generate_chat_completion(
                messages=messages,
                model=model.model_name,
                max_tokens=max_output_tokens,
                temperature=0.7,
                user_id=user_id,
                board_id=str(board_id)
            )
            
            return {
                "answer_md": ai_result["content"],
                "used_items": used_items,
                "usage": {
                    "input_tokens": ai_result["input_tokens"],
                    "output_tokens": ai_result["output_tokens"],
                    "total_tokens": ai_result["input_tokens"] + ai_result["output_tokens"]
                },
                "model_info": {
                    "alias": model.alias,
                    "model_name": model.model_name,
                    "provider": model.provider
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
        board_id: UUID,
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
            
            # AI 프롬프트 구성
            system_prompt = f"""당신은 전문적인 콘텐츠 작성자입니다. 
제공된 자료들을 바탕으로 초안을 작성해주세요.

**작성 요구사항:**
{requirements}

**참고 자료들:**
{chr(10).join(source_materials)}

다음 지침을 따라 초안을 작성해주세요:
1. 마크다운 형식으로 작성
2. 제공된 자료들의 내용을 적절히 활용
3. 논리적이고 일관된 구조로 구성
4. 참고한 자료의 출처를 명시
5. 적절한 길이로 작성"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "초안을 작성해주세요."}
            ]
            
            # AI 호출
            ai_result = await openai_service.generate_chat_completion(
                messages=messages,
                model=model.model_name,
                max_tokens=2000,  # 기본값으로 설정
                temperature=0.3,  
                user_id=user_id,
                board_id=str(board_id)
            )
            
            return {
                "draft_md": ai_result["content"],
                "used_items": used_items,
                "usage": {
                    "input_tokens": ai_result["input_tokens"],
                    "output_tokens": ai_result["output_tokens"],
                    "total_tokens": ai_result["input_tokens"] + ai_result["output_tokens"]
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


# 전역 서비스 인스턴스
board_ai_service = BoardAIService()


def get_board_ai_service() -> BoardAIService:
    """BoardAIService 인스턴스 반환"""
    return board_ai_service