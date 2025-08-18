"""
YouTube 콘텐츠 추출기
제목과 트랜스크립트에서 핵심 정보 추출
"""

from typing import Dict, Any, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


class YouTubeContentExtractor:
    """
    YouTube 콘텐츠 (제목 + 트랜스크립트)에서 핵심 정보를 추출하는 클래스
    """
    
    def __init__(self):
        """YouTube 콘텐츠 추출기 초기화"""
        self.available = True
        logger.info("YouTubeContentExtractor initialized")
    
    def extract_content(
        self,
        title: str = "",
        transcript: str = "",
        video_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        YouTube 제목과 트랜스크립트에서 핵심 콘텐츠 추출
        
        Args:
            title: YouTube 비디오 제목
            transcript: YouTube 트랜스크립트
            video_id: YouTube 비디오 ID
            
        Returns:
            추출된 콘텐츠 정보
        """
        try:
            # 제목과 트랜스크립트 정제
            cleaned_title = self._clean_title(title)
            cleaned_transcript = self._clean_transcript(transcript)
            
            # 전체 텍스트 조합 (제목 우선순위)
            combined_text = f"{cleaned_title}\n\n{cleaned_transcript}".strip()
            
            if not combined_text:
                logger.warning("No content available for extraction")
                return self._get_empty_result()
            
            # 텍스트 통계 계산
            word_count = len(combined_text.split())
            char_count = len(combined_text)
            
            # 콘텐츠 품질 평가
            quality_score = self._calculate_content_quality(cleaned_title, cleaned_transcript)
            
            result = {
                'title': cleaned_title or 'Untitled YouTube Video',
                'content': combined_text,
                'transcript': cleaned_transcript,
                'word_count': word_count,
                'char_count': char_count,
                'quality_score': quality_score,
                'extraction_method': 'youtube_native',
                'metadata': {
                    'video_id': video_id,
                    'has_title': bool(cleaned_title),
                    'has_transcript': bool(cleaned_transcript),
                    'transcript_length': len(cleaned_transcript),
                    'estimated_duration': self._estimate_video_duration(cleaned_transcript)
                }
            }
            
            logger.info(f"YouTube content extracted - chars: {char_count}, "
                       f"words: {word_count}, quality: {quality_score:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"YouTube content extraction failed: {e}")
            return self._get_empty_result()
    
    def _clean_title(self, title: str) -> str:
        """YouTube 제목 정제"""
        if not title:
            return ""
        
        # 불필요한 문자 제거 및 정규화
        import re
        
        # 특수문자 및 이모지 정리 (한글, 영문, 숫자, 기본 문장부호만 유지)
        cleaned = re.sub(r'[^\w\s가-힣.,!?()[\]{}:;"\'-]', ' ', title)
        
        # 연속된 공백 정리
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # 길이 제한 (너무 긴 제목 방지)
        if len(cleaned) > 200:
            cleaned = cleaned[:200] + "..."
        
        return cleaned
    
    def _clean_transcript(self, transcript: str) -> str:
        """YouTube 트랜스크립트 정제"""
        if not transcript:
            return ""
        
        import re
        
        # 타임스탬프 제거 ([00:12] 같은 패턴)
        cleaned = re.sub(r'\[\d{1,2}:\d{2}\]', '', transcript)
        
        # 반복되는 구어체 표현 정리
        cleaned = re.sub(r'\b(어|음|그|저|뭐|이제)\b', '', cleaned)
        
        # 연속된 공백과 줄바꿈 정리
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # 길이 제한 (너무 긴 트랜스크립트 방지)
        if len(cleaned) > 10000:
            # 앞의 80%만 사용 (주요 내용이 앞에 있을 가능성 높음)
            cleaned = cleaned[:8000] + "..."
        
        return cleaned
    
    def _calculate_content_quality(self, title: str, transcript: str) -> float:
        """콘텐츠 품질 점수 계산 (0.0 - 1.0)"""
        score = 0.0
        
        # 제목 품질 (30%)
        if title:
            title_score = min(len(title) / 50, 1.0)  # 50자 기준으로 정규화
            score += title_score * 0.3
        
        # 트랜스크립트 품질 (70%)
        if transcript:
            # 길이 점수
            length_score = min(len(transcript) / 1000, 1.0)  # 1000자 기준
            score += length_score * 0.4
            
            # 다양성 점수 (유니크한 단어 비율)
            words = transcript.split()
            if words:
                unique_ratio = len(set(words)) / len(words)
                score += unique_ratio * 0.3
        
        return min(score, 1.0)
    
    def _estimate_video_duration(self, transcript: str) -> str:
        """트랜스크립트 길이로 비디오 길이 추정"""
        if not transcript:
            return "Unknown"
        
        # 대략적인 추정 (분당 150-200 단어)
        word_count = len(transcript.split())
        estimated_minutes = word_count / 175  # 평균값 사용
        
        if estimated_minutes < 1:
            return "< 1분"
        elif estimated_minutes < 60:
            return f"약 {int(estimated_minutes)}분"
        else:
            hours = int(estimated_minutes // 60)
            minutes = int(estimated_minutes % 60)
            return f"약 {hours}시간 {minutes}분"
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """빈 결과 반환"""
        return {
            'title': 'Untitled YouTube Video',
            'content': '',
            'transcript': '',
            'word_count': 0,
            'char_count': 0,
            'quality_score': 0.0,
            'extraction_method': 'youtube_empty',
            'metadata': {
                'video_id': None,
                'has_title': False,
                'has_transcript': False,
                'transcript_length': 0,
                'estimated_duration': "Unknown"
            }
        }