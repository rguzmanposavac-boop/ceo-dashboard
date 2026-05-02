import os
import sys
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command

def run_migrations():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set in env, skipping migrations")
        return

    # Handle postgres:// to postgresql:// migration for SQLAlchemy
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    print("Connecting to database...")
    engine = create_engine(url)
    inspector = inspect(engine)
    
    alembic_cfg = Config("alembic.ini")
    # Make sure we use the same DB url in alembic
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    
    has_alembic = inspector.has_table("alembic_version")
    
    with engine.connect() as conn:
        if not has_alembic and inspector.has_table("catalysts"):
            print("Database has tables but no alembic_version. Stamping schema based on columns...")
            columns = [c["name"] for c in inspector.get_columns("catalysts")]
            
            if "discount_pct" in columns:
                print("Stamping head (discount_pct exists)")
                command.stamp(alembic_cfg, "head")
            elif "last_reviewed" in columns:
                print("Stamping 0004 and upgrading to head")
                command.stamp(alembic_cfg, "0004")
                command.upgrade(alembic_cfg, "head")
            else:
                if inspector.has_table("price_history"):
                    print("Stamping 0003 and upgrading to head")
                    command.stamp(alembic_cfg, "0003")
                elif inspector.has_table("refresh_config"):
                    print("Stamping 0002 and upgrading to head")
                    command.stamp(alembic_cfg, "0002")
                else:
                    print("Stamping 0001 and upgrading to head")
                    command.stamp(alembic_cfg, "0001")
                command.upgrade(alembic_cfg, "head")
        else:
            print("Running normal alembic upgrade...")
            command.upgrade(alembic_cfg, "head")
            
    print("Migrations complete.")

if __name__ == "__main__":
    run_migrations()
