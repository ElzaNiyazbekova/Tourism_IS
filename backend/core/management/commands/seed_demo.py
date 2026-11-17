"""
python manage.py seed_demo [--reset]

Fictional demo data (all emails @example.com): 5 destinations, 10 packages with EN/RU/KZ texts,
6 guides, 30 non-overlapping departures, one user per role + 5 tourists, ~50 bookings in every
status with payments and reviews (the 50-booking test for the Task 9 analytics query).
The 5 deliberately bad records are NOT here - they come from `seed_bad_records` (Phase 4).

Owner: Elza (Data & Database)
"""
import os
import random
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Guide, Role, User
from bookings.models import AuditLog, Booking, Notification, Payment
from catalog.models import Departure, Destination, PackageTranslation, Review, TourPackage

DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "Demo#Tourism2026")   # demo accounts only; documented in README

DESTINATIONS = [("Almaty", "Kazakhstan"), ("Astana", "Kazakhstan"), ("Turkistan", "Kazakhstan"),
                ("Mangystau", "Kazakhstan"), ("Burabay", "Kazakhstan")]

# (destination index, price KZT, days, accommodation, transport, seats, {lang: (title, description)})
PACKAGES = [
    (0, 15000, 1, False, False, 12, {
        "en": ("Almaty City Highlights", "Walk through Panfilov Park, the Green Bazaar and the Zenkov Cathedral with a local guide."),
        "ru": ("Главные места Алматы", "Прогулка по парку Панфилова, Зелёному базару и Вознесенскому собору с местным гидом."),
        "kk": ("Алматының басты көрікті жерлері", "Жергілікті гидпен Панфилов саябағы, Жасыл базар және Вознесенский соборы бойынша серуен.")}),
    (0, 18000, 1, False, True, 10, {
        "en": ("Kok-Tobe and Medeu Day", "Cable car to Kok-Tobe hill, then the Medeu high-mountain skating rink and Shymbulak views."),
        "ru": ("Кок-Тобе и Медеу", "Канатная дорога на Кок-Тобе, затем высокогорный каток Медеу и виды на Шымбулак."),
        "kk": ("Көктөбе және Медеу", "Көктөбеге аспалы жол, содан кейін Медеу мұз айдыны және Шымбұлақ көріністері.")}),
    (0, 35000, 2, False, True, 8, {
        "en": ("Charyn Canyon Adventure", "Two days at the Valley of Castles with a picnic in the canyon and a night under the stars."),
        "ru": ("Приключение в Чарынском каньоне", "Два дня в Долине замков: пикник в каньоне и ночь под звёздным небом."),
        "kk": ("Шарын шатқалындағы саяхат", "Қамалдар алқабында екі күн: шатқалда пикник және жұлдызды аспан астындағы түн.")}),
    (0, 22000, 1, False, True, 10, {
        "en": ("Big Almaty Lake Hike", "A day hike to the turquoise Big Almaty Lake with mountain views and a guided nature talk."),
        "ru": ("Поход к Большому Алматинскому озеру", "Однодневный поход к бирюзовому озеру с горными видами и рассказом гида о природе."),
        "kk": ("Үлкен Алматы көліне жорық", "Тау көріністері мен гидтің табиғат туралы әңгімесі бар бір күндік жорық.")}),
    (1, 14000, 1, False, False, 15, {
        "en": ("Astana Modern Architecture Walk", "Bayterek, Khan Shatyr and the Palace of Peace and Reconciliation on foot."),
        "ru": ("Современная архитектура Астаны", "Пешая прогулка: Байтерек, Хан Шатыр и Дворец мира и согласия."),
        "kk": ("Астананың заманауи сәулеті", "Бәйтерек, Хан Шатыр және Бейбітшілік пен келісім сарайы бойынша жаяу серуен.")}),
    (2, 45000, 2, True, True, 10, {
        "en": ("Turkistan Heritage Tour", "The Mausoleum of Khoja Ahmed Yasawi and the ancient city of Otrar, with hotel and transfers."),
        "ru": ("Наследие Туркестана", "Мавзолей Ходжи Ахмеда Ясави и древний город Отрар, проживание и трансфер включены."),
        "kk": ("Түркістан мұрасы", "Қожа Ахмет Йасауи кесенесі және ежелгі Отырар қаласы, тұру мен трансфер қоса.")}),
    (3, 85000, 3, True, True, 6, {
        "en": ("Mangystau: Valley of Balls", "Three days across the Torysh stone spheres, chalk cliffs and the Ustyurt plateau."),
        "ru": ("Мангистау: Долина шаров", "Три дня среди каменных шаров Торыша, меловых скал и плато Устюрт."),
        "kk": ("Маңғыстау: Шарлар аңғары", "Торыш тас шарлары, бор жартастары және Үстірт үстіртімен үш күн.")}),
    (3, 70000, 2, True, True, 6, {
        "en": ("Bozzhyra Tract Expedition", "Off-road trip to the white-and-pink limestone formations of Bozzhyra."),
        "ru": ("Экспедиция в урочище Бозжыра", "Поездка на внедорожниках к бело-розовым известняковым скалам Бозжыры."),
        "kk": ("Бозжыра алқабына экспедиция", "Бозжыраның ақ-қызғылт әктас жартастарына жол талғамайтын көлікпен сапар.")}),
    (4, 30000, 2, True, False, 10, {
        "en": ("Burabay Lakes and Rocks", "Zhumbaktas rock, Lake Burabay and pine forest trails over two days with lodging."),
        "ru": ("Озёра и скалы Бурабая", "Скала Жумбактас, озеро Бурабай и сосновые тропы в течение двух дней с проживанием."),
        "kk": ("Бурабай көлдері мен жартастары", "Жұмбақтас жартасы, Бурабай көлі және қарағай орманындағы соқпақтар, екі күн, тұруымен.")}),
    (4, 16000, 1, False, False, 8, {
        "en": ("Burabay Sunrise Trek", "An early-morning trek to a viewpoint above the lakes, with tea at the top."),
        "ru": ("Рассвет в Бурабае", "Ранний поход на смотровую площадку над озёрами с чаем на вершине."),
        "kk": ("Бурабайдағы таң", "Көлдер үстіндегі көрініс алаңына ерте таңғы жорық, шыңда шай ішу.")}),
]

