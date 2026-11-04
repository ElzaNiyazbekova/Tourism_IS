"""
bookings, payments, notifications, audit_log.   Owner: Elza (Data & Database)

Governance rule (Task 7): bookings are created ONLY by bookings.services.create_booking,
which also generates booking_ref. Tourists never type a ref, a status or a price.
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Booking(models.Model):
    PENDING, CONFIRMED, CANCELLED, COMPLETED, NEEDS_REVIEW = "Pending", "Confirmed", "Cancelled", "Completed", "Needs review"
    STATUSES = [PENDING, CONFIRMED, CANCELLED, COMPLETED, NEEDS_REVIEW]
    ACTIVE = [PENDING, CONFIRMED]          # statuses that hold a seat and block a duplicate

    id = models.AutoField(primary_key=True, db_column="booking_id")
    booking_ref = models.CharField(max_length=12, unique=True)                  # "BK-0001", system only
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings", db_index=False)
    departure = models.ForeignKey("catalog.Departure", on_delete=models.PROTECT, related_name="bookings", db_index=False)
    booking_date = models.DateField()
    travel_date = models.DateField()
    travelers_count = models.IntegerField()
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)           # frozen at booking time
    status = models.CharField(max_length=20, default=PENDING)
    special_request = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)                    # Pending: created_at + 48 h

    class Meta:
        db_table = "bookings"
        indexes = [
            models.Index(fields=["user"], name="ix_bookings_user"),
            models.Index(fields=["departure"], name="ix_bookings_departure"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(travel_date__gte=F("booking_date")), name="ck_bookings_dates"),
            models.CheckConstraint(condition=Q(travelers_count__gt=0), name="ck_bookings_travelers"),
            models.CheckConstraint(condition=Q(total_cost__gte=0), name="ck_bookings_cost"),
            models.CheckConstraint(
                condition=Q(status__in=["Pending", "Confirmed", "Cancelled", "Completed", "Needs review"]),
                name="ck_bookings_status"),
            # rule 4: one ACTIVE booking per tourist per departure
            models.UniqueConstraint(fields=["user", "departure"], condition=Q(status__in=["Pending", "Confirmed"]),
                                    name="uq_bookings_active_user_departure"),
        ]

    def __str__(self):
        return self.booking_ref


class Payment(models.Model):
    SUCCESS, FAILED = "Success", "Failed"

    id = models.AutoField(primary_key=True, db_column="payment_id")
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10)
    transaction_ref = models.CharField(max_length=40, unique=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments"
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="ck_payments_amount"),
            models.CheckConstraint(condition=Q(status__in=["Success", "Failed"]), name="ck_payments_status"),
        ]


class Notification(models.Model):
    id = models.AutoField(primary_key=True, db_column="notification_id")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="notifications", db_index=False)
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, null=True, blank=True, related_name="notifications")
    type = models.CharField(max_length=30)             # created / confirmed / cancelled / expired
    message_key = models.CharField(max_length=100)     # translated by the frontend
    params = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        indexes = [models.Index(fields=["user", "is_read"], name="ix_notifications_user_read")]


class AuditLog(models.Model):
    id = models.AutoField(primary_key=True, db_column="audit_id")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="audit_entries")
    action = models.CharField(max_length=30)           # create / update / status_change / ...
    table_name = models.CharField(max_length=60)
    record_id = models.IntegerField(null=True, blank=True)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        indexes = [models.Index(fields=["table_name", "record_id"], name="ix_audit_table_record")]
