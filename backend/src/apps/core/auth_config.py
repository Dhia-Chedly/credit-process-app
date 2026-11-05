from django.apps import AppConfig


class LeanAuthConfig(AppConfig):
    """Keep Django authentication primitives without its group/permission subsystem."""

    name = "django.contrib.auth"
    label = "auth"

    def ready(self) -> None:
        # Deliberately do not register auth's post-migrate permission creator.
        return None
