from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config.settings.base import *

DEBUG = False
SECRET_KEY = "test-only-secret-with-at-least-thirty-two-bytes"
SIMPLE_JWT = {**SIMPLE_JWT, "SIGNING_KEY": SECRET_KEY}
ALLOWED_HOSTS = ["testserver"]
MIDDLEWARE = [
    middleware
    for middleware in MIDDLEWARE
    if middleware != "whitenoise.middleware.WhiteNoiseMiddleware"
]

if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured(
        "config.settings.test requires PostgreSQL. Set DATABASE_URL to a PostgreSQL database."
    )

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MEDIA_ROOT = Path("/tmp/microcrd-test-media")
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
