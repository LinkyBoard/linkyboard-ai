#!/bin/bash
set -Eeuo pipefail

echo "📊 현재 마이그레이션 상태:"
cd /app && python -m alembic current -v || true

echo ""
echo "🔄 마이그레이션 실행:"
cd /app && python -m alembic upgrade head

echo ""
echo "✅ 마이그레이션 완료 상태:"
cd /app && python -m alembic current -v
