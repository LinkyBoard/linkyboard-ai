"""
중복 콘텐츠 탐지 및 제안 시스템

SimHash + BM25 알고리즘을 사용하여 중복 가능성이 있는 콘텐츠를 탐지하고
사용자에게 중복 후보를 제안합니다.

주요 기능:
1. SimHash: 빠른 유사도 계산을 위한 해시 기반 알고리즘
2. BM25: 키워드 기반 유사도 계산
3. Hybrid Scoring: 두 알고리즘의 결합된 스코어링
4. Duplicate Suggestions: 중복 후보 제안
"""

import re
import hashlib
import math
from typing import List, Dict, Tuple, Set, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.core.logging import get_logger
from app.core.models import Item
from app.observability import trace_request, record_db_operation

logger = get_logger(__name__)


@dataclass
class DuplicateCandidate:
    """중복 후보 데이터 클래스"""
    item_id: int
    title: str
    url: str
    similarity_score: float
    simhash_distance: int
    bm25_score: float
    created_at: datetime
    match_type: str  # "exact", "high", "medium", "low"


@dataclass
class ContentFingerprint:
    """콘텐츠 지문 데이터 클래스"""
    item_id: int
    simhash: int
    keywords: List[str]
    title_normalized: str
    url_normalized: str
    content_length: int


class SimHashCalculator:
    """SimHash 계산기"""
    
    def __init__(self, hash_bits: int = 64):
        self.hash_bits = hash_bits
    
    def calculate_simhash(self, text: str, keywords: List[str] = None) -> int:
        """텍스트의 SimHash 값 계산"""
        # 텍스트를 정규화하고 토큰화
        tokens = self._tokenize(text)
        
        # 키워드가 제공된 경우 가중치 부여
        if keywords:
            keyword_set = set(k.lower() for k in keywords)
            weighted_tokens = []
            for token in tokens:
                weight = 3 if token.lower() in keyword_set else 1
                weighted_tokens.extend([token] * weight)
            tokens = weighted_tokens
        
        # 각 토큰의 해시값 계산
        v = [0] * self.hash_bits
        for token in tokens:
            hash_value = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16)
            for i in range(self.hash_bits):
                bit_mask = 1 << i
                if hash_value & bit_mask:
                    v[i] += 1
                else:
                    v[i] -= 1
        
        # 최종 SimHash 값 생성
        simhash = 0
        for i in range(self.hash_bits):
            if v[i] > 0:
                simhash |= 1 << i
        
        return simhash
    
    def calculate_distance(self, hash1: int, hash2: int) -> int:
        """두 SimHash 값 사이의 해밍 거리 계산"""
        xor = hash1 ^ hash2
        distance = 0
        while xor:
            distance += 1
            xor &= xor - 1  # 가장 오른쪽 1 비트 제거
        return distance
    
    def _tokenize(self, text: str) -> List[str]:
        """텍스트를 토큰으로 분할"""
        # 한글, 영문, 숫자만 추출
        text = re.sub(r'[^\w\s가-힣]', ' ', text)
        # 2글자 이상의 토큰만 사용
        tokens = [token for token in text.split() if len(token) >= 2]
        return tokens


class BM25Calculator:
    """BM25 스코어 계산기"""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.document_frequencies = defaultdict(int)
        self.document_lengths = {}
        self.avg_doc_length = 0
        self.num_documents = 0
    
    def build_index(self, documents: List[Tuple[int, str]]):
        """문서 인덱스 구축"""
        self.document_frequencies.clear()
        self.document_lengths.clear()
        
        total_length = 0
        self.num_documents = len(documents)
        
        for doc_id, content in documents:
            tokens = self._tokenize(content)
            doc_length = len(tokens)
            self.document_lengths[doc_id] = doc_length
            total_length += doc_length
            
            # 각 고유 토큰의 문서 빈도 계산
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.document_frequencies[token] += 1
        
        self.avg_doc_length = total_length / self.num_documents if self.num_documents > 0 else 0
    
    def calculate_score(self, query_tokens: List[str], doc_id: int, doc_content: str) -> float:
        """BM25 스코어 계산"""
        if doc_id not in self.document_lengths:
            return 0.0
        
        doc_tokens = self._tokenize(doc_content)
        doc_length = self.document_lengths[doc_id]
        
        score = 0.0
        token_counts = Counter(doc_tokens)
        
        for token in query_tokens:
            if token not in token_counts:
                continue
            
            tf = token_counts[token]  # 용어 빈도
            df = self.document_frequencies[token]  # 문서 빈도
            idf = math.log((self.num_documents - df + 0.5) / (df + 0.5))
            
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / self.avg_doc_length))
            
            score += idf * (numerator / denominator)
        
        return score
    
    def _tokenize(self, text: str) -> List[str]:
        """텍스트를 토큰으로 분할"""
        text = re.sub(r'[^\w\s가-힣]', ' ', text.lower())
        tokens = [token for token in text.split() if len(token) >= 2]
        return tokens


class DuplicateDetector:
    """중복 콘텐츠 탐지기"""
    
    def __init__(self):
        self.simhash_calc = SimHashCalculator()
        self.bm25_calc = BM25Calculator()
        self.content_fingerprints: List[ContentFingerprint] = []
        
        # 유사도 임계값 설정
        self.thresholds = {
            "exact": {"simhash_distance": 0, "bm25_score": 0.9},
            "high": {"simhash_distance": 3, "bm25_score": 0.7},
            "medium": {"simhash_distance": 6, "bm25_score": 0.5},
            "low": {"simhash_distance": 10, "bm25_score": 0.3},
        }
    
    async def build_index(self, session: AsyncSession, user_id: int):
        """사용자의 기존 콘텐츠로 인덱스 구축"""
        async with trace_request("duplicate_detection_index_build", user_id=user_id) as span:
            try:
                # 사용자의 활성 아이템 조회
                stmt = select(Item).where(
                    Item.user_id == user_id,
                    Item.is_active == True,
                    Item.processing_status == "completed"
                )
                result = await session.execute(stmt)
                items = result.scalars().all()
                
                span.set_attribute("items_count", len(items))
                logger.info(f"Building duplicate detection index for user {user_id} with {len(items)} items")
                
                # 콘텐츠 지문 생성
                self.content_fingerprints = []
                documents = []
                
                for item in items:
                    # 제목과 요약을 결합한 텍스트
                    combined_text = f"{item.title or ''} {item.summary or ''}"
                    
                    # 키워드 추출 (간단한 구현)
                    keywords = self._extract_keywords(combined_text)
                    
                    # SimHash 계산
                    simhash = self.simhash_calc.calculate_simhash(combined_text, keywords)
                    
                    fingerprint = ContentFingerprint(
                        item_id=item.id,
                        simhash=simhash,
                        keywords=keywords,
                        title_normalized=self._normalize_text(item.title or ''),
                        url_normalized=self._normalize_url(item.source_url or ''),
                        content_length=len(combined_text)
                    )
                    
                    self.content_fingerprints.append(fingerprint)
                    documents.append((item.id, combined_text))
                
                # BM25 인덱스 구축
                self.bm25_calc.build_index(documents)
                
                logger.info(f"Duplicate detection index built successfully for user {user_id}")
                record_db_operation("select", "items")
                
            except Exception as e:
                logger.error(f"Failed to build duplicate detection index for user {user_id}: {str(e)}")
                raise
    
    async def find_duplicates(
        self, 
        title: str, 
        summary: str, 
        url: str,
        max_candidates: int = 5
    ) -> List[DuplicateCandidate]:
        """중복 후보 찾기"""
        async with trace_request("duplicate_detection_search", title=title[:50]) as span:
            try:
                combined_text = f"{title or ''} {summary or ''}"
                keywords = self._extract_keywords(combined_text)
                
                # 새 콘텐츠의 SimHash 계산
                new_simhash = self.simhash_calc.calculate_simhash(combined_text, keywords)
                
                candidates = []
                query_tokens = self.bm25_calc._tokenize(combined_text)
                
                for fingerprint in self.content_fingerprints:
                    # SimHash 거리 계산
                    simhash_distance = self.simhash_calc.calculate_distance(
                        new_simhash, fingerprint.simhash
                    )
                    
                    # BM25 스코어 계산
                    bm25_score = self.bm25_calc.calculate_score(
                        query_tokens, 
                        fingerprint.item_id,
                        f"{fingerprint.title_normalized} {' '.join(fingerprint.keywords)}"
                    )
                    
                    # URL 기반 정확한 중복 체크
                    url_normalized = self._normalize_url(url or '')
                    is_exact_url_match = (
                        url_normalized and 
                        fingerprint.url_normalized and 
                        url_normalized == fingerprint.url_normalized
                    )
                    
                    # 하이브리드 스코어 계산
                    hybrid_score = self._calculate_hybrid_score(
                        simhash_distance, bm25_score, is_exact_url_match
                    )
                    
                    # 매치 타입 결정
                    match_type = self._determine_match_type(simhash_distance, bm25_score, is_exact_url_match)
                    
                    if match_type:  # 임계값을 넘는 경우만
                        candidate = DuplicateCandidate(
                            item_id=fingerprint.item_id,
                            title=fingerprint.title_normalized,
                            url=fingerprint.url_normalized,
                            similarity_score=hybrid_score,
                            simhash_distance=simhash_distance,
                            bm25_score=bm25_score,
                            created_at=datetime.now(),
                            match_type=match_type
                        )
                        candidates.append(candidate)
                
                # 유사도 기준으로 정렬하고 상위 결과 반환
                candidates.sort(key=lambda x: x.similarity_score, reverse=True)
                top_candidates = candidates[:max_candidates]
                
                span.set_attribute("candidates_found", len(top_candidates))
                logger.info(f"Found {len(top_candidates)} duplicate candidates")
                
                return top_candidates
                
            except Exception as e:
                logger.error(f"Failed to find duplicates: {str(e)}")
                return []
    
    def _extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """간단한 키워드 추출"""
        # 불용어 제거 및 키워드 추출 (간단한 구현)
        stopwords = {'의', '가', '이', '은', '는', '을', '를', '에', '와', '과', '로', '으로', 
                    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        
        tokens = re.findall(r'\b\w{2,}\b', text.lower())
        keywords = [token for token in tokens if token not in stopwords]
        
        # 빈도 기반 상위 키워드 선택
        keyword_counts = Counter(keywords)
        top_keywords = [word for word, count in keyword_counts.most_common(max_keywords)]
        
        return top_keywords
    
    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화"""
        if not text:
            return ""
        
        # 특수문자 제거, 소문자 변환, 공백 정리
        normalized = re.sub(r'[^\w\s가-힣]', ' ', text)
        normalized = re.sub(r'\s+', ' ', normalized).strip().lower()
        return normalized
    
    def _normalize_url(self, url: str) -> str:
        """URL 정규화"""
        if not url:
            return ""
        
        # 프로토콜, www, 쿼리 파라미터 제거
        url = re.sub(r'^https?://', '', url)
        url = re.sub(r'^www\.', '', url)
        url = re.sub(r'\?.*$', '', url)
        url = url.rstrip('/')
        return url.lower()
    
    def _calculate_hybrid_score(
        self, 
        simhash_distance: int, 
        bm25_score: float, 
        is_exact_url_match: bool
    ) -> float:
        """하이브리드 유사도 스코어 계산"""
        # URL 정확 매치인 경우 높은 스코어
        if is_exact_url_match:
            return 0.95
        
        # SimHash 거리를 0-1 범위로 정규화 (거리가 작을수록 높은 스코어)
        simhash_score = max(0, 1 - (simhash_distance / 20))
        
        # BM25 스코어 정규화 (0-1 범위로)
        bm25_normalized = min(1.0, bm25_score / 10)
        
        # 가중 평균 (SimHash 60%, BM25 40%)
        hybrid_score = 0.6 * simhash_score + 0.4 * bm25_normalized
        
        return hybrid_score
    
    def _determine_match_type(
        self, 
        simhash_distance: int, 
        bm25_score: float, 
        is_exact_url_match: bool
    ) -> Optional[str]:
        """매치 타입 결정"""
        if is_exact_url_match:
            return "exact"
        
        for match_type, thresholds in self.thresholds.items():
            if (simhash_distance <= thresholds["simhash_distance"] or 
                bm25_score >= thresholds["bm25_score"]):
                return match_type
        
        return None


# 전역 중복 탐지기 인스턴스
duplicate_detector = DuplicateDetector()


async def check_for_duplicates(
    session: AsyncSession,
    user_id: int,
    title: str,
    summary: str,
    url: str,
    max_candidates: int = 5
) -> List[DuplicateCandidate]:
    """중복 콘텐츠 확인 (편의 함수)"""
    # 인덱스 구축 (캐싱 로직 추가 가능)
    await duplicate_detector.build_index(session, user_id)
    
    # 중복 후보 찾기
    candidates = await duplicate_detector.find_duplicates(
        title, summary, url, max_candidates
    )
    
    return candidates
