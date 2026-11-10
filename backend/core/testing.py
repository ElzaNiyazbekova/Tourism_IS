"""Small factories shared by the tests.   Owner: Dastan (Testing)"""
import itertools
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Guide, User
from catalog.models import Departure, Destination, PackageTranslation, TourPackage

PASSWORD = "Strong#Pass2026"
_n = itertools.count(1)


def make_user(role="tourist", email=None, **kw):
    email = email or f"{role}{next(_n)}@example.com"
    return User.objects.create_user(email, PASSWORD, kw.pop("full_name", f"Test {role.title()}"), role=role,
                                    phone=kw.pop("phone", "+7 700 555 00 00"), **kw)


def make_guide(languages="en,ru", **kw):
    return Guide.objects.create(user=make_user("guide", **kw), languages_spoken=languages)


def make_destination(name="Almaty"):
    return Destination.objects.get_or_create(name=name, country="Kazakhstan")[0]


def make_package(title="Almaty City Tour", price=15000, days=1, active=True, destination=None):
    p = TourPackage.objects.create(destination=destination or make_destination(), base_price=Decimal(price),
                                   duration_days=days, is_active=active)
    PackageTranslation.objects.create(package=p, language_code="en", title=title, description="desc")
    return p


def make_departure(package=None, guide=None, start_in_days=10, hours=8, seats=5, active=True):
    start = (timezone.now() + timedelta(days=start_in_days)).replace(minute=0, second=0, microsecond=0)
    return Departure.objects.create(package=package or make_package(), guide=guide or make_guide(),
                                    start_at=start, end_at=start + timedelta(hours=hours),
                                    seats_total=seats, seats_available=seats, is_active=active)


def client_for(user=None):
    c = APIClient()
    if user is not None:
        c.force_authenticate(user=user)
    return c
