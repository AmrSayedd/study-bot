import os

if os.environ.get("DATABASE_URL"):
    from .db_postgres import Database
else:
    from .db_sqlite import Database

__all__ = ["Database"]
