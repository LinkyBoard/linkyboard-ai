#!/usr/bin/env python3
"""
AI 모델 카탈로그 데이터를 prod 데이터베이스에 복제하거나 새 데이터베이스에 초기 설정하는 스크립트
"""
import sys
import os
import json
import argparse
from typing import List, Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.models import ModelCatalog
from datetime import datetime

# 초기 모델 데이터
INITIAL_MODEL_DATA = [
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

def insert_models_to_database(database_url: str, models_data: List[Dict[str, Any]]):
    """데이터베이스에 모델 데이터 삽입"""
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    with SessionLocal() as session:
        try:
            inserted_count = 0
            updated_count = 0
            
            for model_data in models_data:
                # 기존 모델 확인
                existing_model = session.query(ModelCatalog).filter(
                    ModelCatalog.model_name == model_data['model_name']
                ).first()
                
                if existing_model:
                    # 업데이트
                    for key, value in model_data.items():
                        if hasattr(existing_model, key):
                            setattr(existing_model, key, value)
                    existing_model.updated_at = datetime.utcnow()
                    updated_count += 1
                    print(f"업데이트: {model_data['alias']} ({model_data['model_name']})")
                else:
                    # 새로 삽입
                    new_model = ModelCatalog(**model_data)
                    session.add(new_model)
                    inserted_count += 1
                    print(f"삽입: {model_data['alias']} ({model_data['model_name']})")
            
            session.commit()
            print(f"\n성공적으로 완료되었습니다:")
            print(f"- 새로 삽입: {inserted_count}개")
            print(f"- 업데이트: {updated_count}개")
            
        except Exception as e:
            session.rollback()
            print(f"오류 발생: {e}")
            raise

def load_models_from_file(filename: str) -> List[Dict[str, Any]]:
    """JSON 파일에서 모델 데이터 로드"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {filename}")
        return []
    except json.JSONDecodeError as e:
        print(f"JSON 파일 파싱 오류: {e}")
        return []

def setup_initial_models(database_url: str):
    """새 데이터베이스에 초기 모델 설정"""
    print("초기 AI 모델 데이터를 설정합니다...")
    insert_models_to_database(database_url, INITIAL_MODEL_DATA)

def sync_models_from_dev(dev_database_url: str, target_database_url: str):
    """Dev 데이터베이스에서 Target 데이터베이스로 모델 동기화"""
    print("Dev 데이터베이스에서 모델 정보를 가져옵니다...")
    
    dev_engine = create_engine(dev_database_url)
    with dev_engine.connect() as conn:
        result = conn.execute(text("""
            SELECT model_name, alias, provider, model_type, role_mask, status, version,
                   price_input, price_output, price_embedding, 
                   weight_input, weight_output, weight_embedding,
                   reference_model, reference_price_input, reference_price_output,
                   cached_factor, embedding_alpha, is_active
            FROM model_catalog 
            WHERE is_active = true
            ORDER BY id
        """))
        
        models = []
        for row in result:
            model_data = {
                'model_name': row.model_name,
                'alias': row.alias,
                'provider': row.provider,
                'model_type': row.model_type,
                'role_mask': row.role_mask,
                'status': row.status,
                'version': row.version,
                'price_input': row.price_input,
                'price_output': row.price_output,
                'price_embedding': row.price_embedding,
                'weight_input': row.weight_input,
                'weight_output': row.weight_output,
                'weight_embedding': row.weight_embedding,
                'reference_model': row.reference_model,
                'reference_price_input': row.reference_price_input,
                'reference_price_output': row.reference_price_output,
                'cached_factor': row.cached_factor,
                'embedding_alpha': row.embedding_alpha,
                'is_active': row.is_active
            }
            models.append(model_data)
    
    if models:
        print(f"{len(models)}개의 모델을 대상 데이터베이스에 복제합니다...")
        insert_models_to_database(target_database_url, models)
    else:
        print("Dev 데이터베이스에서 활성 모델을 찾지 못했습니다.")

def main():
    parser = argparse.ArgumentParser(description='AI 모델 카탈로그 데이터 관리')
    parser.add_argument('--action', choices=['init', 'sync', 'from-file'], required=True,
                       help='수행할 작업 (init: 초기 설정, sync: dev에서 동기화, from-file: 파일에서 로드)')
    parser.add_argument('--database-url', required=True,
                       help='대상 데이터베이스 URL')
    parser.add_argument('--dev-database-url',
                       help='Dev 데이터베이스 URL (sync 작업 시 필요)')
    parser.add_argument('--file',
                       help='모델 데이터 JSON 파일 경로 (from-file 작업 시 필요)')
    
    args = parser.parse_args()
    
    try:
        if args.action == 'init':
            setup_initial_models(args.database_url)
        
        elif args.action == 'sync':
            if not args.dev_database_url:
                print("sync 작업에는 --dev-database-url이 필요합니다.")
                return False
            sync_models_from_dev(args.dev_database_url, args.database_url)
        
        elif args.action == 'from-file':
            if not args.file:
                print("from-file 작업에는 --file이 필요합니다.")
                return False
            models = load_models_from_file(args.file)
            if models:
                insert_models_to_database(args.database_url, models)
        
        return True
        
    except Exception as e:
        print(f"작업 실행 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
