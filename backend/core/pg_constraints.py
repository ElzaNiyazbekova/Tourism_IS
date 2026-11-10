"""
Things Django migrations cannot express portably. Idempotent: safe to run after every `migrate`.
Owner: Elza (Data & Database)

 1. The 5 role rows (the system needs them before anyone can register).
 2. PostgreSQL only: btree_gist + EXCLUDE constraint (guide can never overlap = BR-01 / FR-01),
    the full-text GIN index used by /api/search and the analyst_booking_view (aggregates only).
 On SQLite (offline fallback) the same overlap rule is enforced in the service layer
 (catalog.services.assert_no_guide_overlap) and covered by tests.
"""
from django.db import connection

ROLES = ("tourist", "guide", "manager", "analyst", "admin")

ANALYST_VIEW = """
CREATE VIEW analyst_booking_view AS
SELECT p.package_id,
       COALESCE(t.title, '(no English title)')                                          AS package_title,
       COUNT(b.booking_id) FILTER (WHERE b.status IN ('Pending', 'Confirmed'))          AS active_bookings,
       COUNT(b.booking_id) FILTER (WHERE b.status = 'Completed')                        AS completed_bookings,
       COUNT(b.booking_id) FILTER (WHERE b.status = 'Cancelled')                        AS cancelled_bookings,
       COALESCE(SUM(pay.paid), 0)::numeric(12, 2)                                       AS revenue
FROM tour_packages p
LEFT JOIN package_translations t ON t.package_id = p.package_id AND t.language_code = 'en'
LEFT JOIN departures d           ON d.package_id = p.package_id
LEFT JOIN bookings b             ON b.departure_id = d.departure_id
LEFT JOIN (SELECT booking_id, SUM(amount) AS paid FROM payments WHERE status = 'Success' GROUP BY booking_id) pay
                                 ON pay.booking_id = b.booking_id
GROUP BY p.package_id, t.title
"""

PG_STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS btree_gist",
    # BR-01: a guide cannot have two overlapping ACTIVE departures. (An older version of this constraint
    # without "WHERE (is_active)" is replaced.)
    """
    DO $$
    DECLARE def text;
    BEGIN
        SELECT pg_get_constraintdef(oid) INTO def FROM pg_constraint WHERE conname = 'ex_departures_guide_no_overlap';
        IF def IS NOT NULL AND def NOT LIKE '%is_active%' THEN
            ALTER TABLE departures DROP CONSTRAINT ex_departures_guide_no_overlap;
            def := NULL;
        END IF;
        IF def IS NULL THEN
            ALTER TABLE departures ADD CONSTRAINT ex_departures_guide_no_overlap
                EXCLUDE USING gist (guide_id WITH =, tstzrange(start_at, end_at) WITH &&) WHERE (is_active);
        END IF;
    END $$
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_package_translations_fts
        ON package_translations USING gin (to_tsvector('simple', title || ' ' || description))
    """,
    "DROP VIEW IF EXISTS analyst_booking_view",
    ANALYST_VIEW,                       # rule 12: counts and totals only, NO email / phone / names
]


def apply_after_migrate(sender=None, **kwargs):
    if sender is None or sender.label != "bookings":      # run once per `migrate`
        return
    from accounts.models import Role

    for name in ROLES:
        Role.objects.get_or_create(name=name)

    if connection.vendor == "postgresql":
        with connection.cursor() as cur:
            for sql in PG_STATEMENTS:
                cur.execute(sql)
