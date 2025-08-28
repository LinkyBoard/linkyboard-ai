"""
Legacy Adapter - 레거시 어댑터

V2 Agent 시스템에서 기존 V1 시스템을 호출할 수 있도록 어댑터를 제공합니다.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)


class LegacyAdapter:
    """레거시 시스템 어댑터"""
    
    def __init__(self):
        self.supported_request_types = [
            'board_analysis',
            'clipper', 
            'summary',
            'content_analysis'
        ]
        
    async def process_request(
        self,
        request_type: str,
        request_data: Dict[str, Any],
        user_id: int,
        board_id: Optional[int] = None,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        레거시 시스템으로 요청 처리
        
        Args:
            request_type: 요청 타입
            request_data: 요청 데이터  
            user_id: 사용자 ID
            board_id: 보드 ID
            session: DB 세션
            
        Returns:
            처리 결과
        """
        try:
            logger.info(f"Processing legacy request: {request_type} for user {user_id}")
            
            if request_type not in self.supported_request_types:
                raise ValueError(f"Unsupported request type: {request_type}")
            
            # 요청 타입별 레거시 시스템 호출
            if request_type == 'board_analysis':
                return await self._handle_board_analysis(request_data, user_id, board_id, session)
            
            elif request_type == 'clipper':
                return await self._handle_clipper(request_data, user_id, board_id, session)
            
            elif request_type == 'summary':
                return await self._handle_summary(request_data, user_id, board_id, session)
                
            elif request_type == 'content_analysis':
                return await self._handle_content_analysis(request_data, user_id, board_id, session)
            
            else:
                raise ValueError(f"Handler not implemented for: {request_type}")
                
        except Exception as e:
            logger.error(f"Legacy request processing failed: {e}")
            raise
    
    async def _handle_board_analysis(
        self,
        request_data: Dict[str, Any],
        user_id: int,
        board_id: Optional[int],
        session: Optional[AsyncSession]
    ) -> Dict[str, Any]:
        """보드 분석 처리"""
        try:
            # 실제 구현에서는 기존 BoardAI Service를 호출
            # 현재는 모의 응답 반환
            
            logger.info(f"Legacy board analysis for board {board_id}")
            
            # 기존 서비스 호출 시뮬레이션
            await asyncio.sleep(0.1)  # 처리 시간 시뮬레이션
            
            # 모의 분석 결과
            analysis_result = {
                'board_id': board_id,
                'analysis_type': 'comprehensive',
                'summary': '보드의 주요 내용을 분석했습니다.',
                'key_points': [
                    '주요 포인트 1',
                    '주요 포인트 2', 
                    '주요 포인트 3'
                ],
                'categories': ['일반', '업무'],
                'sentiment': 'neutral',
                'confidence_score': 0.87
            }
            
            return {
                'success': True,
                'content': analysis_result,
                'wtu_consumed': 1.5,
                'execution_time_ms': 100,
                'metadata': {
                    'processing_method': 'legacy_board_analysis',
                    'timestamp': datetime.now().isoformat(),
                    'model_used': 'legacy-model'
                }
            }
            
        except Exception as e:
            logger.error(f"Legacy board analysis failed: {e}")
            return {
                'success': False,
                'error_message': str(e),
                'wtu_consumed': 0.0,
                'execution_time_ms': 0
            }
    
    async def _handle_clipper(
        self,
        request_data: Dict[str, Any],
        user_id: int,
        board_id: Optional[int],
        session: Optional[AsyncSession]
    ) -> Dict[str, Any]:
        """클리퍼 처리"""
        try:
            # 실제 구현에서는 기존 Clipper Service를 호출
            
            url = request_data.get('url', '')
            logger.info(f"Legacy clipper processing for URL: {url}")
            
            await asyncio.sleep(0.2)  # 처리 시간 시뮬레이션
            
            clipper_result = {
                'url': url,
                'title': 'Extracted Title from URL',
                'summary': 'URL 내용을 요약했습니다.',
                'content': 'Extracted content from the webpage...',
                'tags': ['tag1', 'tag2', 'tag3'],
                'category': 'general',
                'extraction_method': 'legacy_clipper'
            }
            
            return {
                'success': True,
                'content': clipper_result,
                'wtu_consumed': 2.0,
                'execution_time_ms': 200,
                'metadata': {
                    'processing_method': 'legacy_clipper',
                    'timestamp': datetime.now().isoformat(),
                    'model_used': 'legacy-model'
                }
            }
            
        except Exception as e:
            logger.error(f"Legacy clipper failed: {e}")
            return {
                'success': False,
                'error_message': str(e),
                'wtu_consumed': 0.0,
                'execution_time_ms': 0
            }
    
    async def _handle_summary(
        self,
        request_data: Dict[str, Any],
        user_id: int,
        board_id: Optional[int],
        session: Optional[AsyncSession]
    ) -> Dict[str, Any]:
        """요약 처리"""
        try:
            content = request_data.get('content', '')
            summary_type = request_data.get('summary_type', 'general')
            
            logger.info(f"Legacy summary generation: type={summary_type}")
            
            await asyncio.sleep(0.15)  # 처리 시간 시뮬레이션
            
            summary_result = {
                'summary': f'{summary_type} 요약이 생성되었습니다.',
                'summary_type': summary_type,
                'key_points': [
                    '핵심 포인트 1',
                    '핵심 포인트 2'
                ],
                'word_count': 150,
                'original_length': len(content),
                'compression_ratio': 0.1
            }
            
            return {
                'success': True,
                'content': summary_result,
                'wtu_consumed': 1.2,
                'execution_time_ms': 150,
                'metadata': {
                    'processing_method': 'legacy_summary',
                    'timestamp': datetime.now().isoformat(),
                    'model_used': 'legacy-model'
                }
            }
            
        except Exception as e:
            logger.error(f"Legacy summary failed: {e}")
            return {
                'success': False,
                'error_message': str(e),
                'wtu_consumed': 0.0,
                'execution_time_ms': 0
            }
    
    async def _handle_content_analysis(
        self,
        request_data: Dict[str, Any],
        user_id: int,
        board_id: Optional[int],
        session: Optional[AsyncSession]
    ) -> Dict[str, Any]:
        """콘텐츠 분석 처리"""
        try:
            content = request_data.get('content', '')
            analysis_type = request_data.get('analysis_type', 'basic')
            
            logger.info(f"Legacy content analysis: type={analysis_type}")
            
            await asyncio.sleep(0.2)  # 처리 시간 시뮬레이션
            
            analysis_result = {
                'analysis_type': analysis_type,
                'summary': '콘텐츠 분석이 완료되었습니다.',
                'keywords': ['키워드1', '키워드2', '키워드3'],
                'entities': [
                    {'type': 'PERSON', 'value': 'John Doe', 'confidence': 0.9},
                    {'type': 'ORGANIZATION', 'value': 'Company', 'confidence': 0.8}
                ],
                'sentiment': {
                    'overall': 'positive',
                    'confidence': 0.75
                },
                'topics': ['topic1', 'topic2'],
                'quality_score': 0.82
            }
            
            return {
                'success': True,
                'content': analysis_result,
                'wtu_consumed': 1.8,
                'execution_time_ms': 200,
                'metadata': {
                    'processing_method': 'legacy_content_analysis',
                    'timestamp': datetime.now().isoformat(),
                    'model_used': 'legacy-model'
                }
            }
            
        except Exception as e:
            logger.error(f"Legacy content analysis failed: {e}")
            return {
                'success': False,
                'error_message': str(e),
                'wtu_consumed': 0.0,
                'execution_time_ms': 0
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """레거시 시스템 건강성 확인"""
        try:
            # 실제 구현에서는 레거시 서비스들의 상태를 확인
            # 현재는 모의 응답
            
            health_status = {
                'status': 'ok',
                'services': {
                    'board_ai': 'healthy',
                    'clipper': 'healthy',
                    'summary_generator': 'healthy'
                },
                'supported_requests': self.supported_request_types,
                'timestamp': datetime.now().isoformat()
            }
            
            return health_status
            
        except Exception as e:
            logger.error(f"Legacy health check failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_supported_requests(self) -> List[str]:
        """지원되는 요청 타입 목록 반환"""
        return self.supported_request_types.copy()


# 글로벌 레거시 어댑터 인스턴스
legacy_adapter = LegacyAdapter()