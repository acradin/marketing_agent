from alembic import context
from packages.core.config import Settings
from packages.core.database import database
from packages.core.models import Base

engine, _ = database(Settings().database_url)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
