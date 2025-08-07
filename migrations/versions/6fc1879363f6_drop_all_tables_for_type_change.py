"""Drop all tables for type change

Revision ID: 6fc1879363f6
Revises: 40c23c4857f2
Create Date: 2025-08-07 21:45:47.717164

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
# pgvector 관련 import (필요시)
# import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '6fc1879363f6'
down_revision: Union[str, Sequence[str], None] = '40c23c4857f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('search_histories')
    op.drop_table('item_tags') 
    op.drop_table('items')
    op.drop_table('users')


def downgrade() -> None:
    """Downgrade schema."""
    pass
