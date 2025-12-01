#!/usr/bin/env python3
"""커밋 메시지 유효성 검사 스크립트"""

import re
import sys
from pathlib import Path

# 커밋 메시지 규칙
TITLE_MAX_LENGTH = 72
BODY_MAX_LENGTH = 100
ALLOWED_TYPES = [
    "feat",  # 새로운 기능
    "fix",  # 버그 수정
    "docs",  # 문서 변경
    "style",  # 코드 포맷팅 (동작 변경 없음)
    "refactor",  # 리팩토링
    "perf",  # 성능 개선
    "test",  # 테스트 추가/수정
    "build",  # 빌드 시스템/외부 의존성 변경
    "ci",  # CI 설정 변경
    "chore",  # 기타 변경 (빌드 스크립트 등)
    "revert",  # 커밋 되돌리기
]

# 제목 패턴: type(scope): subject 또는 type: subject
TITLE_PATTERN = re.compile(
    rf"^({'|'.join(ALLOWED_TYPES)})"  # type
    r"(\([a-zA-Z0-9_-]+\))?"  # scope (optional)
    r":\s"  # colon and space
    r".+$"  # subject
)


def validate_commit_message(message: str) -> list[str]:
    """커밋 메시지 유효성 검사"""
    errors = []
    lines = message.strip().split("\n")

    if not lines:
        errors.append("커밋 메시지가 비어있습니다.")
        return errors

    title = lines[0]

    # 1. 제목 길이 검사
    if len(title) > TITLE_MAX_LENGTH:
        errors.append(
            f"제목이 너무 깁니다. "
            f"({len(title)}자 > {TITLE_MAX_LENGTH}자 제한)\n"
            f"  현재: {title}"
        )

    # 2. 제목 형식 검사 (Conventional Commits)
    if not TITLE_PATTERN.match(title):
        errors.append(
            f"제목 형식이 올바르지 않습니다.\n"
            f"  현재: {title}\n"
            f"  형식: <type>(<scope>): <subject>\n"
            f"  허용 타입: {', '.join(ALLOWED_TYPES)}\n"
            f"  예시: feat(users): 사용자 생성 API 추가"
        )

    # 3. 제목 끝 마침표 검사
    if title.endswith("."):
        errors.append("제목 끝에 마침표를 사용하지 마세요.")

    # 4. 본문이 있는 경우
    if len(lines) > 1:
        # 제목과 본문 사이 빈 줄 검사
        if lines[1].strip() != "":
            errors.append("제목과 본문 사이에 빈 줄이 필요합니다.")

        # 본문 각 줄 길이 검사
        for i, line in enumerate(lines[2:], start=3):
            if len(line) > BODY_MAX_LENGTH:
                errors.append(
                    f"본문 {i}번째 줄이 너무 깁니다. "
                    f"({len(line)}자 > {BODY_MAX_LENGTH}자 제한)\n"
                    f"  내용: {line[:50]}..."
                )

    return errors


def main():
    """메인 함수"""
    if len(sys.argv) < 2:
        print("사용법: commit-msg <commit-message-file>")
        sys.exit(1)

    commit_msg_file = Path(sys.argv[1])

    if not commit_msg_file.exists():
        print(f"파일을 찾을 수 없습니다: {commit_msg_file}")
        sys.exit(1)

    message = commit_msg_file.read_text(encoding="utf-8")

    # 주석 라인 제거 (# 으로 시작하는 줄)
    lines = [line for line in message.split("\n") if not line.startswith("#")]
    cleaned_message = "\n".join(lines).strip()

    errors = validate_commit_message(cleaned_message)

    if errors:
        print("\n❌ 커밋 메시지 검증 실패:\n")
        for error in errors:
            print(f"  • {error}\n")
        print("─" * 50)
        print("📝 Conventional Commits 형식을 따라주세요:")
        print("   <type>(<scope>): <subject>")
        print("")
        print("   [optional body]")
        print("─" * 50)
        sys.exit(1)

    print("✅ 커밋 메시지 검증 통과")
    sys.exit(0)


if __name__ == "__main__":
    main()
