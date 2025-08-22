"""
공통 유틸리티 함수들
"""
import re
from typing import Optional


def extract_text_from_html(html_content: str, max_length: Optional[int] = None) -> str:
    """
    HTML에서 텍스트를 추출하여 정제된 문자열로 반환
    
    Args:
        html_content: HTML 문자열
        max_length: 최대 길이 제한 (선택적)
        
    Returns:
        정제된 텍스트 문자열
    """
    if not html_content or not isinstance(html_content, str):
        return ""
    
    try:
        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', html_content)
        
        # HTML 엔티티 디코딩 (기본적인 것들)
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        text = text.replace('&nbsp;', ' ')
        
        # 연속된 공백을 하나로 변경
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 길이 제한 적용
        if max_length and len(text) > max_length:
            # 문장 경계에서 자르기 시도
            truncated = text[:max_length]
            last_sentence_end = max(
                truncated.rfind('.'),
                truncated.rfind('!'),
                truncated.rfind('?'),
                truncated.rfind('。')  # 한국어 마침표
            )
            
            if last_sentence_end > max_length * 0.7:  # 70% 이상이면 문장 단위로 자름
                text = truncated[:last_sentence_end + 1]
            else:
                text = truncated + "..."
        
        return text
        
    except Exception as e:
        # HTML 파싱 실패 시 빈 문자열 반환
        return ""


def truncate_text_for_ai(text: str, max_tokens: int = 3000) -> str:
    """
    AI 모델의 토큰 제한을 고려하여 텍스트를 잘라냄
    
    Args:
        text: 원본 텍스트
        max_tokens: 최대 토큰 수 (대략 글자 수 * 1.3으로 추산)
        
    Returns:
        잘라낸 텍스트
    """
    # 대략적인 토큰 수 계산 (한글/영문 혼재 고려)
    estimated_chars = int(max_tokens * 0.75)  # 보수적으로 추정
    
    if len(text) <= estimated_chars:
        return text
    
    # 문단 단위로 자르기 시도
    truncated = text[:estimated_chars]
    
    # 문단 경계 찾기
    last_paragraph = truncated.rfind('\n\n')
    if last_paragraph > estimated_chars * 0.6:
        return truncated[:last_paragraph] + "\n\n[...]"
    
    # 문장 경계 찾기
    sentence_endings = ['.', '!', '?', '。', '!', '?']
    last_sentence = -1
    for ending in sentence_endings:
        pos = truncated.rfind(ending)
        last_sentence = max(last_sentence, pos)
    
    if last_sentence > estimated_chars * 0.6:
        return truncated[:last_sentence + 1] + " [...]"
    
    # 단어 경계에서 자르기
    last_space = truncated.rfind(' ')
    if last_space > estimated_chars * 0.8:
        return truncated[:last_space] + " [...]"
    
    return truncated + " [...]"