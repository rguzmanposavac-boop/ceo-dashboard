#!/usr/bin/env python
import os
import sys
from app.database import Base, engine

def init_db():
    """Create all tables and seed data"""
    try:
        print("Creating tables...")
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created successfully")
        
        print("Seeding data...")
        from app.seed import seed_data
        seed_data()
        print("✅ Data seeded successfully")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_db()