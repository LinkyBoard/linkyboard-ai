import re
from typing import List
from app.ai.embedding.interfaces import ChunkingStrategy, ChunkData
from app.core.logging import get_logger

logger = get_logger("chunking_strategies")


class TokenBasedChunking(ChunkingStrategy):
    """토큰 기반 청킹 전략"""
    
    def get_strategy_name(self) -> str:
        return "token_based"
    
    async def chunk(self, content: str, max_chunk_size: int = 8000) -> List[ChunkData]:
        """
        토큰 제한을 고려하여 콘텐츠를 청크로 분할
        영어 기준 1 토큰 ≈ 4 글자로 계산
        """
        try:
            logger.info(f"Starting token-based chunking (content length: {len(content)}, max_chunk_size: {max_chunk_size})")
            
            if len(content) <= max_chunk_size:
                chunk_data = ChunkData(
                    content=content,
                    chunk_number=0,
                    start_position=0,
                    end_position=len(content),
                    chunk_size=len(content),
                    token_count=self._estimate_token_count(content)
                )
                logger.info(f"Single chunk created - content fits in one chunk ({len(content)} <= {max_chunk_size})")
                return [chunk_data]
            
            logger.info(f"Content too large ({len(content)} > {max_chunk_size}), starting multi-chunk processing")
            
            chunks = []
            start = 0
            chunk_number = 0
            
            while start < len(content):
                end = min(start + max_chunk_size, len(content))
                logger.debug(f"Processing chunk {chunk_number}: start={start}, initial_end={end}")
                
                # 문장 경계에서 자르기 위해 마지막 마침표나 줄바꿈 찾기
                if end < len(content):
                    cut_point = self._find_best_cut_point(content, start, end)
                    if cut_point > start:
                        logger.debug(f"Found better cut point: {end} -> {cut_point}")
                        end = cut_point
                
                chunk_content = content[start:end].strip()
                
                if chunk_content:  # 빈 청크 제외
                    chunk_data = ChunkData(
                        content=chunk_content,
                        chunk_number=chunk_number,
                        start_position=start,
                        end_position=end,
                        chunk_size=len(chunk_content),
                        token_count=self._estimate_token_count(chunk_content)
                    )
                    chunks.append(chunk_data)
                    logger.info(f"Created chunk {chunk_number}: {len(chunk_content)} chars (start={start}, end={end})")
                    chunk_number += 1
                
                start = end
            
            logger.info(f"Token-based chunking completed: {len(chunks)} chunks created")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to chunk content: {str(e)}")
            # 실패 시 전체를 하나의 청크로 반환
            return [ChunkData(
                content=content[:max_chunk_size],
                chunk_number=0,
                start_position=0,
                end_position=min(max_chunk_size, len(content)),
                chunk_size=min(max_chunk_size, len(content)),
                token_count=self._estimate_token_count(content[:max_chunk_size])
            )]
    
    def _find_best_cut_point(self, content: str, start: int, end: int) -> int:
        """최적의 자르기 지점 찾기"""
        search_range = min(1000, (end - start) // 4)  # 뒤에서 1000자 또는 1/4 지점까지 검색
        search_start = max(start, end - search_range)
        
        # 우선순위: 마침표 > 줄바꿈 > 공백
        for pattern in [r'[.!?]\s+', r'\n\s*', r'\s+']:
            matches = list(re.finditer(pattern, content[search_start:end]))
            if matches:
                # 가장 뒤에 있는 매치 선택
                last_match = matches[-1]
                cut_point = search_start + last_match.end()
                return cut_point
        
        return end
    
    def _estimate_token_count(self, text: str) -> int:
        """토큰 수 추정 (영어 기준 4글자 ≈ 1토큰)"""
        # 한국어와 영어가 섞인 경우를 고려하여 보수적으로 계산
        return len(text) // 3


class SentenceBasedChunking(ChunkingStrategy):
    """문장 기반 청킹 전략"""
    
    def get_strategy_name(self) -> str:
        return "sentence_based"
    
    async def chunk(self, content: str, max_chunk_size: int = 8000) -> List[ChunkData]:
        """문장 단위로 청크 분할"""
        try:
            logger.info(f"Starting sentence-based chunking (content length: {len(content)})")
            
            # 문장 분할
            sentences = self._split_sentences(content)
            
            if not sentences:
                return []
            
            chunks = []
            current_chunk = ""
            chunk_number = 0
            start_position = 0
            
            for sentence in sentences:
                # 현재 청크에 문장을 추가했을 때 크기 확인
                test_chunk = current_chunk + sentence
                
                if len(test_chunk) <= max_chunk_size:
                    current_chunk = test_chunk
                else:
                    # 현재 청크 저장
                    if current_chunk.strip():
                        chunk_data = ChunkData(
                            content=current_chunk.strip(),
                            chunk_number=chunk_number,
                            start_position=start_position,
                            end_position=start_position + len(current_chunk),
                            chunk_size=len(current_chunk.strip()),
                            token_count=len(current_chunk.strip()) // 3
                        )
                        chunks.append(chunk_data)
                        chunk_number += 1
                        start_position += len(current_chunk)
                    
                    # 새 청크 시작
                    current_chunk = sentence
            
            # 마지막 청크 저장
            if current_chunk.strip():
                chunk_data = ChunkData(
                    content=current_chunk.strip(),
                    chunk_number=chunk_number,
                    start_position=start_position,
                    end_position=start_position + len(current_chunk),
                    chunk_size=len(current_chunk.strip()),
                    token_count=len(current_chunk.strip()) // 3
                )
                chunks.append(chunk_data)
            
            logger.info(f"Sentence-based chunking completed: {len(chunks)} chunks created")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to chunk content by sentences: {str(e)}")
            # 실패 시 토큰 기반 청킹으로 폴백
            token_chunking = TokenBasedChunking()
            return await token_chunking.chunk(content, max_chunk_size)
    
    def _split_sentences(self, content: str) -> List[str]:
        """문장 분할"""
        # 한국어와 영어 문장 끝 패턴
        sentence_endings = r'[.!?]\s+|[。！？]\s*'
        sentences = re.split(sentence_endings, content)
        
        # 빈 문장 제거 및 정리
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
