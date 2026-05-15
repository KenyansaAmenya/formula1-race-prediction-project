#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text  # Import at top level

from src.utils.db import get_db
from src.utils.logger import get_logger

logger = get_logger("db_init")


def init_schema():
    db = get_db()
    
    with open("sql/schema_postgres.sql", "r") as f:
        sql = f.read()
    
    try:
        # Execute statements individually for better error handling
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        
        for stmt in statements:
            # Skip comments and empty lines
            clean = '\n'.join(
                line for line in stmt.split('\n')
                if line.strip() and not line.strip().startswith('--')
            )
            if not clean:
                continue
                
            try:
                db.execute_query(clean)
                print(f"✓ Executed: {clean[:60]}...")
            except Exception as e:
                # Some statements may fail if extensions already exist
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"⊘ Skipped (already exists): {clean[:40]}...")
                else:
                    print(f"✗ Error: {str(e)[:80]}")
                    raise
        
        logger.info("schema_initialized_successfully")
        print("\n✅ Database schema initialized successfully")
        
    except Exception as e:
        logger.error("schema_init_failed", error=str(e))
        print(f"\n❌ Schema initialization failed: {e}")
        raise


if __name__ == "__main__":
    init_schema()