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
        # post_migrate is only sent for apps that HAVE models, and this app (core) has none, so we hook the
        # signal for every app and let the handler act once, for "bookings" (the last app): by then every
        # table exists.
        post_migrate.connect(apply_after_migrate, dispatch_uid="tourism_pg_constraints")
