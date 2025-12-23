"""create_model_catalog_table

Revision ID: 501d4bbb1a8c
Revises: 054266193b8b
Create Date: 2025-12-23 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "501d4bbb1a8c"
down_revision: Union[str, None] = "054266193b8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """업그레이드 마이그레이션"""
    # model_catalog 테이블 생성
    op.create_table(
        "model_catalog",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "alias",
            sa.String(length=50),
            nullable=False,
            comment="모델 별칭 (gpt-4o-mini, claude-4.5-haiku)",
        ),
        sa.Column(
            "provider",
            sa.String(length=20),
            nullable=False,
            comment="제공자 (openai, anthropic, google, perplexity)",
        ),
        sa.Column(
            "model_name",
            sa.String(length=100),
            nullable=False,
            comment="실제 모델명",
        ),
        sa.Column(
            "model_type",
            sa.String(length=50),
            nullable=False,
            server_default="llm",
            comment="모델 타입 (llm, embedding, search)",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="모델 설명",
        ),
        sa.Column(
            "input_price_per_1m",
            sa.Numeric(10, 4),
            nullable=False,
            comment="입력 토큰 1M당 가격 (USD)",
        ),
        sa.Column(
            "output_price_per_1m",
            sa.Numeric(10, 4),
            nullable=False,
            comment="출력 토큰 1M당 가격 (USD)",
        ),
        sa.Column(
            "input_wtu_multiplier",
            sa.Numeric(6, 2),
            nullable=False,
            server_default="1.00",
            comment="입력 토큰 WTU 가중치 (기준 모델 = 1.00)",
        ),
        sa.Column(
            "output_wtu_multiplier",
            sa.Numeric(6, 2),
            nullable=False,
            server_default="1.00",
            comment="출력 토큰 WTU 가중치 (기준 모델 = 1.00)",
        ),
        sa.Column(
            "max_context_tokens",
            sa.Integer(),
            nullable=False,
            server_default="128000",
            comment="최대 컨텍스트 토큰",
        ),
        sa.Column(
            "tier",
            sa.String(length=20),
            nullable=True,
            comment="LLM 티어 (light, standard, premium, search, embedding)",
        ),
        sa.Column(
            "fallback_priority",
            sa.Integer(),
            nullable=True,
            comment="티어 내 fallback 우선순위 (낮을수록 먼저 시도, null은 fallback 미사용)",
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="기본 모델 여부",
        ),
        sa.Column(
            "is_available",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="사용 가능 여부",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="생성일시",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="수정일시",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alias"),
    )

    # 인덱스 생성
    op.create_index(
        "ix_model_catalog_provider",
        "model_catalog",
        ["provider"],
        unique=False,
    )
    op.create_index(
        "ix_model_catalog_is_available",
        "model_catalog",
        ["is_available"],
        unique=False,
        postgresql_where=sa.text("is_available = true"),
    )
    op.create_index(
        "ix_model_catalog_tier", "model_catalog", ["tier"], unique=False
    )

    # 초기 데이터 삽입
    # WTU 가중치 계산: 기준 모델(claude-4.5-haiku) 대비 가격 비율
    # input_wtu_multiplier = model_input_price / haiku_input_price (1.00)
    # output_wtu_multiplier = model_output_price / haiku_output_price (5.00)

    # 현재 fallback 순서:
    # light: claude-4.5-haiku (1), gemini-2.0-flash (2)
    # standard: gpt-5-mini (1), claude-4.5-sonnet (2)
    # premium: gpt-5.2 (1), claude-4.5-opus (2)
    # search: pplx-70b-online (1), pplx-online-mini (2)
    # embedding: text-embedding-3-large (1)

    op.execute(
        """
        INSERT INTO model_catalog (
            alias, provider, model_name, model_type, description,
            input_price_per_1m, output_price_per_1m,
            input_wtu_multiplier, output_wtu_multiplier,
            max_context_tokens, tier, fallback_priority,
            is_default, is_available
        ) VALUES
        -- Light tier (빠르고 저렴한 모델)
        (
            'claude-4.5-haiku', 'anthropic',
            'claude-haiku-4.5-20250912', 'llm',
            'Claude 4.5 Haiku - 기준 모델',
            1.00, 5.00,
            1.00, 1.00,
            200000, 'light', 1,
            true, true
        ),
        (
            'gemini-2.0-flash', 'google',
            'gemini-2.0-flash-exp', 'llm',
            'Gemini 2.0 Flash - 초고속 모델',
            0.10, 0.30,
            0.10, 0.06,
            1000000, 'light', 2,
            false, true
        ),

        -- Standard tier (중간 성능)
        (
            'gpt-5-mini', 'openai', 'gpt-5-mini', 'llm',
            'GPT-5 Mini - 차세대 GPT 저가 모델',
            0.25, 2.00,
            0.25, 0.40,
            128000, 'standard', 1,
            false, true
        ),
        (
            'claude-4.5-sonnet', 'anthropic',
            'claude-sonnet-4.5-20250201', 'llm',
            'Claude 4.5 Sonnet - 고성능 모델',
            3.00, 15.00,
            3.00, 3.00,
            200000, 'standard', 2,
            false, true
        ),

        -- Premium tier (최고 성능)
        (
            'gpt-5.2', 'openai', 'gpt-5.2', 'llm',
            'GPT-5.2 - 범용 고성능 모델',
            1.75, 14.00,
            1.75, 2.80,
            128000, 'premium', 1,
            false, true
        ),
        (
            'claude-4.5-opus', 'anthropic',
            'claude-opus-4.5-20250201', 'llm',
            'Claude Opus 4.5 - 최고 성능 모델',
            5.00, 25.00,
            5.00, 5.00,
            200000, 'premium', 2,
            false, true
        ),

        -- Embedding tier
        (
            'text-embedding-3-large', 'openai',
            'text-embedding-3-large', 'embedding',
            'OpenAI Embedding - 3072 차원',
            0.13, 0.00,
            1.00, 1.00,
            8191, 'embedding', 1,
            false, true
        )
        """
    )


def downgrade() -> None:
    """다운그레이드 마이그레이션"""
    op.drop_index("ix_model_catalog_tier", table_name="model_catalog")
    op.drop_index("ix_model_catalog_is_available", table_name="model_catalog")
    op.drop_index("ix_model_catalog_provider", table_name="model_catalog")
    op.drop_table("model_catalog")
