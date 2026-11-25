"""Replace the unused Needs review status with Expired. Owner: Elza"""
from django.db import migrations, models
from django.db.models import F, Q


def forwards(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")
    Departure = apps.get_model("catalog", "Departure")
    Payment = apps.get_model("bookings", "Payment")
    AuditLog = apps.get_model("bookings", "AuditLog")

    for booking in Booking.objects.filter(status="Needs review").select_for_update():
        success = Payment.objects.filter(booking_id=booking.pk, status="Success").exists()
        if success:
            booking.status = "Confirmed"
            booking.save(update_fields=["status"])
            reason = "needs_review_removed_confirmed"
            new_value = {"status": "Confirmed", "reason": reason}
        else:
            booking.status = "Expired"
            booking.save(update_fields=["status"])
            Departure.objects.filter(pk=booking.departure_id).update(seats_available=F("seats_available") + booking.travelers_count)
            reason = "needs_review_removed"
            new_value = {"status": "Expired", "reason": reason}
        AuditLog.objects.create(user=None, action="status_change", table_name="bookings", record_id=booking.pk,
                                old_value={"status": "Needs review"}, new_value=new_value)


def backwards(apps, schema_editor):
    # Harmless: no real booking should re-enter the removed status.
    pass


class Migration(migrations.Migration):
    dependencies = [("bookings", "0002_audit_log_indexes")]

    operations = [
        migrations.RemoveConstraint(model_name="booking", name="ck_bookings_status"),
        migrations.RunPython(forwards, backwards),
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.CheckConstraint(condition=Q(status__in=["Pending", "Confirmed", "Cancelled", "Completed", "Expired"]), name="ck_bookings_status"),
        ),
    ]
