"""
core app: shared helpers (errors, permissions, health) and the PostgreSQL-only DDL.
Owner: Amina A. (Architecture & Security) / Elza for pg_constraints.
"""
from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        from .pg_constraints import apply_after_migrate
        # Fires once after `migrate`, when every table already exists.
        post_migrate.connect(apply_after_migrate, sender=self)
