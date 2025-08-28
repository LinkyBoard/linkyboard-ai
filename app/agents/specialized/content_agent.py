"""
Content Analysis Agent - 콘텐츠 분석 전문 에이전트

웹 페이지, 문서, 텍스트 등의 콘텐츠를 분석하고 구조화된 정보를 추출합니다.
"""

from typing import Dict, Any, List, Optional
import json
import re
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.ai.providers.router import ai_router
from ..core.base_agent import AIAgent
from ..schemas import AgentContext

logger = get_logger(__name__)


class ContentAnalysisAgent(AIAgent):
    """콘텐츠 분석 에이전트"""
    
    def __init__(self):
        super().__init__(
            agent_name="ContentAnalysisAgent",
            default_model="gpt-4o-mini"
        )
        self.analysis_types = [
            "structure_analysis",
            "entity_extraction", 
            "sentiment_analysis",
            "topic_classification",
            "key_information_extraction"
        ]
    
    def get_agent_type(self) -> str:
        return "content_analysis"
    
    def get_capabilities(self) -> List[str]:
        return [
            "웹 페이지 구조 분석",
            "엔티티 및 키워드 추출",
            "감정 분석",
            "주제 분류",
            "핵심 정보 요약",
            "메타데이터 추출",
            "콘텐츠 품질 평가"
        ]
    
    async def validate_input(self, input_data: Dict[str, Any], context: AgentContext) -> bool:
        """입력 데이터 유효성 검증"""
        try:
            # 필수 필드 확인
            if not input_data.get('content') and not input_data.get('url'):
                logger.warning("No content or URL provided for analysis")
                return False
            
            # 콘텐츠 길이 제한 확인 (너무 큰 콘텐츠는 처리 제한)
            content = input_data.get('content', '')
            if len(content) > 500000:  # 500KB 제한
                logger.warning(f"Content too large: {len(content)} characters")
                return False
            
            # 분석 타입 유효성 확인
            analysis_type = input_data.get('analysis_type', 'comprehensive')
            valid_types = self.analysis_types + ['comprehensive', 'basic']
            if analysis_type not in valid_types:
                logger.warning(f"Invalid analysis type: {analysis_type}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Input validation failed: {e}")
            return False
    
    async def execute_ai_task(
        self,
        input_data: Dict[str, Any],
        model_name: str,
        context: AgentContext
    ) -> Dict[str, Any]:
        """콘텐츠 분석 AI 작업 실행"""
        try:
            # 1. 입력 데이터 처리
            content = input_data.get('content', '')
            url = input_data.get('url', '')
            analysis_type = input_data.get('analysis_type', 'comprehensive')
            board_id = context.board_id
            
            # URL에서 콘텐츠 가져오기 (필요한 경우)
            if not content and url:
                content = await self._fetch_content_from_url(url)
            
            if not content:
                raise ValueError("No content available for analysis")
            
            # 2. 분석 유형에 따른 프롬프트 생성
            system_prompt = await self._build_analysis_prompt(analysis_type, context)
            user_prompt = await self._build_user_prompt(content, url, input_data)
            
            logger.info(f"Starting content analysis with {model_name}, type: {analysis_type}")
            
            # 3. AI 모델 호출
            response = await ai_router.chat_completion(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                user_id=context.user_id,
                board_id=board_id,
                temperature=0.2,  # 분석 작업이므로 낮은 temperature
                max_tokens=4000
            )
            
            # 4. 응답 파싱 및 구조화
            analysis_result = await self._parse_analysis_response(
                response, analysis_type, content, url
            )
            
            # 5. 결과 검증 및 보강
            validated_result = await self._validate_and_enhance_result(
                analysis_result, content, context
            )
            
            return {
                'content': validated_result,
                'metadata': {
                    'analysis_type': analysis_type,
                    'content_length': len(content),
                    'url': url,
                    'model_selection_reason': 'user_preference_with_task_optimization',
                    'processing_time': datetime.now().isoformat()
                },
                'usage': response.get('usage', {}),
                'model_response_raw': response.get('content', '')
            }
            
        except Exception as e:
            logger.error(f"Content analysis execution failed: {e}")
            raise
    
    async def _fetch_content_from_url(self, url: str) -> str:
        """URL에서 콘텐츠 가져오기"""
        try:
            # 이 부분은 실제로는 웹 스크래핑 로직이 들어가야 함
            # 현재는 플레이스홀더로 처리
            logger.warning(f"URL content fetching not implemented: {url}")
            return f"Content from URL: {url}"
            
        except Exception as e:
            logger.error(f"Failed to fetch content from URL {url}: {e}")
            return ""
    
    async def _build_analysis_prompt(self, analysis_type: str, context: AgentContext) -> str:
        """분석 타입에 따른 시스템 프롬프트 생성"""
        
        base_prompt = """당신은 전문적인 콘텐츠 분석 AI 에이전트입니다. 
주어진 콘텐츠를 분석하여 구조화된 정보를 추출하고 인사이트를 제공합니다."""
        
        if analysis_type == "comprehensive":
            return f"""{base_prompt}

다음과 같은 포괄적인 분석을 수행해주세요:

1. **구조 분석**: 콘텐츠의 전반적인 구조와 구성 요소
2. **핵심 정보 추출**: 주요 키워드, 엔티티, 중요한 데이터
3. **주제 분류**: 콘텐츠의 주요 주제와 카테고리
4. **감정 및 톤 분석**: 전반적인 감정과 어조
5. **품질 평가**: 콘텐츠의 신뢰성, 완성도, 정확성
6. **메타데이터**: 작성일, 저자, 소스 등 메타 정보

결과는 JSON 형태로 구조화하여 반환해주세요."""

        elif analysis_type == "entity_extraction":
            return f"""{base_prompt}

다음 엔티티들을 추출해주세요:
- 인명 (PERSON)
- 조직명 (ORGANIZATION) 
- 위치 (LOCATION)
- 날짜/시간 (DATE)
- 숫자/수치 (NUMBER)
- 기술/제품명 (TECHNOLOGY)
- 기타 중요 엔티티

각 엔티티는 타입, 값, 신뢰도와 함께 JSON으로 반환해주세요."""

        elif analysis_type == "sentiment_analysis":
            return f"""{base_prompt}

감정 분석을 수행해주세요:
- 전반적인 감정 (positive/negative/neutral)
- 감정 강도 (0-1 스케일)
- 세부 감정 분류 (기쁨, 슬픔, 분노, 두려움 등)
- 감정의 근거가 되는 텍스트 구간

결과를 JSON으로 구조화해주세요."""

        elif analysis_type == "topic_classification":
            return f"""{base_prompt}

주제 분류를 수행해주세요:
- 주요 주제 카테고리 (최대 5개)
- 각 주제의 관련도 점수 (0-1)
- 주제별 핵심 키워드
- 주제 간 연관성 분석

결과를 JSON으로 구조화해주세요."""

        else:  # basic or other types
            return f"""{base_prompt}

기본적인 콘텐츠 분석을 수행해주세요:
- 주요 키워드 및 핵심 정보
- 콘텐츠 요약 (3-5 문장)
- 주제 분류
- 중요도 평가

결과를 JSON으로 구조화해주세요."""
    
    async def _build_user_prompt(self, content: str, url: str, input_data: Dict[str, Any]) -> str:
        """사용자 프롬프트 생성"""
        
        prompt_parts = []
        
        if url:
            prompt_parts.append(f"**분석 대상 URL**: {url}")
        
        # 콘텐츠가 너무 길면 일부만 사용
        if len(content) > 50000:
            content = content[:50000] + "... [콘텐츠 일부 생략]"
        
        prompt_parts.append(f"**분석할 콘텐츠**:\n{content}")
        
        # 추가 분석 지시사항
        if input_data.get('focus_areas'):
            focus_areas = input_data['focus_areas']
            prompt_parts.append(f"**중점 분석 영역**: {', '.join(focus_areas)}")
        
        if input_data.get('custom_instructions'):
            prompt_parts.append(f"**추가 지시사항**: {input_data['custom_instructions']}")
        
        return "\n\n".join(prompt_parts)
    
    async def _parse_analysis_response(
        self,
        response: Dict[str, Any],
        analysis_type: str,
        original_content: str,
        url: str
    ) -> Dict[str, Any]:
        """AI 응답 파싱 및 구조화"""
        try:
            content = response.get('content', '')
            
            # JSON 응답 파싱 시도
            try:
                # JSON 블록 추출
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    # JSON 블록이 없으면 전체 내용에서 JSON 찾기
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                    else:
                        json_str = content
                
                parsed_result = json.loads(json_str)
                
            except json.JSONDecodeError:
                # JSON 파싱 실패시 텍스트 기반 파싱
                parsed_result = await self._parse_text_response(content, analysis_type)
            
            # 기본 메타데이터 추가
            parsed_result['analysis_metadata'] = {
                'agent_name': self.agent_name,
                'analysis_type': analysis_type,
                'content_length': len(original_content),
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'content_preview': original_content[:200] + "..." if len(original_content) > 200 else original_content
            }
            
            return parsed_result
            
        except Exception as e:
            logger.error(f"Failed to parse analysis response: {e}")
            # 파싱 실패시 기본 구조 반환
            return {
                'analysis_result': response.get('content', ''),
                'error': f'파싱 실패: {str(e)}',
                'analysis_metadata': {
                    'agent_name': self.agent_name,
                    'analysis_type': analysis_type,
                    'timestamp': datetime.now().isoformat(),
                    'parsing_failed': True
                }
            }
    
    async def _parse_text_response(self, content: str, analysis_type: str) -> Dict[str, Any]:
        """텍스트 응답을 구조화"""
        
        result = {
            'raw_response': content,
            'parsing_method': 'text_extraction'
        }
        
        # 간단한 텍스트 파싱 로직
        if analysis_type == "comprehensive":
            result.update({
                'summary': self._extract_section(content, ['요약', 'summary']),
                'keywords': self._extract_keywords(content),
                'topics': self._extract_section(content, ['주제', 'topic', '분류']),
                'sentiment': self._extract_section(content, ['감정', 'sentiment', '톤'])
            })
        
        elif analysis_type == "entity_extraction":
            result['entities'] = self._extract_entities_from_text(content)
        
        elif analysis_type == "sentiment_analysis":
            result['sentiment_analysis'] = self._extract_sentiment_from_text(content)
        
        return result
    
    def _extract_section(self, text: str, keywords: List[str]) -> str:
        """텍스트에서 특정 섹션 추출"""
        for keyword in keywords:
            pattern = rf'({keyword}[:\s]*)(.+?)(?=\n\n|\n[A-Z]|$)'
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(2).strip()
        return ""
    
    def _extract_keywords(self, text: str) -> List[str]:
        """키워드 추출"""
        # 간단한 키워드 추출 로직
        keyword_pattern = r'키워드[:\s]*(.+?)(?=\n|$)'
        match = re.search(keyword_pattern, text, re.IGNORECASE)
        if match:
            keywords_text = match.group(1)
            return [kw.strip() for kw in re.split(r'[,;]', keywords_text) if kw.strip()]
        return []
    
    def _extract_entities_from_text(self, text: str) -> List[Dict[str, Any]]:
        """텍스트에서 엔티티 추출"""
        # 이 부분은 실제로는 더 정교한 NLP 라이브러리를 사용해야 함
        entities = []
        
        # 간단한 패턴 매칭
        patterns = {
            'PERSON': r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',
            'DATE': r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}',
            'NUMBER': r'\b\d+(?:,\d{3})*(?:\.\d+)?\b'
        }
        
        for entity_type, pattern in patterns.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                entities.append({
                    'type': entity_type,
                    'value': match.group(),
                    'start': match.start(),
                    'end': match.end(),
                    'confidence': 0.8  # 패턴 매칭이므로 중간 신뢰도
                })
        
        return entities
    
    def _extract_sentiment_from_text(self, text: str) -> Dict[str, Any]:
        """텍스트에서 감정 분석 결과 추출"""
        # 간단한 감정 분석 결과 파싱
        sentiment_info = {
            'overall_sentiment': 'neutral',
            'confidence': 0.5,
            'details': {}
        }
        
        # 감정 관련 키워드 찾기
        positive_patterns = r'긍정|좋|훌륭|excellent|good|positive'
        negative_patterns = r'부정|나쁨|terrible|bad|negative'
        
        if re.search(positive_patterns, text, re.IGNORECASE):
            sentiment_info['overall_sentiment'] = 'positive'
            sentiment_info['confidence'] = 0.7
        elif re.search(negative_patterns, text, re.IGNORECASE):
            sentiment_info['overall_sentiment'] = 'negative'
            sentiment_info['confidence'] = 0.7
        
        return sentiment_info
    
    async def _validate_and_enhance_result(
        self,
        result: Dict[str, Any],
        original_content: str,
        context: AgentContext
    ) -> Dict[str, Any]:
        """분석 결과 검증 및 보강"""
        try:
            # 1. 필수 필드 확인 및 추가
            if 'analysis_metadata' not in result:
                result['analysis_metadata'] = {}
            
            result['analysis_metadata'].update({
                'validation_passed': True,
                'content_stats': {
                    'character_count': len(original_content),
                    'word_count_estimate': len(original_content.split()),
                    'line_count': original_content.count('\n') + 1
                }
            })
            
            # 2. 품질 점수 계산
            quality_score = await self._calculate_analysis_quality_score(result, original_content)
            result['analysis_metadata']['quality_score'] = quality_score
            
            # 3. 레퍼런스 자료와의 연관성 체크 (있는 경우)
            if context.reference_materials:
                reference_relevance = await self._check_reference_relevance(
                    result, context.reference_materials
                )
                result['analysis_metadata']['reference_relevance'] = reference_relevance
            
            return result
            
        except Exception as e:
            logger.error(f"Result validation failed: {e}")
            result['analysis_metadata'] = result.get('analysis_metadata', {})
            result['analysis_metadata']['validation_error'] = str(e)
            return result
    
    async def _calculate_analysis_quality_score(
        self,
        result: Dict[str, Any],
        original_content: str
    ) -> float:
        """분석 품질 점수 계산"""
        score = 0.0
        
        try:
            # 기본 점수 (결과가 있으면 0.5)
            if result and len(str(result)) > 100:
                score += 0.5
            
            # 구조화 정도 (JSON 파싱 성공시 추가 점수)
            if isinstance(result, dict) and not result.get('parsing_failed'):
                score += 0.3
            
            # 분석 깊이 (여러 분석 항목이 있으면 점수 추가)
            analysis_items = 0
            for key in ['summary', 'keywords', 'entities', 'sentiment', 'topics']:
                if key in result and result[key]:
                    analysis_items += 1
            
            score += min(0.2, analysis_items * 0.04)  # 최대 0.2점
            
            # 최종 점수 정규화
            return min(1.0, score)
            
        except Exception as e:
            logger.warning(f"Quality score calculation failed: {e}")
            return 0.5  # 기본 점수
    
    async def _check_reference_relevance(
        self,
        result: Dict[str, Any],
        reference_materials: List[str]
    ) -> Dict[str, Any]:
        """레퍼런스 자료와의 연관성 확인"""
        # 현재는 기본 구현
        # 실제로는 벡터 유사도나 키워드 매칭을 통한 연관성 분석이 필요
        
        return {
            'reference_count': len(reference_materials),
            'relevance_checked': True,
            'relevance_score': 0.7,  # 기본값
            'note': 'Reference relevance checking not fully implemented'
        }