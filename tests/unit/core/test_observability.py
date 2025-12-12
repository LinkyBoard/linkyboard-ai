# LLM API 호출 테스트 - 주석처리됨
# run_with_fallback에서 실제 API 호출 발생 방지

# """Observability 모듈 테스트
# 
# LangFuse 초기화 및 observe 데코레이터 테스트
# """
# 
# from unittest.mock import MagicMock, patch
# 
# import pytest
# 
# 
# class TestInitializeLangfuse:
#     """initialize_langfuse 함수 테스트"""
# 
#     @patch("app.core.llm.observability.Langfuse")
#     @patch("app.core.llm.observability.settings")
#     def test_initialize_langfuse_success(
#         self, mock_settings, mock_langfuse_class
#     ):
#         """LangFuse 초기화 성공 케이스"""
#         # Given
#         mock_settings.langfuse_secret_key = "test-secret-key"
#         mock_settings.langfuse_public_key = "test-public-key"
#         mock_settings.langfuse_host = "https://test.langfuse.com"
# 
#         mock_client = MagicMock()
#         mock_langfuse_class.return_value = mock_client
# 
#         # 모듈 다시 import하여 initialize_langfuse 실행
#         from app.core.llm.observability import initialize_langfuse
# 
#         # When
#         result = initialize_langfuse()
# 
#         # Then
#         assert result is not None
#         mock_langfuse_class.assert_called_with(
#             secret_key="test-secret-key",
#             public_key="test-public-key",
#             host="https://test.langfuse.com",
#         )
# 
#     @patch("app.core.llm.observability.Langfuse")
#     @patch("app.core.llm.observability.settings")
#     def test_initialize_langfuse_failure(
#         self, mock_settings, mock_langfuse_class
#     ):
#         """LangFuse 초기화 실패 시 None 반환"""
#         # Given
#         mock_settings.langfuse_secret_key = "test-secret-key"
#         mock_settings.langfuse_public_key = "test-public-key"
#         mock_settings.langfuse_host = "https://test.langfuse.com"
# 
#         mock_langfuse_class.side_effect = Exception("Connection failed")
# 
#         from app.core.llm.observability import initialize_langfuse
# 
#         # When
#         result = initialize_langfuse()
# 
#         # Then
#         assert result is None
# 
#     @patch("app.core.llm.observability.Langfuse")
#     @patch("app.core.llm.observability.settings")
#     def test_initialize_langfuse_sets_environment_variables(
#         self, mock_settings, mock_langfuse_class
#     ):
#         """LangFuse 초기화 시 환경 변수 설정 확인"""
#         import os
# 
#         # Given
#         mock_settings.langfuse_secret_key = "env-secret-key"
#         mock_settings.langfuse_public_key = "env-public-key"
#         mock_settings.langfuse_host = "https://env.langfuse.com"
# 
#         mock_langfuse_class.return_value = MagicMock()
# 
#         from app.core.llm.observability import initialize_langfuse
# 
#         # When
#         initialize_langfuse()
# 
#         # Then
#         assert os.environ.get("LANGFUSE_SECRET_KEY") == "env-secret-key"
#         assert os.environ.get("LANGFUSE_PUBLIC_KEY") == "env-public-key"
#         assert os.environ.get("LANGFUSE_HOST") == "https://env.langfuse.com"
# 
# 
# class TestGetObserveDecorator:
#     """get_observe_decorator 함수 테스트"""
# 
#     def test_noop_decorator_returns_original_function(self):
#         """no-op 데코레이터가 원본 함수를 그대로 반환하는지 확인"""
# 
#         # Given: no-op 데코레이터 직접 생성
#         def noop_observe(*args, **kwargs):
#             def decorator(func):
#                 return func
# 
#             return decorator
# 
#         @noop_observe()
#         def sample_function():
#             return "original"
# 
#         # When
#         result = sample_function()
# 
#         # Then
#         assert result == "original"
# 
#     def test_noop_decorator_with_arguments(self):
#         """no-op 데코레이터가 인자와 함께 사용될 때 동작 확인"""
# 
#         # Given
#         def noop_observe(*args, **kwargs):
#             def decorator(func):
#                 return func
# 
#             return decorator
# 
#         @noop_observe(name="test_span")
#         def sample_function_with_args(x, y):
#             return x + y
# 
#         # When
#         result = sample_function_with_args(1, 2)
# 
#         # Then
#         assert result == 3
# 
#     async def test_noop_decorator_preserves_async_function(self):
#         """no-op 데코레이터가 async 함수를 보존하는지 확인"""
# 
#         # Given
#         def noop_observe(*args, **kwargs):
#             def decorator(func):
#                 return func
# 
#             return decorator
# 
#         @noop_observe()
#         async def async_sample_function():
#             return "async result"
# 
#         # When
#         result = await async_sample_function()
# 
#         # Then
#         assert result == "async result"
# 
#     @patch("app.core.llm.observability.langfuse_client", None)
#     def test_get_observe_decorator_returns_noop_when_langfuse_unavailable(
#         self,
#     ):
#         """LangFuse가 없을 때 no-op 데코레이터 반환"""
#         # Given
#         from app.core.llm.observability import get_observe_decorator
# 
#         observe = get_observe_decorator()
# 
#         @observe()
#         def test_function():
#             return "test"
# 
#         # When
#         result = test_function()
# 
#         # Then
#         assert result == "test"
# 
#     @patch("app.core.llm.observability.langfuse_client")
#     def test_get_observe_decorator_returns_langfuse_observe_when_available(
#         self, mock_client
#     ):
#         """LangFuse가 있을 때 langfuse observe 데코레이터 반환"""
#         # Given
#         mock_client.__bool__ = lambda self: True  # truthy 값으로 만듦
# 
#         from app.core.llm.observability import get_observe_decorator, observe
# 
#         # When
#         result_decorator = get_observe_decorator()
# 
#         # Then
#         assert result_decorator == observe
# 
# 
# class TestObservabilityGracefulDegradation:
#     """Observability graceful degradation 테스트"""
# 
#     def test_decorated_function_works_without_langfuse(self):
#         """LangFuse 없이도 데코레이트된 함수가 정상 동작"""
# 
#         # Given: no-op 데코레이터 시뮬레이션
#         def noop_observe(*args, **kwargs):
#             def decorator(func):
#                 return func
# 
#             return decorator
# 
#         observe = noop_observe
# 
#         @observe()
#         def business_logic():
#             return {"status": "success", "data": [1, 2, 3]}
# 
#         # When
#         result = business_logic()
# 
#         # Then
#         assert result == {"status": "success", "data": [1, 2, 3]}
# 
#     async def test_decorated_async_function_works_without_langfuse(self):
#         """LangFuse 없이도 async 데코레이트된 함수가 정상 동작"""
# 
#         # Given
#         def noop_observe(*args, **kwargs):
#             def decorator(func):
#                 return func
# 
#             return decorator
# 
#         observe = noop_observe
# 
#         @observe(name="async_operation")
#         async def async_business_logic(value: int):
#             return value * 2
# 
#         # When
#         result = await async_business_logic(5)
# 
#         # Then
#         assert result == 10
# 
#     def test_decorated_function_with_exception_propagates_error(self):
#         """데코레이트된 함수에서 발생한 예외가 정상적으로 전파"""
# 
#         # Given
#         def noop_observe(*args, **kwargs):
#             def decorator(func):
#                 return func
# 
#             return decorator
# 
#         observe = noop_observe
# 
#         @observe()
#         def failing_function():
#             raise ValueError("Expected error")
# 
#         # When/Then
#         with pytest.raises(ValueError, match="Expected error"):
#             failing_function()
# 
#     def test_multiple_decorated_functions_work_independently(self):
#         """여러 데코레이트된 함수가 독립적으로 동작"""
# 
#         # Given
#         def noop_observe(*args, **kwargs):
#             def decorator(func):
#                 return func
# 
#             return decorator
# 
#         observe = noop_observe
# 
#         @observe(name="func1")
#         def function_one():
#             return "one"
# 
#         @observe(name="func2")
#         def function_two():
#             return "two"
# 
#         @observe(name="func3")
#         def function_three():
#             return "three"
# 
#         # When
#         results = [function_one(), function_two(), function_three()]
# 
#         # Then
#         assert results == ["one", "two", "three"]
