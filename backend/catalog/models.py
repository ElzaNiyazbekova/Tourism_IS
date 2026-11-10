"""
destinations, tour_packages, package_translations, departures, reviews.
Owner: Elza (Data & Database)

Departure = one package + one guide at a fixed start_at/end_at with seats_total
(seats_total = 1 means a private guided tour).
The "guide cannot overlap" EXCLUDE constraint lives in core/pg_constraints.py (PostgreSQL),
and in catalog/services.py for the SQLite fallback.
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Destination(models.Model):
    id = models.AutoField(primary_key=True, db_column="destination_id")
    name = models.CharField(max_length=120)
    country = models.CharField(max_length=80)

    class Meta:
        db_table = "destinations"
        constraints = [models.UniqueConstraint(fields=["name", "country"], name="uq_destinations_name_country")]

    def __str__(self):
        return f"{self.name}, {self.country}"


class TourPackage(models.Model):
    id = models.AutoField(primary_key=True, db_column="package_id")
    destination = models.ForeignKey(Destination, on_delete=models.PROTECT, related_name="packages", db_index=False)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField()
    accommodation_included = models.BooleanField(default=False)   # flag only - no hotel tables
    transport_included = models.BooleanField(default=False)       # flag only - no transport tables
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "tour_packages"
        indexes = [models.Index(fields=["destination"], name="ix_packages_destination")]
        constraints = [
            models.CheckConstraint(condition=Q(base_price__gte=0), name="ck_packages_price"),
            models.CheckConstraint(condition=Q(duration_days__gt=0), name="ck_packages_duration"),
        ]

    def __str__(self):
        return f"package #{self.pk}"


class PackageTranslation(models.Model):
    id = models.AutoField(primary_key=True, db_column="translation_id")
    package = models.ForeignKey(TourPackage, on_delete=models.PROTECT, related_name="translations")
    language_code = models.CharField(max_length=2, choices=[("en", "English"), ("ru", "Русский"), ("kk", "Қазақша")])
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "package_translations"
        constraints = [
            models.UniqueConstraint(fields=["package", "language_code"], name="uq_translation_package_lang"),
            models.CheckConstraint(condition=Q(language_code__in=["en", "ru", "kk"]), name="ck_translation_lang"),
        ]


class Departure(models.Model):
    id = models.AutoField(primary_key=True, db_column="departure_id")
    package = models.ForeignKey(TourPackage, on_delete=models.PROTECT, related_name="departures")
    guide = models.ForeignKey("accounts.Guide", on_delete=models.PROTECT, related_name="departures", db_index=False)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    seats_total = models.IntegerField()
    seats_available = models.IntegerField()
    is_active = models.BooleanField(default=True)   # deactivate instead of delete; an inactive slot frees the guide's time

    class Meta:
        db_table = "departures"
        indexes = [
            models.Index(fields=["start_at"], name="ix_departures_start_at"),
            models.Index(fields=["guide"], name="ix_departures_guide"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(end_at__gt=F("start_at")), name="ck_departures_time"),
            models.CheckConstraint(condition=Q(seats_total__gt=0), name="ck_departures_total"),
            models.CheckConstraint(condition=Q(seats_available__gte=0) & Q(seats_available__lte=F("seats_total")),
                                   name="ck_departures_seats"),
        ]

    def __str__(self):
        return f"departure #{self.pk} {self.start_at:%Y-%m-%d %H:%M}"


class Review(models.Model):
    id = models.AutoField(primary_key=True, db_column="review_id")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviews")
    package = models.ForeignKey(TourPackage, on_delete=models.PROTECT, related_name="reviews")
    rating = models.SmallIntegerField()
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reviews"
        constraints = [
            models.CheckConstraint(condition=Q(rating__gte=1) & Q(rating__lte=5), name="ck_reviews_rating"),
            models.UniqueConstraint(fields=["user", "package"], name="uq_reviews_user_package"),
        ]
