import re
from typing import Optional, Dict, Any
from app.embedding.interfaces import ContentProcessor
from app.core.logging import get_logger

logger = get_logger("html_processor")


class HTMLProcessor(ContentProcessor):
    """HTML 콘텐츠 전처리기"""
    
    def get_content_type(self) -> str:
        return "html"
    
    async def process(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        HTML 콘텐츠에서 불필요한 부분 제거하고 텍스트만 추출
        """
        try:
            logger.info(f"Processing HTML content (length: {len(content)})")
            
            # HTML 태그 제거
            text = self._remove_html_tags(content)
            
            # 스크립트 및 스타일 태그 제거
            text = self._remove_script_style(text)
            
            # 여러 공백을 하나로 변환
            text = re.sub(r'\s+', ' ', text)
            
            # 특수 HTML 엔티티 변환
            text = self._decode_html_entities(text)
            
            # 앞뒤 공백 제거
            text = text.strip()
            
            # 너무 긴 경우 안전하게 자르기
            max_chars = 50000  # 안전 제한
            if len(text) > max_chars:
                text = text[:max_chars] + "..."
                logger.warning(f"Content truncated to {max_chars} characters")
            
            logger.info(f"HTML processing completed (output length: {len(text)})")
            return text
            
        except Exception as e:
            logger.error(f"Failed to process HTML content: {str(e)}")
            # 실패 시 원본의 일부라도 반환
            return content[:10000] if len(content) > 10000 else content
    
    def _remove_html_tags(self, html: str) -> str:
        """HTML 태그 제거"""
        # script와 style 태그는 내용까지 완전히 제거
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # 나머지 HTML 태그 제거
        text = re.sub(r'<[^>]+>', ' ', html)
        return text
    
    def _remove_script_style(self, text: str) -> str:
        """스크립트와 스타일 관련 잔여물 제거"""
        # JavaScript 코드 패턴 제거
        text = re.sub(r'function\s*\([^)]*\)\s*\{[^}]*\}', '', text)
        text = re.sub(r'var\s+\w+\s*=.*?;', '', text)
        text = re.sub(r'document\.\w+.*?;', '', text)
        
        # CSS 관련 패턴 제거
        text = re.sub(r'\w+\s*:\s*[^;]+;', '', text)
        text = re.sub(r'@\w+[^{]*\{[^}]*\}', '', text)
        
        return text
    
    def _decode_html_entities(self, text: str) -> str:
        """HTML 엔티티 디코딩"""
        html_entities = {
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&apos;': "'",
            '&nbsp;': ' ',
            '&#8217;': "'",
            '&#8220;': '"',
            '&#8221;': '"',
            '&#8230;': '...',
        }
        
        for entity, char in html_entities.items():
            text = text.replace(entity, char)
        
        # 숫자 HTML 엔티티 처리 (예: &#123;)
        text = re.sub(r'&#\d+;', ' ', text)
        
        return text


class TextProcessor(ContentProcessor):
    """일반 텍스트 전처리기"""
    
    def get_content_type(self) -> str:
        return "text"
    
    async def process(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """텍스트 콘텐츠 정규화"""
        try:
            logger.info(f"Processing text content (length: {len(content)})")
            
            # 여러 줄바꿈을 하나로 변환
            text = re.sub(r'\n+', '\n', content)
            
            # 여러 공백을 하나로 변환
            text = re.sub(r' +', ' ', text)
            
            # 앞뒤 공백 제거
            text = text.strip()
            
            logger.info(f"Text processing completed (output length: {len(text)})")
            return text
            
        except Exception as e:
            logger.error(f"Failed to process text content: {str(e)}")
            return content
