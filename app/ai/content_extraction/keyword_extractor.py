"""
키워드 추출 서비스
NLP 라이브러리를 사용하여 텍스트에서 핵심 키워드를 추출합니다.
"""

import re
from typing import List, Dict, Set, Optional, Tuple
from collections import Counter
from app.core.logging import get_logger

logger = get_logger(__name__)


class KeywordExtractor:
    """텍스트에서 키워드를 추출하는 서비스"""
    
    def __init__(self):
        """키워드 추출기 초기화"""
        self.korean_stopwords = self._load_korean_stopwords()
        self.english_stopwords = self._load_english_stopwords()
        
        # 선택적 라이브러리 로드
        self.spacy_available = self._init_spacy()
        self.sklearn_available = self._init_sklearn()
        self.konlpy_available = self._init_konlpy()
        
        logger.info(f"KeywordExtractor initialized - spaCy: {self.spacy_available}, sklearn: {self.sklearn_available}, konlpy: {self.konlpy_available}")
    
    def _init_spacy(self) -> bool:
        """spaCy 라이브러리 초기화"""
        try:
            import spacy
            # 영어 모델 로드 시도
            try:
                self.nlp_en = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("English spaCy model not found, using basic tokenizer")
                self.nlp_en = None
            
            # 한국어 모델 로드 시도  
            try:
                self.nlp_ko = spacy.load("ko_core_news_sm")
            except OSError:
                logger.warning("Korean spaCy model not found")
                self.nlp_ko = None
            
            self.spacy = spacy
            return True
            
        except ImportError:
            logger.warning("spaCy not available")
            return False
    
    def _init_sklearn(self) -> bool:
        """scikit-learn 라이브러리 초기화"""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            
            self.TfidfVectorizer = TfidfVectorizer
            self.cosine_similarity = cosine_similarity
            return True
            
        except ImportError:
            logger.warning("scikit-learn not available")
            return False
    
    def _init_konlpy(self) -> bool:
        """KoNLPy 라이브러리 초기화"""
        try:
            from konlpy.tag import Okt, Hannanum
            
            # Okt (Open Korean Text) 우선 사용
            try:
                self.okt = Okt()
                self.korean_analyzer = 'okt'
            except Exception:
                try:
                    self.hannanum = Hannanum()
                    self.korean_analyzer = 'hannanum'
                except Exception:
                    logger.warning("No KoNLPy analyzer available")
                    return False
            
            return True
            
        except ImportError:
            logger.warning("KoNLPy not available")
            return False
    
    def extract_keywords(
        self,
        text: str,
        max_keywords: int = 10,
        min_length: int = 2,
        include_phrases: bool = True
    ) -> List[Dict[str, any]]:
        """
        텍스트에서 키워드를 추출합니다.
        
        Args:
            text: 추출할 텍스트
            max_keywords: 최대 키워드 수
            min_length: 최소 키워드 길이
            include_phrases: 구문 포함 여부
            
        Returns:
            키워드 리스트 (점수 포함)
        """
        if not text or len(text.strip()) < min_length:
            return []
        
        try:
            # 언어 감지
            is_korean = self._detect_korean(text)
            
            # 방법별 키워드 추출
            keywords_sets = []
            
            # 1. NLP 라이브러리 사용
            if is_korean and self.konlpy_available:
                nlp_keywords = self._extract_with_konlpy(text, max_keywords)
                keywords_sets.append(('konlpy', nlp_keywords))
            elif not is_korean and self.spacy_available and self.nlp_en:
                nlp_keywords = self._extract_with_spacy(text, max_keywords)
                keywords_sets.append(('spacy', nlp_keywords))
            
            # 2. TF-IDF 사용
            if self.sklearn_available:
                tfidf_keywords = self._extract_with_tfidf(text, max_keywords)
                keywords_sets.append(('tfidf', tfidf_keywords))
            
            # 3. 빈도 기반 추출 (항상 사용 가능)
            freq_keywords = self._extract_with_frequency(text, max_keywords, min_length)
            keywords_sets.append(('frequency', freq_keywords))
            
            # 4. 구문 추출 (선택사항)
            if include_phrases:
                phrases = self._extract_phrases(text, max_keywords)
                keywords_sets.append(('phrases', phrases))
            
            # 결과 통합 및 가중치 적용
            final_keywords = self._combine_keywords(keywords_sets, max_keywords)
            
            # 정제 및 필터링
            filtered_keywords = self._filter_keywords(final_keywords, min_length)
            
            return filtered_keywords[:max_keywords]
            
        except Exception as e:
            logger.error(f"Keyword extraction failed: {e}")
            # Fallback to basic frequency method
            return self._extract_with_frequency(text, max_keywords, min_length)
    
    def _detect_korean(self, text: str) -> bool:
        """텍스트에서 한국어 비율 확인"""
        korean_chars = len(re.findall(r'[가-힣]', text))
        total_chars = len(re.sub(r'\s+', '', text))
        
        return korean_chars / max(total_chars, 1) > 0.3 if total_chars > 0 else False
    
    def _extract_with_konlpy(self, text: str, max_keywords: int) -> List[Tuple[str, float]]:
        """KoNLPy를 사용한 한국어 키워드 추출"""
        try:
            if self.korean_analyzer == 'okt':
                # 명사만 추출
                nouns = self.okt.nouns(text)
            else:
                # Hannanum 사용
                pos_tags = self.hannanum.pos(text)
                nouns = [word for word, pos in pos_tags if pos.startswith('N')]
            
            # 불용어 제거 및 길이 필터링
            filtered_nouns = [
                noun for noun in nouns 
                if len(noun) > 1 and noun not in self.korean_stopwords
            ]
            
            # 빈도 계산
            noun_counts = Counter(filtered_nouns)
            
            # 점수 정규화
            max_count = max(noun_counts.values()) if noun_counts else 1
            scored_keywords = [
                (noun, count / max_count)
                for noun, count in noun_counts.most_common(max_keywords)
            ]
            
            return scored_keywords
            
        except Exception as e:
            logger.warning(f"KoNLPy extraction failed: {e}")
            return []
    
    def _extract_with_spacy(self, text: str, max_keywords: int) -> List[Tuple[str, float]]:
        """spaCy를 사용한 영어 키워드 추출"""
        try:
            doc = self.nlp_en(text)
            
            # 명사, 고유명사, 형용사 추출
            keywords = []
            for token in doc:
                if (token.pos_ in ['NOUN', 'PROPN', 'ADJ'] and
                    not token.is_stop and
                    not token.is_punct and
                    len(token.text) > 1 and
                    token.text.lower() not in self.english_stopwords):
                    keywords.append(token.lemma_.lower())
            
            # 빈도 계산
            keyword_counts = Counter(keywords)
            
            # 점수 정규화
            max_count = max(keyword_counts.values()) if keyword_counts else 1
            scored_keywords = [
                (keyword, count / max_count)
                for keyword, count in keyword_counts.most_common(max_keywords)
            ]
            
            return scored_keywords
            
        except Exception as e:
            logger.warning(f"spaCy extraction failed: {e}")
            return []
    
    def _extract_with_tfidf(self, text: str, max_keywords: int) -> List[Tuple[str, float]]:
        """TF-IDF를 사용한 키워드 추출"""
        try:
            # 문장 단위로 분할
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if len(sentences) < 2:
                return []
            
            # TF-IDF 벡터화
            vectorizer = self.TfidfVectorizer(
                max_features=max_keywords * 2,
                stop_words=None,  # 사용자 정의 불용어 사용
                token_pattern=r'\b[가-힣a-zA-Z]{2,}\b',  # 한글, 영어 2글자 이상
                lowercase=True
            )
            
            tfidf_matrix = vectorizer.fit_transform(sentences)
            feature_names = vectorizer.get_feature_names_out()
            
            # 평균 TF-IDF 점수 계산
            mean_scores = tfidf_matrix.mean(axis=0).A1
            
            # 불용어 필터링
            scored_keywords = []
            for idx, score in enumerate(mean_scores):
                word = feature_names[idx]
                if (score > 0 and 
                    word not in self.korean_stopwords and 
                    word not in self.english_stopwords):
                    scored_keywords.append((word, score))
            
            # 점수 순 정렬
            scored_keywords.sort(key=lambda x: x[1], reverse=True)
            
            return scored_keywords[:max_keywords]
            
        except Exception as e:
            logger.warning(f"TF-IDF extraction failed: {e}")
            return []
    
    def _extract_with_frequency(self, text: str, max_keywords: int, min_length: int) -> List[Tuple[str, float]]:
        """빈도 기반 키워드 추출 (fallback 방법)"""
        try:
            # 단어 추출 (한글, 영어, 숫자 조합)
            words = re.findall(r'[가-힣a-zA-Z0-9]{' + str(min_length) + ',}', text.lower())
            
            # 불용어 제거
            filtered_words = [
                word for word in words 
                if word not in self.korean_stopwords and 
                   word not in self.english_stopwords
            ]
            
            # 빈도 계산
            word_counts = Counter(filtered_words)
            
            # 점수 정규화
            max_count = max(word_counts.values()) if word_counts else 1
            scored_keywords = [
                (word, count / max_count)
                for word, count in word_counts.most_common(max_keywords)
            ]
            
            return scored_keywords
            
        except Exception as e:
            logger.error(f"Frequency extraction failed: {e}")
            return []
    
    def _extract_phrases(self, text: str, max_phrases: int) -> List[Tuple[str, float]]:
        """구문(n-gram) 추출"""
        try:
            # 2-3 단어 구문 찾기
            phrases = []
            
            # 2-gram
            bigrams = re.findall(r'[가-힣a-zA-Z]{2,}\s+[가-힣a-zA-Z]{2,}', text)
            phrases.extend(bigrams)
            
            # 3-gram
            trigrams = re.findall(r'[가-힣a-zA-Z]{2,}\s+[가-힣a-zA-Z]{2,}\s+[가-힣a-zA-Z]{2,}', text)
            phrases.extend(trigrams)
            
            # 빈도 계산
            phrase_counts = Counter(phrases)
            
            # 점수 정규화
            max_count = max(phrase_counts.values()) if phrase_counts else 1
            scored_phrases = [
                (phrase, count / max_count)
                for phrase, count in phrase_counts.most_common(max_phrases)
            ]
            
            return scored_phrases
            
        except Exception as e:
            logger.warning(f"Phrase extraction failed: {e}")
            return []
    
    def _combine_keywords(self, keywords_sets: List[Tuple[str, List[Tuple[str, float]]]], max_keywords: int) -> List[Tuple[str, float]]:
        """여러 방법으로 추출된 키워드를 통합"""
        # 방법별 가중치
        weights = {
            'konlpy': 0.4,
            'spacy': 0.4,
            'tfidf': 0.3,
            'frequency': 0.2,
            'phrases': 0.1
        }
        
        # 키워드별 점수 합계
        combined_scores = {}
        
        for method, keywords in keywords_sets:
            weight = weights.get(method, 0.1)
            for keyword, score in keywords:
                if keyword not in combined_scores:
                    combined_scores[keyword] = 0
                combined_scores[keyword] += score * weight
        
        # 점수 순 정렬
        sorted_keywords = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        
        return sorted_keywords[:max_keywords]
    
    def _filter_keywords(self, keywords: List[Tuple[str, float]], min_length: int) -> List[Dict[str, any]]:
        """키워드 필터링 및 포맷팅"""
        filtered = []
        
        for keyword, score in keywords:
            # 길이 체크
            if len(keyword) < min_length:
                continue
            
            # 특수 문자만으로 구성된 경우 제외
            if not re.search(r'[가-힣a-zA-Z]', keyword):
                continue
            
            # 포맷팅
            filtered.append({
                'keyword': keyword.strip(),
                'score': round(score, 3),
                'length': len(keyword)
            })
        
        return filtered
    
    def _load_korean_stopwords(self) -> Set[str]:
        """한국어 불용어 로드"""
        # 기본 한국어 불용어
        stopwords = {
            '이', '그', '저', '것', '들', '에', '의', '를', '을', '로', '으로', '와', '과', '도', '만',
            '부터', '까지', '에서', '에게', '한테', '께', '에다', '한', '두', '세', '네', '다섯',
            '여섯', '일곱', '여덟', '아홉', '열', '하나', '나', '너', '우리', '저희', '당신',
            '자신', '자기', '아주', '매우', '너무', '정말', '진짜', '좀', '조금', '많이',
            '어떤', '어떻게', '왜', '언제', '어디', '누구', '무엇', '그런', '이런', '저런',
            '그렇게', '이렇게', '저렇게', '그래서', '그러나', '하지만', '그리고', '또한',
            '따라서', '즉', '예를', '대해', '위해', '통해', '대한', '관한', '같은', '다른',
            '새로운', '오래된', '좋은', '나쁜', '큰', '작은', '높은', '낮은', '빠른', '느린'
        }
        return stopwords
    
    def _load_english_stopwords(self) -> Set[str]:
        """영어 불용어 로드"""
        # 기본 영어 불용어
        stopwords = {
            'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours',
            'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her', 'hers',
            'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves',
            'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are',
            'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does',
            'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until',
            'while', 'of', 'at', 'by', 'for', 'with', 'through', 'during', 'before', 'after',
            'above', 'below', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again',
            'further', 'then', 'once', 'very', 'can', 'will', 'just', 'should', 'now'
        }
        return stopwords