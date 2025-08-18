"""
스마트 태그/카테고리 추출 서비스
OpenAI 대신 로컬 NLP + 사용자 히스토리 기반 추출 시스템
"""

from typing import List, Dict, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.logging import get_logger
from app.core.models import Item
from app.ai.content_extraction import HTMLContentExtractor, KeywordExtractor
from app.ai.content_extraction.recommendation_engine import RecommendationEngine

logger = get_logger(__name__)


class SmartExtractionService:
    """
    HTML 파싱 + NLP + 사용자 히스토리를 결합한 스마트 추출 서비스
    OpenAI 대신 비용 효율적인 로컬 처리 방식 사용
    """
    
    def __init__(self):
        """스마트 추출 서비스 초기화"""
        self.html_extractor = HTMLContentExtractor()
        self.keyword_extractor = KeywordExtractor()
        self.recommendation_engine = RecommendationEngine()
        
        logger.info("SmartExtractionService initialized")
    
    async def extract_tags_and_category(
        self,
        html_content: str,
        url: Optional[str] = None,
        user_id: Optional[int] = None,
        max_tags: int = 5,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        HTML 콘텐츠에서 태그와 카테고리를 추출합니다.
        
        Args:
            html_content: HTML 콘텐츠
            url: 웹페이지 URL
            user_id: 사용자 ID (히스토리 조회용)
            max_tags: 최대 태그 개수
            session: 데이터베이스 세션
            
        Returns:
            태그와 카테고리 추출 결과
        """
        try:
            # 1. HTML에서 핵심 콘텐츠 추출
            logger.info(f"Extracting content from HTML (length: {len(html_content)})")
            content_info = self.html_extractor.extract_content(html_content, url)
            
            extracted_content = content_info['content']
            content_title = content_info['title']
            
            if not extracted_content:
                logger.warning("No content extracted from HTML")
                return self._get_fallback_result()
            
            logger.info(f"Extracted content: {content_info['char_count']} chars, "
                       f"method: {content_info['extraction_method']}")
            
            # 2. 키워드 추출
            logger.info("Extracting keywords from content")
            keywords = self.keyword_extractor.extract_keywords(
                text=extracted_content,
                max_keywords=max_tags * 2,  # 추천 엔진에서 필터링하므로 더 많이 추출
                min_length=2,
                include_phrases=True
            )
            
            if not keywords:
                logger.warning("No keywords extracted")
                return self._get_fallback_result(content_title=content_title)
            
            logger.info(f"Extracted {len(keywords)} keywords")
            
            # 3. 사용자 히스토리 조회 (있는 경우)
            user_history_tags = []
            user_history_categories = []
            
            if user_id and session:
                user_history = await self._get_user_history(user_id, session)
                user_history_tags = user_history['tags']
                user_history_categories = user_history['categories']
                
                logger.info(f"User history: {len(user_history_tags)} tags, "
                           f"{len(user_history_categories)} categories")
            
            # 4. 태그 추천
            recommended_tags = self.recommendation_engine.recommend_tags(
                extracted_keywords=keywords,
                user_history_tags=user_history_tags,
                max_recommendations=max_tags,
                similarity_threshold=0.3
            )
            
            # 5. 카테고리 추천
            recommended_category = self.recommendation_engine.recommend_category(
                extracted_keywords=keywords,
                user_history_categories=user_history_categories,
                content_title=content_title,
                similarity_threshold=0.4
            )
            
            # 6. 결과 구성
            result = {
                'tags': [tag_info['tag'] for tag_info in recommended_tags],
                'category': recommended_category['category'],
                'metadata': {
                    'content_info': {
                        'title': content_title,
                        'char_count': content_info['char_count'],
                        'word_count': content_info['word_count'],
                        'extraction_method': content_info['extraction_method']
                    },
                    'keyword_extraction': {
                        'keywords_found': len(keywords),
                        'top_keywords': [kw['keyword'] for kw in keywords[:5]]
                    },
                    'recommendation_details': {
                        'tags': recommended_tags,
                        'category': recommended_category,
                        'user_history_used': len(user_history_tags) > 0
                    },
                    'processing_method': 'smart_extraction',
                    'cost_savings': True  # OpenAI 사용하지 않음을 표시
                }
            }
            
            logger.info(f"Smart extraction completed - tags: {len(result['tags'])}, "
                       f"category: {result['category']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Smart extraction failed: {e}")
            return self._get_fallback_result(content_title=content_title if 'content_title' in locals() else None)
    
    async def extract_tags_from_summary(
        self,
        summary: str,
        user_id: Optional[int] = None,
        max_tags: int = 5,
        session: Optional[AsyncSession] = None
    ) -> List[str]:
        """
        요약문에서 태그를 추출합니다 (기존 API 호환성 유지)
        
        Args:
            summary: 요약 텍스트
            user_id: 사용자 ID
            max_tags: 최대 태그 개수
            session: 데이터베이스 세션
            
        Returns:
            추출된 태그 리스트
        """
        try:
            # 키워드 추출
            keywords = self.keyword_extractor.extract_keywords(
                text=summary,
                max_keywords=max_tags * 2,
                min_length=2,
                include_phrases=False
            )
            
            # 사용자 히스토리 조회
            user_history_tags = []
            if user_id and session:
                user_history = await self._get_user_history(user_id, session)
                user_history_tags = user_history['tags']
            
            # 태그 추천
            recommended_tags = self.recommendation_engine.recommend_tags(
                extracted_keywords=keywords,
                user_history_tags=user_history_tags,
                max_recommendations=max_tags
            )
            
            return [tag_info['tag'] for tag_info in recommended_tags]
            
        except Exception as e:
            logger.error(f"Tag extraction from summary failed: {e}")
            # Fallback: 간단한 키워드 추출
            return self._extract_simple_tags(summary, max_tags)
    
    async def classify_category_from_summary(
        self,
        summary: str,
        user_id: Optional[int] = None,
        session: Optional[AsyncSession] = None
    ) -> str:
        """
        요약문에서 카테고리를 분류합니다 (기존 API 호환성 유지)
        
        Args:
            summary: 요약 텍스트
            user_id: 사용자 ID
            session: 데이터베이스 세션
            
        Returns:
            추천된 카테고리
        """
        try:
            # 키워드 추출
            keywords = self.keyword_extractor.extract_keywords(
                text=summary,
                max_keywords=10,
                min_length=2,
                include_phrases=False
            )
            
            # 사용자 히스토리 조회
            user_history_categories = []
            if user_id and session:
                user_history = await self._get_user_history(user_id, session)
                user_history_categories = user_history['categories']
            
            # 카테고리 추천
            recommended_category = self.recommendation_engine.recommend_category(
                extracted_keywords=keywords,
                user_history_categories=user_history_categories,
                content_title="",
                similarity_threshold=0.4
            )
            
            return recommended_category['category']
            
        except Exception as e:
            logger.error(f"Category classification from summary failed: {e}")
            return '기타'
    
    async def _get_user_history(self, user_id: int, session: AsyncSession) -> Dict[str, List[str]]:
        """사용자의 태그/카테고리 히스토리 조회"""
        try:
            # 최근 100개 아이템의 태그와 카테고리 조회
            stmt = select(Item.tags, Item.category).where(
                Item.user_id == user_id,
                Item.tags.is_not(None),
                Item.category.is_not(None),
                Item.is_active == True
            ).order_by(Item.created_at.desc()).limit(100)
            
            result = await session.execute(stmt)
            items = result.fetchall()
            
            # 태그 리스트 평면화
            all_tags = []
            all_categories = []
            
            for item in items:
                if item.tags:
                    all_tags.extend(item.tags)
                if item.category:
                    all_categories.append(item.category)
            
            return {
                'tags': all_tags,
                'categories': all_categories
            }
            
        except Exception as e:
            logger.error(f"Failed to get user history: {e}")
            return {'tags': [], 'categories': []}
    
    def _get_fallback_result(self, content_title: Optional[str] = None) -> Dict[str, Any]:
        """추출 실패 시 fallback 결과"""
        return {
            'tags': ['웹페이지'] if not content_title else [content_title.split()[0] if content_title.split() else '웹페이지'],
            'category': '기타',
            'metadata': {
                'content_info': {
                    'title': content_title or 'Untitled',
                    'char_count': 0,
                    'word_count': 0,
                    'extraction_method': 'fallback'
                },
                'keyword_extraction': {
                    'keywords_found': 0,
                    'top_keywords': []
                },
                'recommendation_details': {
                    'tags': [],
                    'category': {'category': '기타', 'confidence': 0.1, 'method': 'fallback'},
                    'user_history_used': False
                },
                'processing_method': 'fallback',
                'cost_savings': True
            }
        }
    
    def _extract_simple_tags(self, text: str, max_tags: int) -> List[str]:
        """간단한 태그 추출 (완전 fallback)"""
        try:
            import re
            
            # 2글자 이상 단어 추출
            words = re.findall(r'[가-힣a-zA-Z]{2,}', text)
            
            # 빈도 계산
            from collections import Counter
            word_counts = Counter(words)
            
            # 상위 태그 반환
            return [word for word, _ in word_counts.most_common(max_tags)]
            
        except Exception:
            return ['기본태그']
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """처리 통계 정보 반환"""
        return {
            'html_extractor_available': self.html_extractor.available,
            'keyword_extractor_capabilities': {
                'spacy': self.keyword_extractor.spacy_available,
                'sklearn': self.keyword_extractor.sklearn_available,
                'konlpy': self.keyword_extractor.konlpy_available
            },
            'recommendation_engine_available': self.recommendation_engine.similarity_available,
            'estimated_cost_savings': '90%',  # vs OpenAI
            'processing_time_improvement': '50%'  # vs API calls
        }


# 전역 서비스 인스턴스
smart_extraction_service = SmartExtractionService()