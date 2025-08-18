"""
사용자 히스토리 기반 태그/카테고리 추천 엔진
"""

import re
from typing import List, Dict, Set, Optional, Tuple
from collections import Counter, defaultdict
from app.core.logging import get_logger

logger = get_logger(__name__)


class RecommendationEngine:
    """사용자 히스토리를 기반으로 태그와 카테고리를 추천하는 엔진"""
    
    def __init__(self):
        """추천 엔진 초기화"""
        self.similarity_available = self._init_similarity()
        logger.info(f"RecommendationEngine initialized - similarity: {self.similarity_available}")
    
    def _init_similarity(self) -> bool:
        """유사도 계산 라이브러리 초기화"""
        try:
            from difflib import SequenceMatcher
            self.SequenceMatcher = SequenceMatcher
            
            # sklearn이 있으면 더 정교한 유사도 계산 가능
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity
                self.TfidfVectorizer = TfidfVectorizer
                self.cosine_similarity = cosine_similarity
                self.sklearn_available = True
            except ImportError:
                self.sklearn_available = False
            
            return True
            
        except ImportError:
            logger.warning("Similarity calculation libraries not available")
            return False
    
    def recommend_tags(
        self,
        extracted_keywords: List[Dict[str, any]],
        user_history_tags: List[str],
        max_recommendations: int = 5,
        similarity_threshold: float = 0.3
    ) -> List[Dict[str, any]]:
        """
        추출된 키워드와 사용자 히스토리를 기반으로 태그를 추천합니다.
        
        Args:
            extracted_keywords: 키워드 추출기에서 추출된 키워드 리스트
            user_history_tags: 사용자의 기존 태그 리스트
            max_recommendations: 최대 추천 개수
            similarity_threshold: 유사도 임계값
            
        Returns:
            추천 태그 리스트 (신뢰도 포함)
        """
        if not extracted_keywords:
            # 키워드가 없으면 인기 태그만 반환
            return self._get_popular_tags(user_history_tags, max_recommendations)
        
        try:
            recommended_tags = []
            used_tags = set()
            
            # 1. 직접 매치 - 추출된 키워드가 기존 태그와 정확히 일치
            direct_matches = self._find_direct_matches(extracted_keywords, user_history_tags)
            for tag_info in direct_matches:
                if tag_info['tag'] not in used_tags:
                    recommended_tags.append(tag_info)
                    used_tags.add(tag_info['tag'])
            
            # 2. 유사도 기반 매치 - 비슷한 태그 찾기
            if len(recommended_tags) < max_recommendations and self.similarity_available:
                similar_matches = self._find_similar_matches(
                    extracted_keywords, 
                    user_history_tags, 
                    similarity_threshold,
                    used_tags
                )
                for tag_info in similar_matches:
                    if len(recommended_tags) >= max_recommendations:
                        break
                    recommended_tags.append(tag_info)
                    used_tags.add(tag_info['tag'])
            
            # 3. 새로운 태그 제안 - 추출된 키워드를 그대로 태그로 제안
            if len(recommended_tags) < max_recommendations:
                new_tag_suggestions = self._suggest_new_tags(extracted_keywords, used_tags)
                for tag_info in new_tag_suggestions:
                    if len(recommended_tags) >= max_recommendations:
                        break
                    recommended_tags.append(tag_info)
                    used_tags.add(tag_info['tag'])
            
            # 4. 인기 태그 보완 - 부족한 경우 자주 사용된 태그로 보완
            if len(recommended_tags) < max_recommendations:
                popular_tags = self._get_popular_tags(user_history_tags, max_recommendations - len(recommended_tags))
                for tag_info in popular_tags:
                    if tag_info['tag'] not in used_tags:
                        recommended_tags.append(tag_info)
            
            # 신뢰도 순으로 정렬
            recommended_tags.sort(key=lambda x: x['confidence'], reverse=True)
            
            return recommended_tags[:max_recommendations]
            
        except Exception as e:
            logger.error(f"Tag recommendation failed: {e}")
            # Fallback: 인기 태그만 반환
            return self._get_popular_tags(user_history_tags, max_recommendations)
    
    def recommend_category(
        self,
        extracted_keywords: List[Dict[str, any]],
        user_history_categories: List[str],
        content_title: str = "",
        similarity_threshold: float = 0.4
    ) -> Dict[str, any]:
        """
        추출된 키워드와 사용자 히스토리를 기반으로 카테고리를 추천합니다.
        
        Args:
            extracted_keywords: 키워드 추출기에서 추출된 키워드 리스트
            user_history_categories: 사용자의 기존 카테고리 리스트
            content_title: 콘텐츠 제목 (추가 컨텍스트)
            similarity_threshold: 유사도 임계값
            
        Returns:
            추천 카테고리 정보 (신뢰도 포함)
        """
        if not user_history_categories:
            # 히스토리가 없으면 기본 카테고리 반환
            return self._get_default_category(extracted_keywords, content_title)
        
        try:
            # 모든 텍스트를 결합하여 분석
            all_text = " ".join([kw['keyword'] for kw in extracted_keywords])
            if content_title:
                all_text = content_title + " " + all_text
            
            # 카테고리별 매치 점수 계산
            category_scores = {}
            
            for category in set(user_history_categories):  # 중복 제거
                score = self._calculate_category_score(
                    all_text, 
                    category, 
                    extracted_keywords,
                    user_history_categories
                )
                category_scores[category] = score
            
            # 최고 점수 카테고리 선택
            if category_scores:
                best_category = max(category_scores, key=category_scores.get)
                best_score = category_scores[best_category]
                
                # 임계값 이상이면 추천
                if best_score >= similarity_threshold:
                    return {
                        'category': best_category,
                        'confidence': round(best_score, 3),
                        'method': 'history_based',
                        'alternatives': self._get_alternative_categories(category_scores, best_category)
                    }
            
            # 임계값 미달이면 새 카테고리 제안
            return self._suggest_new_category(extracted_keywords, content_title)
            
        except Exception as e:
            logger.error(f"Category recommendation failed: {e}")
            return self._get_default_category(extracted_keywords, content_title)
    
    def _find_direct_matches(
        self, 
        extracted_keywords: List[Dict[str, any]], 
        user_tags: List[str]
    ) -> List[Dict[str, any]]:
        """추출된 키워드와 기존 태그의 직접 매치 찾기"""
        matches = []
        user_tags_lower = [tag.lower() for tag in user_tags]
        
        for keyword_info in extracted_keywords:
            keyword = keyword_info['keyword'].lower()
            
            if keyword in user_tags_lower:
                # 원래 케이스 찾기
                original_tag = next(tag for tag in user_tags if tag.lower() == keyword)
                matches.append({
                    'tag': original_tag,
                    'confidence': min(keyword_info['score'] * 1.2, 1.0),  # 직접 매치는 가중치 부여
                    'method': 'direct_match',
                    'source_keyword': keyword_info['keyword']
                })
        
        return matches
    
    def _find_similar_matches(
        self,
        extracted_keywords: List[Dict[str, any]],
        user_tags: List[str],
        threshold: float,
        used_tags: Set[str]
    ) -> List[Dict[str, any]]:
        """유사도 기반 태그 매치 찾기"""
        matches = []
        
        for keyword_info in extracted_keywords:
            keyword = keyword_info['keyword']
            
            for user_tag in user_tags:
                if user_tag in used_tags:
                    continue
                
                # 유사도 계산
                similarity = self._calculate_similarity(keyword, user_tag)
                
                if similarity >= threshold:
                    confidence = (keyword_info['score'] * 0.8) * similarity
                    matches.append({
                        'tag': user_tag,
                        'confidence': round(confidence, 3),
                        'method': 'similarity_match',
                        'similarity': round(similarity, 3),
                        'source_keyword': keyword
                    })
        
        # 신뢰도 순 정렬
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        return matches
    
    def _suggest_new_tags(
        self,
        extracted_keywords: List[Dict[str, any]],
        used_tags: Set[str]
    ) -> List[Dict[str, any]]:
        """추출된 키워드를 새로운 태그로 제안"""
        suggestions = []
        
        for keyword_info in extracted_keywords:
            keyword = keyword_info['keyword']
            
            if keyword not in used_tags and self._is_good_tag_candidate(keyword):
                suggestions.append({
                    'tag': keyword,
                    'confidence': keyword_info['score'] * 0.6,  # 새 태그는 신뢰도 낮춤
                    'method': 'new_suggestion',
                    'source_keyword': keyword
                })
        
        return suggestions
    
    def _get_popular_tags(self, user_tags: List[str], count: int) -> List[Dict[str, any]]:
        """사용자의 인기 태그 반환"""
        if not user_tags:
            return []
        
        tag_counts = Counter(user_tags)
        popular = []
        
        for tag, freq in tag_counts.most_common(count):
            # 빈도를 신뢰도로 변환 (정규화)
            confidence = min(freq / len(user_tags) * 2, 1.0)
            popular.append({
                'tag': tag,
                'confidence': round(confidence, 3),
                'method': 'popular_tag',
                'frequency': freq
            })
        
        return popular
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """두 텍스트 간의 유사도 계산"""
        try:
            if self.sklearn_available and len(text1) > 3 and len(text2) > 3:
                # TF-IDF 기반 코사인 유사도
                vectorizer = self.TfidfVectorizer(
                    token_pattern=r'\b[가-힣a-zA-Z]{2,}\b',
                    lowercase=True
                )
                
                try:
                    tfidf_matrix = vectorizer.fit_transform([text1, text2])
                    similarity_matrix = self.cosine_similarity(tfidf_matrix)
                    return float(similarity_matrix[0, 1])
                except:
                    pass
            
            # Fallback: SequenceMatcher 사용
            return self.SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
            
        except Exception:
            # 최종 Fallback: 간단한 문자열 매치
            return self._simple_similarity(text1, text2)
    
    def _simple_similarity(self, text1: str, text2: str) -> float:
        """간단한 문자열 유사도 계산"""
        text1, text2 = text1.lower(), text2.lower()
        
        # 완전 일치
        if text1 == text2:
            return 1.0
        
        # 포함 관계
        if text1 in text2 or text2 in text1:
            shorter = min(len(text1), len(text2))
            longer = max(len(text1), len(text2))
            return shorter / longer * 0.8
        
        # 공통 문자 비율
        common_chars = len(set(text1) & set(text2))
        total_chars = len(set(text1) | set(text2))
        
        return common_chars / total_chars if total_chars > 0 else 0.0
    
    def _calculate_category_score(
        self,
        content_text: str,
        category: str,
        keywords: List[Dict[str, any]],
        category_history: List[str]
    ) -> float:
        """카테고리 매치 점수 계산"""
        score = 0.0
        
        # 1. 텍스트 유사도 (40%)
        text_similarity = self._calculate_similarity(content_text, category)
        score += text_similarity * 0.4
        
        # 2. 키워드 매치도 (30%)
        keyword_match_score = 0.0
        for keyword_info in keywords:
            keyword_similarity = self._calculate_similarity(keyword_info['keyword'], category)
            keyword_match_score += keyword_similarity * keyword_info['score']
        
        if keywords:
            keyword_match_score /= len(keywords)
        score += keyword_match_score * 0.3
        
        # 3. 사용 빈도 가중치 (30%)
        category_frequency = category_history.count(category)
        frequency_weight = min(category_frequency / len(category_history), 0.5)
        score += frequency_weight * 0.3
        
        return score
    
    def _get_alternative_categories(
        self, 
        category_scores: Dict[str, float], 
        selected_category: str
    ) -> List[Dict[str, any]]:
        """대안 카테고리 제안"""
        alternatives = []
        
        for category, score in category_scores.items():
            if category != selected_category and score > 0.2:
                alternatives.append({
                    'category': category,
                    'confidence': round(score, 3)
                })
        
        alternatives.sort(key=lambda x: x['confidence'], reverse=True)
        return alternatives[:3]  # 최대 3개 대안
    
    def _suggest_new_category(
        self, 
        extracted_keywords: List[Dict[str, any]], 
        content_title: str
    ) -> Dict[str, any]:
        """새로운 카테고리 제안"""
        # 가장 점수 높은 키워드를 카테고리로 제안
        if extracted_keywords:
            best_keyword = extracted_keywords[0]
            category = self._clean_category_name(best_keyword['keyword'])
            
            return {
                'category': category,
                'confidence': best_keyword['score'] * 0.5,  # 새 카테고리는 신뢰도 낮춤
                'method': 'new_suggestion',
                'source': 'keyword_based'
            }
        
        # 키워드도 없으면 제목 기반
        if content_title:
            category = self._extract_category_from_title(content_title)
            return {
                'category': category,
                'confidence': 0.3,
                'method': 'title_based',
                'source': 'content_title'
            }
        
        # 최종 기본값
        return {
            'category': '기타',
            'confidence': 0.1,
            'method': 'default',
            'source': 'fallback'
        }
    
    def _get_default_category(
        self, 
        extracted_keywords: List[Dict[str, any]], 
        content_title: str
    ) -> Dict[str, any]:
        """기본 카테고리 반환 (히스토리가 없을 때)"""
        return self._suggest_new_category(extracted_keywords, content_title)
    
    def _is_good_tag_candidate(self, keyword: str) -> bool:
        """키워드가 태그로 적합한지 판단"""
        # 길이 체크
        if len(keyword) < 2 or len(keyword) > 20:
            return False
        
        # 특수문자나 숫자만으로 구성된 경우 제외
        if not re.search(r'[가-힣a-zA-Z]', keyword):
            return False
        
        # 너무 일반적인 단어 제외
        common_words = {'내용', '정보', '설명', '소개', '안내', 'content', 'info', 'description'}
        if keyword.lower() in common_words:
            return False
        
        return True
    
    def _clean_category_name(self, name: str) -> str:
        """카테고리 이름 정제"""
        # 불필요한 문자 제거
        cleaned = re.sub(r'[^\w\s가-힣]', '', name)
        
        # 길이 제한 (최대 15자)
        if len(cleaned) > 15:
            cleaned = cleaned[:15]
        
        # 첫 글자 대문자 (영어인 경우)
        if re.match(r'^[a-zA-Z]', cleaned):
            cleaned = cleaned.capitalize()
        
        return cleaned.strip() or '기타'
    
    def _extract_category_from_title(self, title: str) -> str:
        """제목에서 카테고리 추출"""
        # 제목의 첫 번째 의미있는 단어를 카테고리로 사용
        words = re.findall(r'[가-힣a-zA-Z]{3,}', title)
        
        if words:
            return self._clean_category_name(words[0])
        
        return '기타'