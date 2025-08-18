"""
HTML 콘텐츠 추출 서비스
trafilatura를 사용하여 웹페이지에서 핵심 콘텐츠를 추출합니다.
"""

import re
from typing import Dict, Any, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


class HTMLContentExtractor:
    """HTML에서 핵심 콘텐츠를 추출하는 서비스"""
    
    def __init__(self):
        """HTML 콘텐츠 추출기 초기화"""
        try:
            # trafilatura가 설치되어 있는지 확인하고 import
            import trafilatura
            from bs4 import BeautifulSoup
            
            self.trafilatura = trafilatura
            self.BeautifulSoup = BeautifulSoup
            self.available = True
            logger.info("HTML content extractor initialized with trafilatura and BeautifulSoup")
            
        except ImportError as e:
            logger.warning(f"trafilatura or BeautifulSoup not available: {e}")
            self.available = False
    
    def extract_content(self, html_content: str, url: Optional[str] = None) -> Dict[str, Any]:
        """
        HTML에서 핵심 콘텐츠를 추출합니다.
        
        Args:
            html_content: 원본 HTML 콘텐츠
            url: 웹페이지 URL (선택사항)
            
        Returns:
            Dict containing extracted content, title, and metadata
        """
        try:
            if not self.available:
                # Fallback to basic extraction
                return self._extract_content_fallback(html_content)
            
            # trafilatura를 사용한 고급 추출
            extracted_text = self.trafilatura.extract(
                html_content,
                include_comments=False,
                include_tables=True,
                include_formatting=False,
                output_format='txt'
            )
            
            # 메타데이터 추출
            metadata = self.trafilatura.extract_metadata(html_content, fast=True)
            
            # 제목 추출
            title = None
            if metadata:
                title = metadata.title
            
            if not title:
                title = self._extract_title_fallback(html_content)
            
            # 텍스트 정제
            if extracted_text:
                cleaned_text = self._clean_text(extracted_text)
            else:
                # trafilatura 실패 시 fallback
                fallback_result = self._extract_content_fallback(html_content)
                cleaned_text = fallback_result['content']
                title = title or fallback_result['title']
            
            return {
                'content': cleaned_text,
                'title': title or 'Untitled',
                'word_count': len(cleaned_text.split()) if cleaned_text else 0,
                'char_count': len(cleaned_text) if cleaned_text else 0,
                'extraction_method': 'trafilatura'
            }
            
        except Exception as e:
            logger.warning(f"trafilatura extraction failed: {e}, using fallback")
            return self._extract_content_fallback(html_content)
    
    def _extract_content_fallback(self, html_content: str) -> Dict[str, Any]:
        """
        trafilatura 사용할 수 없을 때의 fallback 추출 방법
        BeautifulSoup를 사용한 기본 추출
        """
        try:
            if not self.available:
                # 매우 기본적인 HTML 태그 제거
                return self._extract_content_basic(html_content)
            
            soup = self.BeautifulSoup(html_content, 'html.parser')
            
            # 불필요한 태그 제거
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'advertisement']):
                tag.decompose()
            
            # 제목 추출
            title = None
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
            
            if not title:
                # h1 태그에서 제목 찾기
                h1_tag = soup.find('h1')
                if h1_tag:
                    title = h1_tag.get_text().strip()
            
            # 본문 추출 시도
            content = None
            
            # 일반적인 본문 컨테이너들
            content_selectors = [
                'article', 'main', '.content', '.post', '.entry',
                '.article-body', '.post-content', '#content'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text()
                    break
            
            # 본문을 찾지 못했으면 body에서 추출
            if not content:
                body = soup.find('body')
                if body:
                    content = body.get_text()
                else:
                    content = soup.get_text()
            
            # 텍스트 정제
            cleaned_content = self._clean_text(content) if content else ''
            
            return {
                'content': cleaned_content,
                'title': title or 'Untitled',
                'word_count': len(cleaned_content.split()),
                'char_count': len(cleaned_content),
                'extraction_method': 'beautifulsoup_fallback'
            }
            
        except Exception as e:
            logger.error(f"BeautifulSoup extraction failed: {e}")
            return self._extract_content_basic(html_content)
    
    def _extract_content_basic(self, html_content: str) -> Dict[str, Any]:
        """
        가장 기본적인 HTML 태그 제거 방식
        모든 라이브러리 사용 불가 시 사용
        """
        try:
            # HTML 태그 제거
            text = re.sub(r'<[^>]+>', '', html_content)
            
            # 제목 추출 시도
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else 'Untitled'
            
            # 텍스트 정제
            cleaned_text = self._clean_text(text)
            
            return {
                'content': cleaned_text,
                'title': title,
                'word_count': len(cleaned_text.split()),
                'char_count': len(cleaned_text),
                'extraction_method': 'basic_regex'
            }
            
        except Exception as e:
            logger.error(f"Basic extraction failed: {e}")
            return {
                'content': '',
                'title': 'Untitled',
                'word_count': 0,
                'char_count': 0,
                'extraction_method': 'failed'
            }
    
    def _extract_title_fallback(self, html_content: str) -> Optional[str]:
        """BeautifulSoup를 사용한 제목 추출"""
        try:
            soup = self.BeautifulSoup(html_content, 'html.parser')
            
            # title 태그 우선
            title_tag = soup.find('title')
            if title_tag and title_tag.get_text().strip():
                return title_tag.get_text().strip()
            
            # h1 태그 차선
            h1_tag = soup.find('h1')
            if h1_tag and h1_tag.get_text().strip():
                return h1_tag.get_text().strip()
            
            return None
            
        except Exception:
            return None
    
    def _clean_text(self, text: str) -> str:
        """
        추출된 텍스트를 정제합니다.
        
        Args:
            text: 정제할 텍스트
            
        Returns:
            정제된 텍스트
        """
        if not text:
            return ''
        
        # HTML 엔티티 디코딩
        text = re.sub(r'&[a-zA-Z0-9#]+;', ' ', text)
        
        # 연속된 공백 제거
        text = re.sub(r'\s+', ' ', text)
        
        # 연속된 줄바꿈 제거 (최대 2개까지만 허용)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 앞뒤 공백 제거
        text = text.strip()
        
        return text
    
    def get_content_preview(self, content: str, max_length: int = 200) -> str:
        """
        콘텐츠 미리보기를 생성합니다.
        
        Args:
            content: 전체 콘텐츠
            max_length: 최대 길이
            
        Returns:
            미리보기 텍스트
        """
        if not content:
            return ''
        
        if len(content) <= max_length:
            return content
        
        # 단어 경계에서 자르기
        preview = content[:max_length]
        last_space = preview.rfind(' ')
        
        if last_space > max_length * 0.8:  # 80% 이상이면 단어 경계에서 자르기
            preview = preview[:last_space]
        
        return preview + '...'