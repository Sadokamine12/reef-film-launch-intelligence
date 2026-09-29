from reef import models  # noqa: F401 - registers all migration tables
from alembic import context
from reef.db import Base, engine

with engine().connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
