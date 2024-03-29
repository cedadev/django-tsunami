from django.apps import AppConfig


class TsunamiAppConfig(AppConfig):
    """
    Django app config for the tsunami app.
    """
    name = 'tsunami'

    # By default, use bigints for the id field of Tsunami models
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # When the app is ready, enable tracking
        from . import tracking
        tracking.enable()


# Patch the ModelAdmin history_view to point to the events for an object
from django.contrib.admin import ModelAdmin
from django.contrib.admin.utils import unquote
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from django.core.exceptions import PermissionDenied
def history_redirect(model_admin, request, object_id, extra_context = None):
    # First, find the object that the history is for
    model = model_admin.model
    obj = model_admin.get_object(request, unquote(object_id))
    if obj is None:
        return model_admin._get_obj_does_not_exist_redirect(request, model._meta, object_id)
    if not model_admin.has_view_or_change_permission(request, obj):
        raise PermissionDenied
    # If we get this far, redirect to the tsunami events with the correct parameters
    from django.contrib.contenttypes.models import ContentType
    ctype = ContentType.objects.get_for_model(obj)
    events_url = reverse('admin:tsunami_event_changelist')
    qs = urlencode(dict(
        aggregate__aggregate_ctype__id__exact = ctype.pk,
        aggregate__aggregate_id = obj.pk
    ))
    return redirect('{}?{}'.format(events_url, qs))
ModelAdmin.history_view = history_redirect
