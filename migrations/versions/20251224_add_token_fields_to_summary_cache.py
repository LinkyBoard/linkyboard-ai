"""add_token_fields_to_summary_cache

Revision ID: a1b2c3d4e5f6
Revises: 501d4bbb1a8c
Create Date: 2025-12-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "501d4bbb1a8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add total_input_tokens and total_output_tokens to summary_cache"""
    op.add_column(
        "summary_cache",
        sa.Column(
            "total_input_tokens",
            sa.Integer(),
            nullable=True,
            comment="원본 생성 시 사용된 총 입력 토큰",
        ),
    )
    op.add_column(
        "summary_cache",
        sa.Column(
            "total_output_tokens",
            sa.Integer(),
            nullable=True,
            comment="원본 생성 시 사용된 총 출력 토큰",
        ),
    )


def downgrade() -> None:
    """Remove total_input_tokens and total_output_tokens from summary_cache"""
    op.drop_column("summary_cache", "total_output_tokens")
    op.drop_column("summary_cache", "total_input_tokens")