GUIDE_NAMES = [("Aigerim Seitkali", "en,ru,kk"), ("Marat Omarov", "ru,kk"), ("Daniyar Nurlan", "en,ru"),
               ("Saule Akhmetova", "en,kk"), ("Bolat Zhaksylyk", "ru,kk,en"), ("Madina Kenzhebay", "en,ru,kk")]
TOURIST_NAMES = ["Anna Petrova", "John Smith", "Aliya Nurgali", "Timur Bekov", "Elena Ivanova"]
COMMENTS = ["Great guide, very friendly.", "Beautiful places, well organised.", "A bit tiring but worth it.",
            "Would book again!", "Good value for the price."]


class Command(BaseCommand):
    help = "Load fictional demo data (idempotent: refuses to run twice unless --reset)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="delete existing demo data first")

    @transaction.atomic
    def handle(self, *args, **opts):
        if Destination.objects.exists() or User.objects.exists():
            if not opts["reset"]:
                raise CommandError("Data already exists. Use --reset to wipe and reload the demo data.")
            self._wipe()
        rng = random.Random(42)          # fixed seed => the same demo every time
        now = timezone.now()

        # --- users: one per role + 5 tourists + guides ---------------------
        User.objects.create_user("admin@example.com", DEMO_PASSWORD, "Demo Admin", role=Role.ADMIN)
        User.objects.create_user("manager@example.com", DEMO_PASSWORD, "Demo Manager", role=Role.MANAGER, phone="+7 700 000 00 01")
        User.objects.create_user("analyst@example.com", DEMO_PASSWORD, "Demo Analyst", role=Role.ANALYST)
        tourists = [User.objects.create_user(f"tourist{i + 1}@example.com", DEMO_PASSWORD, name, role=Role.TOURIST,
                                             phone=f"+7 700 100 00 0{i + 1}", preferred_language=["en", "ru", "kk", "ru", "en"][i])
                    for i, name in enumerate(TOURIST_NAMES)]
        guides = []
        for i, (name, langs) in enumerate(GUIDE_NAMES):
            u = User.objects.create_user(f"guide{i + 1}@example.com", DEMO_PASSWORD, name, role=Role.GUIDE,
                                         phone=f"+7 700 200 00 0{i + 1}")
            guides.append(Guide.objects.create(user=u, languages_spoken=langs,
                                               bio=f"Licensed local guide, {3 + i} years of experience (fictional)."))

        # --- catalogue ------------------------------------------------------
        dests = [Destination.objects.create(name=n, country=c) for n, c in DESTINATIONS]
        packages = []
        for d_idx, price, days, acc, trans, _seats, texts in PACKAGES:
            p = TourPackage.objects.create(destination=dests[d_idx], base_price=Decimal(price), duration_days=days,
                                           accommodation_included=acc, transport_included=trans)
            for lang, (title, desc) in texts.items():
                PackageTranslation.objects.create(package=p, language_code=lang, title=title, description=desc)
            packages.append(p)

        # --- departures: 30 slots, no guide overlap -------------------------
        # Guide g gets slots every 10 days (tours last <= 3 days), so slots can never overlap.
        day0 = now.replace(hour=9, minute=0, second=0, microsecond=0)
        offsets = [-20, 7, 17, 27, 37]
        departures = []
        for i in range(30):
            pkg_idx, guide = i % 10, guides[i % 6]
            start = day0 + timedelta(days=offsets[i // 6])
            seats = PACKAGES[pkg_idx][5]
            departures.append(Departure.objects.create(
                package=packages[pkg_idx], guide=guide, start_at=start,
                end_at=start + timedelta(days=PACKAGES[pkg_idx][2], hours=-1), seats_total=seats, seats_available=seats))

        # --- ~50 bookings in every status -----------------------------------
        used = {d.pk: 0 for d in departures}
        seen, made, attempts = set(), [], 0
        while len(made) < 50 and attempts < 2000:
            attempts += 1
            user, dep = tourists[attempts % 5], rng.choice(departures)
            n = rng.randint(1, 3)
            if (user.pk, dep.pk) in seen or used[dep.pk] + n > dep.seats_total:
                continue
            seen.add((user.pk, dep.pk))
            past = dep.start_at < now
            status = rng.choice([Booking.COMPLETED] * 4 + [Booking.CANCELLED]) if past else \
                rng.choice([Booking.CONFIRMED] * 4 + [Booking.PENDING] * 2 + [Booking.CANCELLED] * 2 + [Booking.NEEDS_REVIEW])
            travel = timezone.localtime(dep.start_at).date()
            booked = travel - timedelta(days=rng.randint(5, 30)) if past else min(timezone.localdate() - timedelta(days=rng.randint(0, 5)), travel)
            b = Booking.objects.create(
                booking_ref=f"TMP-{uuid.uuid4().hex[:8]}", user=user, departure=dep, booking_date=booked, travel_date=travel,
                travelers_count=n, total_cost=dep.package.base_price * n, status=status,
                special_request=rng.choice(["", "", "Vegetarian lunch please", "Need a child seat"]),
                expires_at=now + timedelta(hours=rng.randint(1, 47)) if status == Booking.PENDING else None)
            b.booking_ref = f"BK-{b.pk:04d}"
            b.save(update_fields=["booking_ref"])
            if status != Booking.CANCELLED:
                used[dep.pk] += n          # cancelled bookings release their seats
            made.append(b)
            AuditLog.objects.create(user=None, action="seed", table_name="bookings", record_id=b.pk,
                                    new_value={"ref": b.booking_ref, "status": status})

            if status in (Booking.CONFIRMED, Booking.COMPLETED):
                Payment.objects.create(booking=b, amount=b.total_cost, status=Payment.SUCCESS,
                                       transaction_ref=f"TX-{uuid.uuid4().hex[:10].upper()}", paid_at=now - timedelta(days=1))
            elif status == Booking.PENDING and rng.random() < 0.4:
                Payment.objects.create(booking=b, amount=b.total_cost, status=Payment.FAILED,
                                       transaction_ref=f"TX-{uuid.uuid4().hex[:10].upper()}")
            if status == Booking.COMPLETED and not Review.objects.filter(user=user, package=dep.package).exists():
                Review.objects.create(user=user, package=dep.package, rating=rng.randint(3, 5), comment=rng.choice(COMMENTS))

        for dep in departures:               # keep seats_available consistent with the bookings
            dep.seats_available = dep.seats_total - used[dep.pk]
            dep.save(update_fields=["seats_available"])

        by_status = {s: sum(1 for b in made if b.status == s) for s in Booking.STATUSES}
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(dests)} destinations, {len(packages)} packages, {len(guides)} guides, "
            f"{len(departures)} departures, {len(made)} bookings {by_status}, "
            f"{Payment.objects.count()} payments, {Review.objects.count()} reviews."))
        self.stdout.write(f"Demo password for every demo account: {DEMO_PASSWORD}")

    def _wipe(self):
        """Delete in dependency order (all FKs are RESTRICT, so order matters)."""
        for model in (Review, Notification, Payment, AuditLog, Booking, PackageTranslation, Departure, TourPackage,
                      Destination, Guide, User):
            model.objects.all().delete()
