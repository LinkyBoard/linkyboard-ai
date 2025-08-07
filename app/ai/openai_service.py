import openai
from typing import List, Dict, Any
from app.core.config import settings


class OpenAIService:
    """OpenAI API 연동 서비스"""
    
    def __init__(self, api_key: str):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate_webpage_tags(
        self, 
        summary: str,
        similar_tags: List[str] = None,
        tag_count: int = 5,
        max_tokens: int = 100
    ) -> List[str]:
        """웹페이지 태그 생성"""
        try:
            
            prompt = f"""
            다음 웹페이지 내용을 분석하여 {tag_count}개의 태그를 생성해주세요.
            바로 저장할 수 있도록 태그만 작성해주세요.
            각 태그는 쉼표로 구분해주세요.
            태그는 한글 또는 영어의 명사형 단어로 작성해주세요.
            사용자가 이전에 저장한 유사 태그가 있다면, 그 태그도 함께 고려해주세요.
            {', '.join(similar_tags) if similar_tags else '없음'}
            
            summary: {summary}
            """
            
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "당신은 웹페이지 내용을 분석하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            return [k.strip() for k in content.split(',') if k.strip()]
            
        except Exception as e:
            raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")

    async def recommend_webpage_category(
        self,
        summary: str,
        similar_categories: List[str] = None,
        max_tokens: int = 100
    ) -> str:
        """웹페이지 카테고리 추천"""
        try:
            prompt = f"""
            다음 웹페이지 내용을 분석하여 적절한 단 하나의 카테고리를 추천해주세요.
            바로 저장할 수 있도록 카테고리만 작성해주세요.
            사용자가 이전에 저장한 유사 카테고리가 있다면, 그 카테고리도 함께 고려해주세요.
            {', '.join(similar_categories) if similar_categories else '없음'}
            카테고리는 반드시 하나여야 하며, 여러 개의 카테고리를 추천하지 마세요.
            사용자가 이전에 저장한 카테고리중 적합한게 없다면 새로 추천해주세요.

            summary: {summary}
            """
            
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "당신은 웹페이지 내용을 분석하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )
            
            content = response.choices[0].message.content.strip()
            return content
            
        except Exception as e:
            raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")

    async def generate_webpage_summary(
        self,
        url: str,
        html_content: str,
        max_tokens: int = 500
    ) -> Dict[str, Any]:
        """웹페이지 요약 생성"""
        try:
            # text_content = self._extract_text_from_html(html_content)

            prompt = f"""
            다음 웹페이지 내용을 분석하여 요약을 생성해주세요.
            바로 저장할 수 있도록 요약만 작성해주세요.
            
            URL: {url}
            """
            
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "당신은 웹페이지 내용을 분석하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )

            content = response.choices[0].message.content.strip()
            return content
            
        except Exception as e:
            raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")
    
    def _extract_text_from_html(self, html_content: str) -> str:
        """HTML에서 텍스트 추출"""
        import re
        text = re.sub(r'<[^>]+>', '', html_content)
        text = re.sub(r'\s+', ' ', text).strip()
        return text


# 서비스 인스턴스 생성
openai_service = OpenAIService(api_key=settings.OPENAI_API_KEY)
