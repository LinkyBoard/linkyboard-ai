"""요약 도메인 타입 정의"""

from dataclasses import dataclass

from app.core.llm.types import LLMResult
from app.core.llm.wtu import calculate_wtu_from_tokens


@dataclass
class SummaryPipelineResult:
    """요약 파이프라인 실행 결과

    요약, 태그 추출, 카테고리 예측의 LLM 호출 결과를 담습니다.

    Attributes:
        summary: 요약 생성 결과
        tags: 태그 추출 결과
        category: 카테고리 예측 결과

    Example::

        result = SummaryPipelineResult(
            summary=summary_llm_result,
            tags=tag_llm_result,
            category=category_llm_result
        )

        # WTU 계산
        total_wtu = result.calculate_total_wtu()

        # 개별 접근
        summary_text = result.summary.content
        tag_list = parse_json(result.tags.content)
    """

    summary: LLMResult
    tags: LLMResult
    category: LLMResult

    def calculate_total_wtu(self) -> int:
        """전체 WTU 계산

        3개 LLM 호출(요약, 태그, 카테고리)의 WTU를 합산합니다.

        Returns:
            int: 총 WTU (Weighted Token Unit)
        """
        return sum(
            [
                calculate_wtu_from_tokens(
                    result.input_tokens, result.output_tokens, result.model
                )
                for result in [self.summary, self.tags, self.category]
            ]
        )
