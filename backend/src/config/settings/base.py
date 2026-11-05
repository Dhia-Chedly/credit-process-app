from datetime import timedelta
from pathlib import Path

import environ

PROJECT_DIR = Path(__file__).resolve().parents[3]
REPOSITORY_DIR = PROJECT_DIR.parent

env = environ.Env(
    DEBUG=(bool, False),
    DJANGO_READ_DOT_ENV_FILE=(bool, False),
)

if env.bool("DJANGO_READ_DOT_ENV_FILE", default=False):
    environ.Env.read_env(REPOSITORY_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-development-secret")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

DJANGO_APPS = [
    "apps.core.auth_config.LeanAuthConfig",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = [
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
]
LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.applications",
    "apps.imports",
    "apps.warehouse",
    "apps.data_quality",
    "apps.analytics",
    "apps.alerts",
    "apps.assistant",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    }
]

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{PROJECT_DIR / 'db.sqlite3'}",
    )
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    database_options = DATABASES["default"].setdefault("OPTIONS", {})
    existing_options = database_options.get("options", "")
    database_options["options"] = (
        f"{existing_options} -c search_path=public,auth,ingestion,warehouse".strip()
    )

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Tunis"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = PROJECT_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = PROJECT_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

WAREHOUSE_PII_ENCRYPTION_KEYS = env.list(
    "WAREHOUSE_PII_ENCRYPTION_KEYS",
    default=[SECRET_KEY],
)
IMPORT_MAX_UPLOAD_BYTES = env.int("IMPORT_MAX_UPLOAD_BYTES", default=25 * 1024 * 1024)
IMPORT_MAX_UNCOMPRESSED_BYTES = env.int(
    "IMPORT_MAX_UNCOMPRESSED_BYTES",
    default=512 * 1024 * 1024,
)
DATA_UPLOAD_MAX_MEMORY_SIZE = IMPORT_MAX_UPLOAD_BYTES + 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = env.int("FILE_UPLOAD_MAX_MEMORY_SIZE", default=5 * 1024 * 1024)
ALERT_EMAIL_ENABLED = env.bool("ALERT_EMAIL_ENABLED", default=False)
EMAIL_HOST = env("SMTP_HOST", default="")
EMAIL_PORT = env.int("SMTP_PORT", default=587)
EMAIL_HOST_USER = env("SMTP_USERNAME", default="")
EMAIL_HOST_PASSWORD = env("SMTP_APP_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("SMTP_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("SMTP_FROM_EMAIL", default=EMAIL_HOST_USER)

ASSISTANT_ENABLED = env.bool("ASSISTANT_ENABLED", default=False)
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
OPENAI_MODEL = env("OPENAI_MODEL", default="")
ASSISTANT_MAX_OUTPUT_TOKENS = env.int("ASSISTANT_MAX_OUTPUT_TOKENS", default=900)

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.VersionedJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_RATES": {
        "auth_login": "5/minute",
        "auth_register": "5/minute",
        "assistant": "20/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=8),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}
JWT_REFRESH_COOKIE_NAME = "microcrd_refresh"
JWT_REFRESH_COOKIE_PATH = "/api/auth/"
JWT_REFRESH_COOKIE_SECURE = env.bool("JWT_REFRESH_COOKIE_SECURE", default=not DEBUG)
JWT_REFRESH_COOKIE_SAMESITE = "Strict"

SPECTACULAR_SETTINGS = {
    "TITLE": "Credit Operations Platform API",
    "DESCRIPTION": "Credit-request ingestion and operations API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Import batches and application lineage intentionally share this taxonomy.
    # Give the shared choice set one stable OpenAPI component name.
    "ENUM_NAME_OVERRIDES": {
        "WorkbookTypeEnum": [
            ("unknown", "Unknown"),
            ("tb1", "TB1 - credit requests"),
            ("tb2", "TB2 - outstanding loans"),
        ],
        "PipelineStageEnum": [
            ("intake", "Intake"),
            ("waiting_visit", "Waiting for visit"),
            ("waiting_decision", "Waiting for decision"),
            ("waiting_disbursement", "Waiting for disbursement"),
            ("completed", "Completed"),
        ],
    },
}

CORS_ALLOWED_ORIGINS = env.list("DJANGO_CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="amqp://guest:guest@localhost:5672//")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_DEFAULT_QUEUE = "microcrd.tasks"
CELERY_TASK_DEFAULT_QUEUE_TYPE = "quorum"
CELERY_TASK_CREATE_MISSING_QUEUE_TYPE = "quorum"
CELERY_BROKER_TRANSPORT_OPTIONS = {"confirm_publish": True}
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_ENABLE_REMOTE_CONTROL = False
CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "verbose"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
