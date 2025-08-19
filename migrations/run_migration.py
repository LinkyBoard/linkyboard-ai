#!/usr/bin/env python3
"""
Database Migration Runner
보드 관리 테이블 마이그레이션 실행 스크립트
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import AsyncSessionLocal, engine
from app.core.logging import get_logger
from sqlalchemy import text

logger = get_logger(__name__)


async def run_migration():
    """마이그레이션 실행"""
    try:
        migration_file = Path(__file__).parent / "add_board_management_tables.sql"
        
        if not migration_file.exists():
            raise FileNotFoundError(f"Migration file not found: {migration_file}")
        
        # SQL 파일 읽기
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        logger.info("Starting board management tables migration...")
        
        # 마이그레이션 실행
        async with AsyncSessionLocal() as session:
            # SQL을 세미콜론으로 분할하여 개별 실행
            statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
            
            for i, statement in enumerate(statements, 1):
                try:
                    if statement.strip():
                        logger.debug(f"Executing statement {i}/{len(statements)}")
                        await session.execute(text(statement))
                        
                except Exception as e:
                    # 이미 존재하는 객체에 대한 에러는 무시 (CREATE IF NOT EXISTS 등)
                    if "already exists" in str(e).lower():
                        logger.debug(f"Object already exists (statement {i}): {str(e)}")
                        continue
                    else:
                        logger.error(f"Error executing statement {i}: {str(e)}")
                        logger.error(f"Statement: {statement[:100]}...")
                        raise
            
            await session.commit()
            logger.info("Migration completed successfully!")
            
            # 테이블 생성 확인
            tables_check = await session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('boards', 'board_items', 'board_analytics', 'board_recommendation_cache')
                ORDER BY table_name
            """))
            
            created_tables = [row[0] for row in tables_check.fetchall()]
            logger.info(f"Created tables: {created_tables}")
            
            return True
            
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        return False


async def check_migration_status():
    """마이그레이션 상태 확인"""
    try:
        async with AsyncSessionLocal() as session:
            # 테이블 존재 확인
            tables_check = await session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('boards', 'board_items', 'board_analytics', 'board_recommendation_cache')
                ORDER BY table_name
            """))
            
            existing_tables = [row[0] for row in tables_check.fetchall()]
            required_tables = ['boards', 'board_items', 'board_analytics', 'board_recommendation_cache']
            
            logger.info(f"Required tables: {required_tables}")
            logger.info(f"Existing tables: {existing_tables}")
            
            missing_tables = set(required_tables) - set(existing_tables)
            
            if missing_tables:
                logger.warning(f"Missing tables: {missing_tables}")
                return False
            else:
                logger.info("All required tables exist!")
                
                # 인덱스 확인
                indexes_check = await session.execute(text("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE schemaname = 'public' 
                    AND indexname LIKE 'idx_board%'
                    ORDER BY indexname
                """))
                
                existing_indexes = [row[0] for row in indexes_check.fetchall()]
                logger.info(f"Board-related indexes: {existing_indexes}")
                
                return True
                
    except Exception as e:
        logger.error(f"Failed to check migration status: {str(e)}")
        return False


async def main():
    """메인 함수"""
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        # 상태 확인만 실행
        await check_migration_status()
    else:
        # 마이그레이션 실행
        success = await run_migration()
        if success:
            logger.info("✅ Board management tables migration completed!")
        else:
            logger.error("❌ Migration failed!")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())