#!/bin/bash
# pre-push 테스트 스크립트
# poetry 환경에서 pytest 실행

cd "$(git rev-parse --show-toplevel)" || exit 1

# poetry virtualenv 경로 찾기 (여러 방법 시도)
find_pytest() {
    # 1. poetry env info 시도 (python 심볼릭 링크가 있는 경우)
    if command -v poetry &> /dev/null; then
        VENV_PATH=$(poetry env info -p 2>/dev/null)
        if [ -n "$VENV_PATH" ] && [ -x "$VENV_PATH/bin/pytest" ]; then
            echo "$VENV_PATH/bin/pytest"
            return
        fi
    fi

    # 2. 프로젝트 내 .venv 확인
    if [ -x ".venv/bin/pytest" ]; then
        echo ".venv/bin/pytest"
        return
    fi

    # 3. poetry 캐시 디렉토리에서 찾기
    POETRY_CACHE="$HOME/Library/Caches/pypoetry/virtualenvs"
    if [ -d "$POETRY_CACHE" ]; then
        PROJECT_NAME=$(basename "$(pwd)")
        VENV_DIR=$(ls -d "$POETRY_CACHE/${PROJECT_NAME}"* 2>/dev/null | head -1)
        if [ -n "$VENV_DIR" ] && [ -x "$VENV_DIR/bin/pytest" ]; then
            echo "$VENV_DIR/bin/pytest"
            return
        fi
        # pyproject.toml의 name으로도 시도
        if [ -f "pyproject.toml" ]; then
            PKG_NAME=$(grep '^name = ' pyproject.toml | head -1 | cut -d'"' -f2)
            VENV_DIR=$(ls -d "$POETRY_CACHE/${PKG_NAME}"* 2>/dev/null | head -1)
            if [ -n "$VENV_DIR" ] && [ -x "$VENV_DIR/bin/pytest" ]; then
                echo "$VENV_DIR/bin/pytest"
                return
            fi
        fi
    fi

    # 4. 시스템 pytest
    if command -v pytest &> /dev/null; then
        echo "pytest"
        return
    fi
}

PYTEST_CMD=$(find_pytest)

if [ -n "$PYTEST_CMD" ]; then
    exec "$PYTEST_CMD" -v --tb=short
else
    echo "pytest를 찾을 수 없습니다. poetry install을 실행해주세요."
    exit 1
fi
