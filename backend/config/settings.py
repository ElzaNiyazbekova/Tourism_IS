"""
Django settings for Tourism IS.
Owner: Amina A. (Architecture & Security)

Every secret comes from environment variables (.env). There are NO default passwords:
if a secret is missing or still says "change-me", the server refuses to start.
"""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    """Tiny .env reader so local runs work without extra packages (Docker passes env itself)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(BASE_DIR.parent / ".env")
_load_env_file(BASE_DIR / ".env")


def env(name: str, default: str | None = None, secret: bool = False) -> str:
    value = os.environ.get(name, default)
    if value is None or (secret and (value == "" or value.startswith("change-me"))):
        raise RuntimeError(
            f"Environment variable {name} is missing or still a placeholder. "
            "Copy .env.example to .env (run scripts/init_env.sh) and set real values."
        )
    return value


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


SECRET_KEY = env("DJANGO_SECRET_KEY", secret=True)
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.auth",          # needed for password hashing/validators; the default admin UI is NOT installed
    "django.contrib.contenttypes",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.messages",

    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "drf_spectacular_sidecar",      # Swagger UI served from our own files (works offline)
    "core",
    "accounts",
    "catalog",
    "bookings",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",   # serves the Angular build in offline mode (Phase 5)
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",     # API uses JWT in a header, so cookies are not trusted anyway
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
AUTH_USER_MODEL = "accounts.User"

# ---- database: PostgreSQL by default, SQLite for the offline demo ----------
DB_ENGINE = env("DB_ENGINE", "postgres").lower()
if DB_ENGINE == "sqlite":
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env("SQLITE_PATH", str(BASE_DIR / "demo.sqlite3")),
    }}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "tourism"),
        "USER": env("POSTGRES_USER", "tourism"),
        "PASSWORD": env("POSTGRES_PASSWORD", secret=True),
        "HOST": env("POSTGRES_HOST", "db"),
        "PORT": env("POSTGRES_PORT", "5432"),
    }}
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"   # integer keys everywhere

# ---- passwords (functionality 1): min 8, not common, not numeric-only -------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_MAX_FAILURES = 5          # lockout after 5 wrong passwords ...
LOGIN_LOCK_MINUTES = 15         # ... for 15 minutes

# ---- REST framework ---------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    # Secure by default: an endpoint is closed unless it explicitly says AllowAny / a role.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "UPDATE_LAST_LOGIN": False,     # our User has no last_login column
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Tourism IS API",
    "DESCRIPTION": "Tour packages, guides, slots and bookings. Errors: {code, message_key, message, field_errors}.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
}

# ---- CORS / CSRF ------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [o.strip() for o in env("CORS_ALLOWED_ORIGINS", "http://localhost:4200").split(",") if o.strip()]
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# ---- i18n / time ------------------------------------------------------------
LANGUAGE_CODE = "en"
SUPPORTED_LANGUAGES = ("en", "ru", "kk")
TIME_ZONE = "Asia/Almaty"
USE_TZ = True

# ---- static files (Angular build is copied here in offline mode) -----------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# ---- business rules (kept here so they are easy to explain) -----------------
PENDING_BOOKING_HOURS = 48      # rule 7: unpaid Pending bookings expire after 48 h
CANCEL_MIN_DAYS_BEFORE = 3      # tourist may cancel up to 3 days before start

# Email goes to the console only (no real SMTP).
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
