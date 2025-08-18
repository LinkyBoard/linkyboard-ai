"""insert_initial_model_catalog_data

Revision ID: initial_model_data
Revises: cac7a9e5064a
Create Date: 2025-08-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c6715b5101f'
down_revision: Union[str, None] = 'cac7a9e5064a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Insert initial model catalog data."""
    # model_catalog 테이블에 초기 데이터 삽입
    models_data = [
        {
            'model_name': 'text-embedding-3-small',
            'alias': 'Text Embedding 3 Small',
            'provider': 'openai',
            'model_type': 'embedding',
            'role_mask': 2,
            'status': 'active',
            'version': None,
            'price_input': None,
            'price_output': None,
            'price_embedding': 0.02,
            'weight_input': None,
            'weight_output': None,
            'weight_embedding': 0.064,
            'reference_model': 'gpt-5-mini',
            'reference_price_input': 0.25,
            'reference_price_output': 2.0,
            'cached_factor': 0.1,
            'embedding_alpha': 0.8,
            'is_active': True
        },
        {
            'model_name': 'gpt-4o-mini',
            'alias': 'GPT-4o Mini',
            'provider': 'openai',
            'model_type': 'llm',
            'role_mask': 1,
            'status': 'active',
            'version': '2024-07-18',
            'price_input': 0.15,
            'price_output': 0.6,
            'price_embedding': None,
            'weight_input': 0.6,
            'weight_output': 2.4,
            'weight_embedding': None,
            'reference_model': 'gpt-5-mini',
            'reference_price_input': 0.25,
            'reference_price_output': 2.0,
            'cached_factor': 0.1,
            'embedding_alpha': 0.8,
            'is_active': True
        }
    ]
    
    # 데이터 삽입 (중복 방지를 위해 ON CONFLICT 사용)
    for model_data in models_data:
        op.execute(f"""
            INSERT INTO model_catalog 
            (model_name, alias, provider, model_type, role_mask, status, version,
             price_input, price_output, price_embedding, 
             weight_input, weight_output, weight_embedding,
             reference_model, reference_price_input, reference_price_output,
             cached_factor, embedding_alpha, is_active, created_at)
            VALUES 
            ('{model_data['model_name']}', 
             '{model_data['alias']}', 
             '{model_data['provider']}', 
             '{model_data['model_type']}', 
             {model_data['role_mask']}, 
             '{model_data['status']}', 
             {f"'{model_data['version']}'" if model_data['version'] else 'NULL'},
             {model_data['price_input'] if model_data['price_input'] else 'NULL'},
             {model_data['price_output'] if model_data['price_output'] else 'NULL'},
             {model_data['price_embedding'] if model_data['price_embedding'] else 'NULL'},
             {model_data['weight_input'] if model_data['weight_input'] else 'NULL'},
             {model_data['weight_output'] if model_data['weight_output'] else 'NULL'},
             {model_data['weight_embedding'] if model_data['weight_embedding'] else 'NULL'},
             '{model_data['reference_model']}',
             {model_data['reference_price_input']},
             {model_data['reference_price_output']},
             {model_data['cached_factor']},
             {model_data['embedding_alpha']},
             {model_data['is_active']},
             NOW())
            ON CONFLICT (model_name) DO UPDATE SET
                alias = EXCLUDED.alias,
                provider = EXCLUDED.provider,
                model_type = EXCLUDED.model_type,
                role_mask = EXCLUDED.role_mask,
                status = EXCLUDED.status,
                version = EXCLUDED.version,
                price_input = EXCLUDED.price_input,
                price_output = EXCLUDED.price_output,
                price_embedding = EXCLUDED.price_embedding,
                weight_input = EXCLUDED.weight_input,
                weight_output = EXCLUDED.weight_output,
                weight_embedding = EXCLUDED.weight_embedding,
                reference_model = EXCLUDED.reference_model,
                reference_price_input = EXCLUDED.reference_price_input,
                reference_price_output = EXCLUDED.reference_price_output,
                cached_factor = EXCLUDED.cached_factor,
                embedding_alpha = EXCLUDED.embedding_alpha,
                is_active = EXCLUDED.is_active,
                updated_at = NOW()
        """)


def downgrade() -> None:
    """Remove initial model catalog data."""
    op.execute("DELETE FROM model_catalog WHERE model_name IN ('text-embedding-3-small', 'gpt-4o-mini')")
