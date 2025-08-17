"""
토큰 카운팅 유틸리티

텍스트의 토큰 수를 추정하는 기능을 제공합니다.
실제 구현에서는 tiktoken 라이브러리 사용을 권장하지만,
현재는 간단한 추정 공식을 사용합니다.
"""

import logging

logger = logging.getLogger(__name__)


def count_tokens(text: str, model: str = "text-embedding-3-small") -> int:
    """
    텍스트의 토큰 수를 추정
    
    실제 구현에서는 tiktoken 라이브러리를 사용하는 것이 좋지만,
    일단 간단한 추정 공식을 사용 (1토큰 ≈ 4글자)
    
    Args:
        text: 토큰을 세을 텍스트
        model: 모델명 (추후 모델별 토큰 계산용)
        
    Returns:
        추정 토큰 수
    """
    if not text:
        return 0
    
    # 간단한 추정: 영어는 4글자당 1토큰, 한국어는 2글자당 1토큰 정도
    # 실제로는 tiktoken 사용 권장
    char_count = len(text)
    
    # 영어/숫자 비율과 한국어/중국어/일본어 비율을 고려한 추정
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    non_ascii_chars = char_count - ascii_chars
    
    estimated_tokens = (ascii_chars // 4) + (non_ascii_chars // 2)
    
    # 최소 1토큰은 보장
    return max(1, estimated_tokens)


def count_tokens_batch(texts: list[str], model: str = "text-embedding-3-small") -> list[int]:
    """
    여러 텍스트의 토큰 수를 일괄 계산
    
    Args:
        texts: 토큰을 세을 텍스트 리스트
        model: 모델명
        
    Returns:
        각 텍스트의 추정 토큰 수 리스트
    """
    return [count_tokens(text, model) for text in texts]


def estimate_embedding_tokens(chunks: list[str], model: str = "text-embedding-3-small") -> int:
    """
    임베딩용 청크들의 총 토큰 수 추정
    
    Args:
        chunks: 임베딩할 텍스트 청크 리스트
        model: 임베딩 모델명
        
    Returns:
        총 토큰 수
    """
    total_tokens = sum(count_tokens(chunk, model) for chunk in chunks)
    
    logger.debug(f"Estimated embedding tokens: {total_tokens} for {len(chunks)} chunks")
    
    return total_tokens
