#!/usr/bin/env python3
"""Add review_mode column to invoices table"""

import os
import sys

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.database import engine
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

def migrate():
    print("Adding review_mode column to invoices table...")
    
    with engine.connect() as conn:
        try:
            # Check if column exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='invoices' AND column_name='review_mode'
            """))
            
            if result.fetchone():
                print("✓ Column 'review_mode' already exists")
                return
            
            # Add the column
            conn.execute(text("""
                ALTER TABLE invoices 
                ADD COLUMN review_mode VARCHAR(50) DEFAULT 'direct'
            """))
            
            # Update existing rows
            conn.execute(text("""
                UPDATE invoices SET review_mode = 'direct' WHERE review_mode IS NULL
            """))
            
            conn.commit()
            print("✓ Migration complete: review_mode column added")
            
        except ProgrammingError as e:
            print(f"✗ Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate()