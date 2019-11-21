from django.apps import AppConfig


class TsunamiAppConfig(AppConfig):
    """
    Django app config for the tsunami app.
    """
    name = 'tsunami'

    def ready(self):
        # When the app is ready, enable tracking
        from . import tracking
        tracking.enable()
