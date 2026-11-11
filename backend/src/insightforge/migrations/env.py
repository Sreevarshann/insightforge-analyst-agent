from __future__ import annotations

from alembic import context

from insightforge.db.models import Base

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Migrations must be run via insightforge.db.session.run_migrations")

context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
with context.begin_transaction():
    context.run_migrations()
