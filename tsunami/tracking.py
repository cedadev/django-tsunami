import threading
import json

from django.apps import apps
from django.db.models.signals import post_save, m2m_changed, post_delete
from django.core.serializers import serialize

from .models import Event
from .settings import app_settings


# Use a thread-local to track the current user
# This is populated by a middleware
state = threading.local()
state.user = None


def _event_type(model, change_type):
    """
    Returns a namespaced event type for the given change type.
    """
    return model._meta.label_lower + '.' + change_type


def _instance_as_dict(instance):
    """
    Returns the instance as a dictionary.
    """
    # In order to get everything in the correct format, we serialize to JSON
    # and then convert back
    data = serialize('json', (instance, ), use_natural_foreign_keys = True)
    return json.loads(data)[0]['fields']


def post_save_receiver(sender, instance, created, **kwargs):
    """
    Handles the post_save signal for tracked models.
    """
    # This receiver creates a create or update event for the instance
    if app_settings.IS_TRACKED_PREDICATE(sender):
        Event.objects.create(
            event_type = _event_type(sender, 'created' if created else 'updated'),
            target = instance,
            data = _instance_as_dict(instance)
        )


def m2m_changed_receiver(sender, instance, action, reverse, **kwargs):
    """
    Handles the m2m_changed signal for tracked models.
    """
    if app_settings.IS_TRACKED_PREDICATE(sender):
        # Only process the forward side of the relation
        if action.startswith("post_") and not reverse:
            Event.objects.create(
                event_type = _event_type(type(instance), 'updated'),
                target = instance,
                data = _instance_as_dict(instance)
            )


def post_delete_receiver(sender, instance, **kwargs):
    """
    Handles the post_delete signal for tracked models.
    """
    if app_settings.IS_TRACKED_PREDICATE(sender):
        Event.objects.create(
            event_type = _event_type(sender, 'deleted'),
            target = instance
        )


def _dispatch_uid(receiver):
    """
    Returns the dispatch_uid for the given receiver.
    """
    return '{}.{}'.format(receiver.__module__, receiver.__qualname__)


def enable():
    """
    Connects the tracking signals, and so enables tracking.
    """
    post_save.connect(post_save_receiver, dispatch_uid = _dispatch_uid(post_save_receiver))
    m2m_changed.connect(m2m_changed_receiver, dispatch_uid = _dispatch_uid(m2m_changed_receiver))
    post_delete.connect(post_delete_receiver, dispatch_uid = _dispatch_uid(post_delete_receiver))


def disable():
    """
    Disconnects the tracking signals, and so disables tracking.
    """
    post_save.disconnect(dispatch_uid = _dispatch_uid(post_save_receiver))
    m2m_changed.disconnect(dispatch_uid = _dispatch_uid(m2m_changed_receiver))
    post_delete.disconnect(dispatch_uid = _dispatch_uid(post_delete_receiver))
