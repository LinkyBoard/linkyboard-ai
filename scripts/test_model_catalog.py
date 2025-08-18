#!/usr/bin/env python3
"""
AI 모델 카탈로그 관리 시스템 테스트 스크립트
"""
import sys
import os
import tempfile
import json
from typing import List, Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.models import ModelCatalog
from app.core.model_catalog_init import init_model_catalog, ensure_model_catalog_initialized

def test_model_catalog_management():
    """모델 카탈로그 관리 기능 테스트"""
    print("🧪 AI 모델 카탈로그 관리 시스템 테스트 시작")
    
    # 임시 SQLite 데이터베이스 생성 (테스트용)
    test_db_path = tempfile.mktemp(suffix='.db')
    test_db_url = f"sqlite:///{test_db_path}"
    
    try:
        # 테스트 데이터베이스 엔진 생성
        engine = create_engine(test_db_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # 테이블 생성
        from app.core.models import Base
        Base.metadata.create_all(bind=engine)
        
        with SessionLocal() as session:
            # 1. 초기 상태 확인
            print("1️⃣ 초기 모델 수 확인...")
            initial_count = session.query(ModelCatalog).count()
            assert initial_count == 0, f"초기 모델 수가 0이어야 하는데 {initial_count}개입니다."
            print("   ✅ 초기 상태 확인 완료")
            
            # 2. 초기 데이터 삽입 테스트
            print("2️⃣ 초기 모델 데이터 삽입 테스트...")
            result = init_model_catalog(session)
            assert result == True, "초기 데이터 삽입이 실패했습니다."
            
            # 3. 삽입된 데이터 확인
            models = session.query(ModelCatalog).all()
            assert len(models) == 2, f"2개의 모델이 삽입되어야 하는데 {len(models)}개입니다."
            
            # 각 모델 타입 확인
            llm_models = [m for m in models if m.model_type == 'llm']
            embedding_models = [m for m in models if m.model_type == 'embedding']
            
            assert len(llm_models) == 1, f"LLM 모델이 1개여야 하는데 {len(llm_models)}개입니다."
            assert len(embedding_models) == 1, f"Embedding 모델이 1개여야 하는데 {len(embedding_models)}개입니다."
            
            print("   ✅ 초기 데이터 삽입 완료")
            
            # 4. 중복 삽입 방지 테스트
            print("3️⃣ 중복 삽입 방지 테스트...")
            result = init_model_catalog(session)
            assert result == False, "중복 삽입이 방지되어야 합니다."
            
            final_count = session.query(ModelCatalog).count()
            assert final_count == 2, f"모델 수가 2개여야 하는데 {final_count}개입니다."
            print("   ✅ 중복 삽입 방지 확인 완료")
            
            # 5. ensure_model_catalog_initialized 테스트
            print("4️⃣ 자동 초기화 기능 테스트...")
            ensure_model_catalog_initialized(session)
            
            final_count_2 = session.query(ModelCatalog).count()
            assert final_count_2 == 2, f"자동 초기화 후 모델 수가 2개여야 하는데 {final_count_2}개입니다."
            print("   ✅ 자동 초기화 기능 확인 완료")
            
            # 6. 모델 정보 상세 확인
            print("5️⃣ 모델 정보 상세 확인...")
            
            gpt_model = session.query(ModelCatalog).filter(
                ModelCatalog.model_name == 'gpt-4o-mini'
            ).first()
            
            assert gpt_model is not None, "GPT-4o Mini 모델을 찾을 수 없습니다."
            assert gpt_model.price_input == 0.15, f"GPT 입력 가격이 0.15여야 하는데 {gpt_model.price_input}입니다."
            assert gpt_model.weight_input == 0.6, f"GPT 입력 가중치가 0.6이어야 하는데 {gpt_model.weight_input}입니다."
            
            embedding_model = session.query(ModelCatalog).filter(
                ModelCatalog.model_name == 'text-embedding-3-small'
            ).first()
            
            assert embedding_model is not None, "Embedding 모델을 찾을 수 없습니다."
            assert embedding_model.price_embedding == 0.02, f"Embedding 가격이 0.02여야 하는데 {embedding_model.price_embedding}입니다."
            assert embedding_model.weight_embedding == 0.064, f"Embedding 가중치가 0.064여야 하는데 {embedding_model.weight_embedding}입니다."
            
            print("   ✅ 모델 정보 상세 확인 완료")
        
        print("\n🎉 모든 테스트가 성공적으로 완료되었습니다!")
        return True
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        return False
        
    finally:
        # 임시 파일 정리
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

def test_json_data_format():
    """JSON 데이터 형식 테스트"""
    print("\n🧪 JSON 데이터 형식 테스트")
    
    try:
        # model_catalog_data.json 파일 확인
        json_file = "model_catalog_data.json"
        if not os.path.exists(json_file):
            print(f"❌ {json_file} 파일이 없습니다.")
            return False
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert isinstance(data, list), "JSON 데이터는 리스트여야 합니다."
        assert len(data) >= 2, f"최소 2개의 모델이 있어야 하는데 {len(data)}개입니다."
        
        # 각 모델 데이터 구조 확인
        required_fields = [
            'model_name', 'alias', 'provider', 'model_type', 'role_mask',
            'status', 'reference_model', 'reference_price_input',
            'reference_price_output', 'cached_factor', 'embedding_alpha',
            'is_active'
        ]
        
        for i, model in enumerate(data):
            for field in required_fields:
                assert field in model, f"모델 {i}에 필수 필드 '{field}'가 없습니다."
        
        print("   ✅ JSON 데이터 형식 확인 완료")
        return True
        
    except Exception as e:
        print(f"   ❌ JSON 데이터 형식 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 실행"""
    print("=" * 60)
    print("🤖 LinkyBoard AI 모델 카탈로그 관리 시스템 테스트")
    print("=" * 60)
    
    success_count = 0
    total_tests = 2
    
    # 테스트 실행
    if test_model_catalog_management():
        success_count += 1
    
    if test_json_data_format():
        success_count += 1
    
    # 결과 출력
    print("\n" + "=" * 60)
    print(f"📊 테스트 결과: {success_count}/{total_tests} 성공")
    
    if success_count == total_tests:
        print("🎉 모든 테스트가 성공했습니다!")
        return True
    else:
        print("❌ 일부 테스트가 실패했습니다.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
