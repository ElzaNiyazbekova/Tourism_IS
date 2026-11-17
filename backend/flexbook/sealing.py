"""
Tamper-evident audit log (feature U1).   Owner: Amina A. (Architecture & Security)

The audit log already says who changed what and when. This adds the missing guarantee: "and nobody
changed the log itself". Every audit_log row gets a seal:

        hash_n = SHA-256( hash_(n-1) + this row's content )

so the rows form a chain, like a mini blockchain without the hype. Edit an old row, delete a row from the
middle, or slip one in behind the application's back, and every hash after that point stops matching.
`verify_chain()` walks the chain and reports the FIRST broken link.

Honest limit: someone who can rewrite the whole database AND recompute every hash can still cheat.
Copy the "head hash" (shown on the admin screen) somewhere outside the database from time to time.
"""
import hashlib
import json
from datetime import timezone as dt_timezone

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from bookings.models import AuditLog

from .models import AuditSeal

GENESIS = "GENESIS"


def compute_hash(prev_hash: str, row: AuditLog) -> str:
    payload = json.dumps(
        [prev_hash, row.pk, row.user_id, row.action, row.table_name, row.record_id, row.old_value, row.new_value,
         row.created_at.astimezone(dt_timezone.utc).isoformat()],
        sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def seal_row(audit_id: int) -> AuditSeal:
    """Add the next link. Runs inside the caller's transaction, so row + seal are saved (or rolled back) together."""
    with transaction.atomic():
        # Hash the row exactly as the database stores it (JSON round-trip), not as the caller passed it.
        row = AuditLog.objects.get(pk=audit_id)
        # Row lock on the last seal: two parallel writers queue up instead of forking the chain (ignored by SQLite).
        last = AuditSeal.objects.select_for_update().order_by("-id").first()
        prev = last.hash if last else GENESIS
        return AuditSeal.objects.create(audit=row, prev_hash=prev, hash=compute_hash(prev, row))


@receiver(post_save, sender=AuditLog, dispatch_uid="flexbook_seal_audit_row")
def _seal_new_audit_row(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        seal_row(instance.pk)


def seal_missing() -> int:
    """Back-fill rows written before FlexBook existed (or while it was switched off). Returns how many."""
    n = 0
    for pk in list(AuditLog.objects.filter(seal__isnull=True).order_by("id").values_list("id", flat=True)):
        seal_row(pk)
        n += 1
    return n


def verify_chain() -> dict:
    """Read-only check of the whole chain."""
    prev, sealed, first_break = GENESIS, 0, None
    for seal in AuditSeal.objects.select_related("audit").order_by("id").iterator(chunk_size=500):
        sealed += 1
        if first_break:
            continue
        if seal.prev_hash != prev:
            first_break = {"audit_id": seal.audit_id, "reason": "chain_link"}      # a row/seal before this one vanished
        elif compute_hash(prev, seal.audit) != seal.hash:
            first_break = {"audit_id": seal.audit_id, "reason": "row_modified"}    # this row's content was edited
        prev = seal.hash
    total = AuditLog.objects.count()
    unsealed = AuditLog.objects.filter(seal__isnull=True).count()
    if first_break:
        status = "broken"
    elif unsealed:
        status = "incomplete"     # rows exist that were never sealed -> run `manage.py seal_audit_log`
    else:
        status = "intact"
    return {"status": status, "total_rows": total, "sealed_rows": sealed, "unsealed_rows": unsealed,
            "first_break": first_break, "head_hash": prev if sealed else None}
