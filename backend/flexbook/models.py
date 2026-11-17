"""
FlexBook tables.   Owner: Amina A.

audit_seals     one SHA-256 link per audit_log row  -> tamper-evident audit log (feature U1)
seat_transfers  "hand my seat to a friend" offers   -> seat handover (feature U4)

No existing table was changed. Foreign keys use CASCADE (not PROTECT) so that
`manage.py seed_demo` can still wipe bookings / audit_log without extra steps.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q


class AuditSeal(models.Model):
    id = models.AutoField(primary_key=True, db_column="seal_id")
    audit = models.OneToOneField("bookings.AuditLog", on_delete=models.CASCADE, related_name="seal")
    prev_hash = models.CharField(max_length=64)            # hash of the previous seal ("GENESIS" for the first)
    hash = models.CharField(max_length=64, unique=True)    # sha256(prev_hash + the audit row's content)
    sealed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_seals"


class SeatTransfer(models.Model):
    PENDING, ACCEPTED, DECLINED, WITHDRAWN, EXPIRED = "pending", "accepted", "declined", "withdrawn", "expired"
    STATUSES = [PENDING, ACCEPTED, DECLINED, WITHDRAWN, EXPIRED]

    id = models.AutoField(primary_key=True, db_column="transfer_id")
    booking = models.ForeignKey("bookings.Booking", on_delete=models.CASCADE, related_name="transfers")
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="handovers_sent")
    # The sender types an e-mail. We do NOT look the account up at that moment, so the form can never be
    # used to find out which e-mails are registered. The receiver is matched when THEY open "incoming".
    to_email = models.EmailField(max_length=254)
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                                related_name="handovers_received")
    status = models.CharField(max_length=10, default=PENDING)
    message = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "seat_transfers"
        indexes = [models.Index(fields=["to_email", "status"], name="ix_transfers_to_status")]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=["pending", "accepted", "declined", "withdrawn", "expired"]),
                                   name="ck_transfers_status"),
            # one OPEN offer per booking
            models.UniqueConstraint(fields=["booking"], condition=Q(status="pending"), name="uq_transfers_open_per_booking"),
        ]
