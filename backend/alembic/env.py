from logging.config import fileConfig
import os
import sys

from alembic import context
from sqlalchemy import create_engine, pool

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import get_settings
from app.db.base import Base
# Import all models to ensure they are registered with Base.metadata
from app.models import *  # noqa: F401, F403

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Retrieve database URL dynamically from application settings."""
    settings = get_settings()
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_url()

    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        context_opts = {
            "connection": connection,
            "target_metadata": target_metadata,
            "compare_type": not is_sqlite,
        }
        if is_sqlite:
            context_opts["render_as_batch"] = True

        context.configure(**context_opts)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
