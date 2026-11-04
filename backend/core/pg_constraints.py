"""
Things Django migrations cannot express portably. Idempotent: safe to run after every `migrate`.
Owner: Elza (Data & Database)

 1. The 5 role rows (the system needs them before anyone can register).
 2. PostgreSQL only: btree_gist + EXCLUDE constraint (guide can never overlap = BR-01 / FR-01)
    and the full-text GIN index used by /api/search.
 On SQLite (offline fallback) the same overlap rule is enforced in the service layer
 (catalog.services.assert_no_guide_overlap) and covered by tests.
"""
from django.db import connection

ROLES = ("tourist", "guide", "manager", "analyst", "admin")

PG_STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS btree_gist",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ex_departures_guide_no_overlap') THEN
            ALTER TABLE departures ADD CONSTRAINT ex_departures_guide_no_overlap
                EXCLUDE USING gist (guide_id WITH =, tstzrange(start_at, end_at) WITH &&);
        END IF;
    END $$
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_package_translations_fts
        ON package_translations USING gin (to_tsvector('simple', title || ' ' || description))
    """,
]


def apply_after_migrate(sender=None, **kwargs):
    from accounts.models import Role

    for name in ROLES:
        Role.objects.get_or_create(name=name)

    if connection.vendor == "postgresql":
        with connection.cursor() as cur:
            for sql in PG_STATEMENTS:
                cur.execute(sql)
