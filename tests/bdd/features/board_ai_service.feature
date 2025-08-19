Feature: Board AI Service
  보드 AI 서비스는 사용자의 질문에 대해 선택된 모델로 답변을 제공해야 함

  Background:
    Given 보드 AI 서비스가 초기화되어 있음
    And 사용자 ID 1001이 있음
    And 보드 ID가 생성되어 있음

  Scenario: 모델 선택을 통한 질문 응답
    Given "gpt-3.5-turbo" 모델이 사용 가능함
    When 사용자가 "Python의 장점은 무엇인가요?" 질문을 "gpt-3.5-turbo" 모델로 요청함
    Then 성공적인 답변을 받아야 함
    And 답변에는 마크다운 형식의 내용이 포함되어야 함
    And 사용량 정보가 포함되어야 함
    And 라우팅 정보에 선택된 모델이 표시되어야 함

  Scenario: 예산 제한 내에서 질문 처리
    Given "gpt-3.5-turbo" 모델이 사용 가능함
    And 예산 제한이 1000 WTU로 설정됨
    When 사용자가 짧은 질문을 요청함
    Then 예산 내에서 성공적으로 처리되어야 함
    And 사용된 WTU가 예산보다 적어야 함

  Scenario: 예산 초과 시 오류 발생
    Given "gpt-3.5-turbo" 모델이 사용 가능함
    And 예산 제한이 10 WTU로 설정됨
    When 사용자가 긴 질문을 요청함
    Then "Budget exceeded" 오류가 발생해야 함

  Scenario: 선택된 아이템 기반 질문 응답
    Given "gpt-3.5-turbo" 모델이 사용 가능함
    And 테스트 아이템이 데이터베이스에 저장되어 있음
    And 아이템 선택 정보가 준비되어 있음
    When 사용자가 선택된 아이템 기반으로 질문함
    Then 성공적인 답변을 받아야 함
    And 사용된 아이템 정보가 응답에 포함되어야 함
    And 아이템의 제목과 요약이 표시되어야 함

  Scenario: 유효하지 않은 아이템 선택 시 오류
    Given "gpt-3.5-turbo" 모델이 사용 가능함
    And 존재하지 않는 아이템이 선택됨
    When 사용자가 선택된 아이템 기반으로 질문함
    Then "선택된 아이템 중 사용할 수 있는 것이 없습니다" 오류가 발생해야 함

  Scenario: 초안 생성 기능
    Given "gpt-3.5-turbo" 모델이 사용 가능함
    And 아웃라인 ["서론", "본론", "결론"]이 제공됨
    When 사용자가 초안 생성을 요청함
    Then 성공적인 초안을 받아야 함
    And 초안에는 제공된 아웃라인이 반영되어야 함
    And 마크다운 형식으로 작성되어야 함

  Scenario: 모델 미지정 시 기본 모델 사용
    Given 활성화된 모델들이 있음
    When 사용자가 모델을 지정하지 않고 질문함
    Then 기본 모델이 자동으로 선택되어야 함
    And 성공적인 답변을 받아야 함