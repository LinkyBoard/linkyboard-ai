"""
Whisper Speech-to-Text Processor

OpenAI Whisper를 사용하여 오디오 파일을 텍스트로 변환하는 모듈입니다.
다국어 지원 및 자동 언어 감지 기능을 제공합니다.
"""

import os
import ssl
import time
from typing import Dict, List, Optional, Union
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


class WhisperSTTError(Exception):
    """Whisper STT 관련 오류"""
    pass


class WhisperSTTResult:
    """STT 결과 데이터 클래스"""
    
    def __init__(
        self,
        text: str,
        language: str,
        segments: List[Dict],
        processing_time: float,
        model_used: str,
        confidence_scores: Optional[List[float]] = None
    ):
        self.text = text
        self.language = language
        self.segments = segments
        self.processing_time = processing_time
        self.model_used = model_used
        self.confidence_scores = confidence_scores or []
    
    def to_dict(self) -> Dict:
        """결과를 딕셔너리로 변환"""
        return {
            'text': self.text,
            'language': self.language,
            'segments_count': len(self.segments),
            'processing_time': self.processing_time,
            'model_used': self.model_used,
            'text_length': len(self.text),
            'average_confidence': sum(self.confidence_scores) / len(self.confidence_scores) if self.confidence_scores else 0.0
        }


