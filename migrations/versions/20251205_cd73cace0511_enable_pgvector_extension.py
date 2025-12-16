"""enable_pgvector_extension

Revision ID: cd73cace0511
Revises: 684968767c83
Create Date: 2025-12-05 00:06:37.278423

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "cd73cace0511"
down_revision: Union[str, None] = "684968767c83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """업그레이드 마이그레이션"""
    # pgvector 확장 설치 (벡터 연산 지원)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """다운그레이드 마이그레이션"""
    # pgvector 확장 제거
    op.execute("DROP EXTENSION IF EXISTS vector")
