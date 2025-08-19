"""
Claude Provider 테스트 - 비활성화됨

사용자 요구사항에 따라 anthropic 패키지가 설치되지 않았으므로
이 테스트들은 비활성화되었습니다.

TODO: anthropic 패키지 설치 후 활성화 예정
"""

import pytest

# Claude Provider 테스트는 anthropic 패키지가 설치되지 않았으므로 비활성화
pytestmark = pytest.mark.skip(reason="Claude provider tests disabled - anthropic package not installed")


def test_placeholder():
    """Claude provider 테스트 placeholder"""
    pass