class WhisperSTTProcessor:
    """Whisper Speech-to-Text 처리기"""
    
    # 사용 가능한 Whisper 모델들 (속도와 정확도 트레이드오프)
    AVAILABLE_MODELS = {
        'tiny': 'whisper-tiny (39MB, 32x faster, lower accuracy)',
        'base': 'whisper-base (74MB, 16x faster, good accuracy)',  # 기본 추천
        'small': 'whisper-small (244MB, 6x faster, better accuracy)',
        'medium': 'whisper-medium (769MB, 2x faster, high accuracy)',
        'large': 'whisper-large (1550MB, 1x speed, highest accuracy)',
        'large-v3': 'whisper-large-v3 (1550MB, latest, highest accuracy)',
    }
    
    def __init__(self, model_name: str = "base", device: str = "auto"):
        """
        Whisper STT 프로세서 초기화
        
        Args:
            model_name: 사용할 Whisper 모델 ('tiny', 'base', 'small', 'medium', 'large', 'large-v3')
            device: 처리 디바이스 ('auto', 'cpu', 'cuda')
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        self._available = False
        
        # Whisper 가용성 확인 및 초기화
        try:
            import whisper
            self._whisper = whisper
            
            # SSL 인증 문제 우회 (Whisper 모델 다운로드용)
            self._setup_ssl_context()
            
            self._available = True
            logger.info(f"WhisperSTTProcessor 초기화 완료 (모델: {model_name})")
        except ImportError:
            logger.error("openai-whisper가 설치되지 않았습니다")
            raise WhisperSTTError("openai-whisper 패키지가 필요합니다. pip install openai-whisper")
    
    def _setup_ssl_context(self):
        """SSL 인증 컨텍스트 설정 (모델 다운로드용)"""
        try:
            ssl._create_default_https_context = ssl._create_unverified_context
            logger.debug("SSL 인증 우회 설정 완료")
        except Exception as e:
            logger.warning(f"SSL 설정 실패 (계속 진행): {e}")
    
    def is_available(self) -> bool:
        """STT 프로세서 사용 가능 여부 확인"""
        return self._available
    
    def load_model(self) -> bool:
        """
        Whisper 모델 로드
        
        Returns:
            bool: 로드 성공 여부
        """
        if not self.is_available():
            return False
        
        if self.model is not None:
            return True  # 이미 로드됨
        
        try:
            logger.info(f"Whisper 모델 로드 시작: {self.model_name}")
            start_time = time.time()
            
            # 디바이스 설정
            device = None if self.device == "auto" else self.device
            
            # 모델 로드
            self.model = self._whisper.load_model(
                self.model_name, 
                device=device
            )
            
            load_time = time.time() - start_time
            logger.info(f"Whisper 모델 로드 완료: {self.model_name} ({load_time:.2f}초)")
            return True
            
        except Exception as e:
            error_msg = f"Whisper 모델 로드 실패: {str(e)}"
            logger.error(error_msg)
            raise WhisperSTTError(error_msg)
    
    async def transcribe_audio(
        self,
        audio_file_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
        temperature: float = 0.0,
        best_of: int = 5,
        beam_size: Optional[int] = None,
        word_timestamps: bool = False,
        **kwargs
    ) -> WhisperSTTResult:
        """
        오디오 파일을 텍스트로 변환
        
        Args:
            audio_file_path: 변환할 오디오 파일 경로
            language: 강제 언어 설정 (None이면 자동 감지)
            task: 'transcribe' 또는 'translate' (영어로 번역)
            temperature: 샘플링 온도 (0.0-1.0)
            best_of: 후보 중 최선 선택 개수
            beam_size: 빔 서치 크기 (None이면 그리디 검색)
            word_timestamps: 단어별 타임스탬프 포함 여부
            
        Returns:
            WhisperSTTResult: STT 결과 객체
            
        Raises:
            WhisperSTTError: STT 처리 실패 시
        """
        if not self.is_available():
            raise WhisperSTTError("Whisper STT 프로세서를 사용할 수 없습니다")
        
        if not os.path.exists(audio_file_path):
            raise WhisperSTTError(f"오디오 파일을 찾을 수 없습니다: {audio_file_path}")
        
        # 모델 로드 (아직 로드되지 않은 경우)
        if not self.load_model():
            raise WhisperSTTError("Whisper 모델을 로드할 수 없습니다")
        
        try:
            logger.info(f"Whisper STT 처리 시작: {audio_file_path}")
            start_time = time.time()
            
            # Whisper 옵션 설정
            options = {
                'language': language,
                'task': task,
                'temperature': temperature,
                'best_of': best_of,
                'word_timestamps': word_timestamps,
                'verbose': False,  # 진행률 출력 비활성화
            }
            
            if beam_size is not None:
                options['beam_size'] = beam_size
            
            # 추가 옵션 병합
            options.update(kwargs)
            
            # STT 실행
            result = self.model.transcribe(audio_file_path, **options)
            
            processing_time = time.time() - start_time
            
            # 결과 추출
            text = result.get('text', '').strip()
            detected_language = result.get('language', 'unknown')
            segments = result.get('segments', [])
            
            # 신뢰도 점수 추출 (segment별로 있을 수 있음)
            confidence_scores = []
            for segment in segments:
                if 'avg_logprob' in segment:
                    # avg_logprob을 확률로 변환 (대략적)
                    confidence = min(1.0, max(0.0, (segment['avg_logprob'] + 1.0)))
                    confidence_scores.append(confidence)
            
            logger.info(
                f"Whisper STT 처리 완료: {len(text)}자, {len(segments)}세그먼트, "
                f"언어: {detected_language}, 처리시간: {processing_time:.2f}초"
            )
            
            return WhisperSTTResult(
                text=text,
                language=detected_language,
                segments=segments,
                processing_time=processing_time,
                model_used=self.model_name,
                confidence_scores=confidence_scores
            )
            
        except Exception as e:
            error_msg = f"Whisper STT 처리 실패: {str(e)}"
            logger.error(error_msg)
            raise WhisperSTTError(error_msg)
    
    async def transcribe_with_language_detection(
        self,
        audio_file_path: str,
        supported_languages: Optional[List[str]] = None,
        confidence_threshold: float = 0.8,
        **kwargs
    ) -> WhisperSTTResult:
        """
        언어 감지 후 최적 언어로 STT 수행
        
        Args:
            audio_file_path: 변환할 오디오 파일 경로
            supported_languages: 지원 언어 목록 (None이면 모든 언어)
            confidence_threshold: 언어 감지 신뢰도 임계값
            
        Returns:
            WhisperSTTResult: STT 결과 객체
        """
        try:
            # 1단계: 언어 자동 감지로 STT 수행
            logger.info("언어 자동 감지로 STT 시작")
            result = await self.transcribe_audio(
                audio_file_path,
                language=None,  # 자동 감지
                **kwargs
            )
            
            detected_lang = result.language
            logger.info(f"감지된 언어: {detected_lang}")
            
            # 2단계: 지원 언어 목록이 있으면 확인
            if supported_languages and detected_lang not in supported_languages:
                logger.warning(
                    f"감지된 언어 '{detected_lang}'가 지원 목록에 없음. "
                    f"지원 언어: {supported_languages}"
                )
                # 영어로 번역 시도
                logger.info("영어로 번역하여 STT 재시도")
                result = await self.transcribe_audio(
                    audio_file_path,
                    task="translate",  # 영어로 번역
                    **kwargs
                )
            
            return result
            
        except Exception as e:
            error_msg = f"언어 감지 STT 실패: {str(e)}"
            logger.error(error_msg)
            raise WhisperSTTError(error_msg)
    
    def get_supported_languages(self) -> List[str]:
        """
        Whisper가 지원하는 언어 목록 반환
        
        Returns:
            List[str]: 언어 코드 목록
        """
        if not self.is_available():
            return []
        
        try:
            # Whisper의 언어 목록은 whisper.tokenizer.LANGUAGES에 있음
            from whisper.tokenizer import LANGUAGES
            return list(LANGUAGES.keys())
        except Exception as e:
            logger.warning(f"언어 목록 조회 실패: {e}")
            return []
    
    def estimate_processing_time(self, audio_duration_seconds: float) -> float:
        """
        오디오 길이 기반 처리 시간 추정
        
        Args:
            audio_duration_seconds: 오디오 길이 (초)
            
        Returns:
            float: 예상 처리 시간 (초)
        """
        # 모델별 처리 속도 비율 (실제 테스트 기반 근사값)
        speed_ratios = {
            'tiny': 0.05,    # 매우 빠름
            'base': 0.13,    # 빠름 (테스트에서 확인된 값)
            'small': 0.20,   # 보통
            'medium': 0.35,  # 느림
            'large': 0.50,   # 매우 느림
            'large-v3': 0.55,  # 가장 느림
        }
        
        ratio = speed_ratios.get(self.model_name, 0.20)  # 기본값
        estimated_time = audio_duration_seconds * ratio
        
        # 최소 처리 시간 보장
        return max(estimated_time, 2.0)
    
    def get_model_info(self) -> Dict:
        """모델 정보 반환"""
        return {
            'model_name': self.model_name,
            'model_description': self.AVAILABLE_MODELS.get(self.model_name, 'Unknown model'),
            'device': self.device,
            'loaded': self.model is not None,
            'available_models': list(self.AVAILABLE_MODELS.keys()),
            'supported_languages_count': len(self.get_supported_languages()),
        }
    
    def unload_model(self):
        """모델 메모리에서 해제"""
        if self.model is not None:
            try:
                del self.model
                self.model = None
                logger.info(f"Whisper 모델 해제 완료: {self.model_name}")
            except Exception as e:
                logger.warning(f"모델 해제 중 오류: {e}")
    
    def __del__(self):
        """소멸자: 모델 메모리 해제"""
        try:
            self.unload_model()
        except:
            pass  # 소멸자에서는 오류를 무시