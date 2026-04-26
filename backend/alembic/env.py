import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importar todos los modelos para que autogenerate los detecte
from app.database import Base  # noqa: F401
import app.models.stock       # noqa: F401
import app.models.ceo         # noqa: F401
import app.models.catalyst    # noqa: F401
import app.models.score       # noqa: F401
import app.models.regime      # noqa: F401

target_metadata = Base.metadata


def get_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://admin:dashboard2026@localhost:5432/ceo_dashboard",
    )


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
