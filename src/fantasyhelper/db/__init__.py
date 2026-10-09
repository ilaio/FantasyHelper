"""Shared database connection. Each package creates the tables it owns."""

from fantasyhelper.db.connection import connect, database_path, project_root

__all__ = ["connect", "database_path", "project_root"]
