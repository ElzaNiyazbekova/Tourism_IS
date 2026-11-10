"""
roles, users, guides.   Owner: Elza (tables/constraints), Amina A. (lockout fields)
Tourists are users with role = "tourist" (ER slide label: "CUSTOMERS / users").
Integer primary keys; the PK column names (user_id, role_id ...) match db/create_tables.sql.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Role(models.Model):
    TOURIST, GUIDE, MANAGER, ANALYST, ADMIN = "tourist", "guide", "manager", "analyst", "admin"
    NAMES = (TOURIST, GUIDE, MANAGER, ANALYST, ADMIN)

    id = models.AutoField(primary_key=True, db_column="role_id")
    name = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = "roles"
        constraints = [models.CheckConstraint(condition=Q(name__in=["tourist", "guide", "manager", "analyst", "admin"]), name="ck_roles_name")]

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    use_in_migrations = False

    def create_user(self, email, password, full_name, role=Role.TOURIST, **extra):
        email = self.normalize_email(email).lower()
        role_obj, _ = Role.objects.get_or_create(name=role)
        user = self.model(email=email, full_name=full_name, role=role_obj, **extra)
        user.set_password(password)          # stored as a hash, never plain text
        user.full_clean(exclude=["password"])  # model-level validation (email format etc.)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, full_name="Admin", **extra):
        return self.create_user(email, password, full_name, role=Role.ADMIN, **extra)


class User(AbstractBaseUser):
    LANGUAGES = [("en", "English"), ("ru", "Русский"), ("kk", "Қазақша")]

    id = models.AutoField(primary_key=True, db_column="user_id")
    email = models.EmailField(max_length=254, unique=True)
    password = models.CharField("password_hash", max_length=128, db_column="password_hash")
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True, default="")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="users")
    preferred_language = models.CharField(max_length=2, choices=LANGUAGES, default="en")
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=64, blank=True, default="")   # TOTP secret (Phase 2)
    failed_login_count = models.SmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    last_login = None   # drop the column Django would add; we do not need it

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]
    objects = UserManager()

    class Meta:
        db_table = "users"
        constraints = [
            models.CheckConstraint(condition=Q(preferred_language__in=["en", "ru", "kk"]), name="ck_users_language"),
            models.CheckConstraint(condition=Q(failed_login_count__gte=0), name="ck_users_failed_login"),
            models.CheckConstraint(condition=Q(email__iregex=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"), name="ck_users_email_format"),
        ]

    def __str__(self):
        return self.email

    # ---- lockout helpers (rule: 5 failures -> locked 15 minutes) ----
    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > timezone.now())

    @property
    def role_name(self):
        return self.role.name

    def register_failure(self):
        """
        One wrong password / wrong MFA code. The 5th failure sets locked_until = now + 15 min and restarts the counter.
        Returns True when the account is locked now. The caller holds the row lock (select_for_update) and
        must NOT raise inside the same transaction.atomic block, or this save would be rolled back.
        """
        self.failed_login_count += 1
        if self.failed_login_count >= settings.LOGIN_MAX_FAILURES:
            self.locked_until = timezone.now() + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
            self.failed_login_count = 0
        self.save(update_fields=["failed_login_count", "locked_until"])
        return self.is_locked

    def clear_failures(self):
        """Successful login: forget earlier failures and any expired lock."""
        if self.failed_login_count or self.locked_until:
            self.failed_login_count = 0
            self.locked_until = None
            self.save(update_fields=["failed_login_count", "locked_until"])


class Guide(models.Model):
    id = models.AutoField(primary_key=True, db_column="guide_id")
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name="guide_profile")
    bio = models.TextField(blank=True, default="")
    languages_spoken = models.CharField(max_length=40, default="en", help_text="comma list of en,ru,kk")
    is_active = models.BooleanField(default=True)   # deactivate instead of delete
    class Meta:
        db_table = "guides"

    def __str__(self):
        return self.user.full_name

    @property
    def languages(self):
        return [c.strip() for c in self.languages_spoken.split(",") if c.strip()]
