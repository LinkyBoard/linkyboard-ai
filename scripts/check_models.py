#!/usr/bin/env python3
"""
Dev 데이터베이스의 모델 정보를 확인하고 Prod에 복제하는 스크립트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import Settings
from app.core.models import ModelCatalog
import json
from typing import List, Dict, Any

def get_dev_models() -> List[Dict[str, Any]]:
    """Dev 데이터베이스에서 모델 정보를 조회"""
    
    # Dev 데이터베이스 설정
    dev_settings = Settings()
    dev_engine = create_engine(dev_settings.sync_database_url)
    
    with dev_engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, model_name, alias, provider, model_type, role_mask, status, version,
                   price_input, price_output, price_embedding, 
                   weight_input, weight_output, weight_embedding,
                   reference_model, reference_price_input, reference_price_output,
                   cached_factor, embedding_alpha, is_active
            FROM model_catalog 
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
        
        return models

def display_models(models: List[Dict[str, Any]]):
    """모델 정보 표시"""
    print("=== AI 모델 정보 ===")
    for i, model in enumerate(models, 1):
        print(f"{i}. {model['alias']} ({model['model_name']})")
        print(f"   Provider: {model['provider']}")
        print(f"   Type: {model['model_type']}")
        print(f"   Status: {model['status']}")
        print(f"   Role Mask: {model['role_mask']}")
        if model['price_input']:
            print(f"   Price Input: ${model['price_input']}/1M tokens")
        if model['price_output']:
            print(f"   Price Output: ${model['price_output']}/1M tokens")
        if model['price_embedding']:
            print(f"   Price Embedding: ${model['price_embedding']}/1M tokens")
        print(f"   Active: {model['is_active']}")
        print()

def save_models_to_file(models: List[Dict[str, Any]], filename: str = "model_catalog_data.json"):
    """모델 정보를 JSON 파일로 저장"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(models, f, ensure_ascii=False, indent=2, default=str)
    print(f"모델 데이터가 {filename}에 저장되었습니다.")

def main():
    try:
        # Dev 데이터베이스에서 모델 정보 조회
        print("Dev 데이터베이스에서 모델 정보를 조회 중...")
        models = get_dev_models()
        
        if not models:
            print("Dev 데이터베이스에 모델 정보가 없습니다.")
            return
        
        # 모델 정보 표시
        display_models(models)
        
        # 파일로 저장
        save_models_to_file(models)
        
        print(f"총 {len(models)}개의 모델 정보를 확인했습니다.")
        
    except Exception as e:
        print(f"오류 발생: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()
