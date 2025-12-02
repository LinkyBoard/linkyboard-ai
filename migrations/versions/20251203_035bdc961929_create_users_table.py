"""create_users_table

Revision ID: 035bdc961929
Revises:
Create Date: 2025-12-03 17:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "035bdc961929"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """업그레이드 마이그레이션: users 테이블 생성"""
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
            autoincrement=False,
            comment="Spring Boot에서 제공하는 사용자 ID",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="생성 일시",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="수정 일시",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="삭제 일시 (Soft Delete)",
        ),
        sa.Column(
            "last_sync_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="마지막 동기화 일시",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Soft Delete를 위한 부분 인덱스 (deleted_at IS NULL인 레코드만 인덱싱)
    op.create_index(
        "idx_users_active",
        "users",
        ["id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """다운그레이드 마이그레이션: users 테이블 삭제"""
    op.drop_index("idx_users_active", table_name="users")
    op.drop_table("users")
