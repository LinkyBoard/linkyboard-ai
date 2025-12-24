"""create_model_call_logs_table

Revision ID: 75c84fb65635
Revises: a1b2c3d4e5f6
Create Date: 2025-12-24 10:03:35.748587

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "75c84fb65635"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """업그레이드 마이그레이션: model_call_logs 테이블 생성"""
    op.create_table(
        "model_call_logs",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
            comment="로그 ID",
        ),
        sa.Column(
            "model_alias",
            sa.String(length=50),
            nullable=False,
            comment="시도한 모델 별칭",
        ),
        sa.Column(
            "tier",
            sa.String(length=20),
            nullable=False,
            comment="LLM 티어 (light, standard, premium, search, embedding)",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            comment="호출 상태 (success, failed, fallback)",
        ),
        sa.Column(
            "error_type",
            sa.String(length=100),
            nullable=True,
            comment="에러 타입 (RateLimitError, InsufficientCredits, etc)",
        ),
        sa.Column("error_message", sa.Text(), nullable=True, comment="에러 메시지"),
        sa.Column(
            "fallback_to",
            sa.String(length=50),
            nullable=True,
            comment="Fallback된 모델 별칭 (fallback 발생 시)",
        ),
        sa.Column(
            "input_tokens", sa.Integer(), nullable=True, comment="입력 토큰 수"
        ),
        sa.Column(
            "output_tokens", sa.Integer(), nullable=True, comment="출력 토큰 수"
        ),
        sa.Column(
            "response_time_ms",
            sa.Integer(),
            nullable=True,
            comment="응답 시간 (밀리초)",
        ),
        sa.Column(
            "request_metadata",
            JSONB(),
            nullable=True,
            comment="요청 메타데이터 (user_id, api_endpoint, etc)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="호출 일시",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 인덱스 생성
    op.create_index(
        "ix_model_call_logs_model_alias", "model_call_logs", ["model_alias"]
    )
    op.create_index("ix_model_call_logs_tier", "model_call_logs", ["tier"])
    op.create_index("ix_model_call_logs_status", "model_call_logs", ["status"])
    op.create_index(
        "ix_model_call_logs_error_type", "model_call_logs", ["error_type"]
    )
    op.create_index(
        "ix_model_call_logs_created_at", "model_call_logs", ["created_at"]
    )


def downgrade() -> None:
    """다운그레이드 마이그레이션: model_call_logs 테이블 삭제"""
    op.drop_index(
        "ix_model_call_logs_created_at", table_name="model_call_logs"
    )
    op.drop_index(
        "ix_model_call_logs_error_type", table_name="model_call_logs"
    )
    op.drop_index("ix_model_call_logs_status", table_name="model_call_logs")
    op.drop_index("ix_model_call_logs_tier", table_name="model_call_logs")
    op.drop_index(
        "ix_model_call_logs_model_alias", table_name="model_call_logs"
    )
    op.drop_table("model_call_logs")
