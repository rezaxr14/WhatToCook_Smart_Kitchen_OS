from django.apps import AppConfig


class GetfoodConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'GetFood'

    def ready(self):
        from . import events  # noqa: F401  (connects the domain-event signal receivers)
