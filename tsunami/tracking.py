import threading
import json
import contextlib

from django.apps import apps
from django.db.models.signals import post_init, post_save, m2m_changed, post_delete
from django.core.serializers import serialize

from .models import Event
from .settings import app_settings


# Use a thread-local to track the current user
# This is populated by a middleware
class _State(threading.local):
    def __init__(self):
        self.user = None
        self.suspended = False

state = _State()


@contextlib.contextmanager
def suspend():
    """
    Context manager that suspends creation of tracking events for the duration of the context.
    """
    state.suspended = True
    try:
        yield
    finally:
        state.suspended = False


def _event_type(model, change_type):
    """
    Returns a namespaced event type for the given change type.
    """
    return '{}.{}'.format(model._meta.label_lower, change_type)


def _instance_as_dict(instance, fields = None):
    """
    Returns the instance as a dictionary.
    """
    # By default, use all fields except M2M as they are a performance hog
    if fields is None:
        fields = tuple(f.name for f in instance._meta.get_fields() if f.concrete and not f.many_to_many)
    # In order to get everything in the correct format, we serialize to JSON and then convert back
    data = serialize('json', (instance, ), fields = fields)
    return json.loads(data)[0]['fields']


def _instance_diff(instance, created = False):
    """
    Returns a diff for the instance as a dict.
    """
    # Get the current state as a dict
    state = _instance_as_dict(instance)
    # If the instance is brand new, just return the full instance
    if created:
        return state
    # Otherwise, since we are dealing with models, a simple single-level diff is enough
    # We only return information about fields that are in the new state
    previous = getattr(instance, '_tsunami_state', {})
    return {
        field: state[field]
        for field in state
        if field not in previous or state[field] != previous[field]
    }


def post_init_receiver(sender, instance, **kwargs):
    """
    Handles the post_init signal for tracked models.
    """
    # If the instance is loaded from the DB, store the initial serialized state
    # This will allow us to diff with the current state when we create an event
    if app_settings.IS_TRACKED_PREDICATE(sender):
        # Try to serialize the instance - this will fail for new instances
        try:
            instance._tsunami_state = _instance_as_dict(instance)
        except ValueError:
            pass


def post_save_receiver(sender, instance, created, **kwargs):
    """
    Handles the post_save signal for tracked models.
    """
    # This receiver creates a create or update event for the instance
    if not state.suspended and app_settings.IS_TRACKED_PREDICATE(sender):
        # Only produce an event if the diff is non-empty
        diff = _instance_diff(instance, created)
        if diff:
            Event.objects.create(
                event_type = _event_type(sender, 'created' if created else 'updated'),
                target = instance,
                data = diff
            )


def m2m_changed_receiver(sender, instance, action, reverse, **kwargs):
    """
    Handles the m2m_changed signal for tracked models.
    """
    # Only process the forward side of the relation
    if action.startswith("post_") and not reverse:
        # Use the instance type instead of the sender to determine if we should track
        model = type(instance)
        if not state.suspended and app_settings.IS_TRACKED_PREDICATE(model):
            # Find the field for which sender is the through model
            field = next(
                iter(
                    f.name
                    for f in model._meta.get_fields()
                    if f.many_to_many and f.remote_field.through == sender
                ),
                None
            )
            if field:
                Event.objects.create(
                    event_type = _event_type(model, 'm2m_changed'),
                    target = instance,
                    # The data is the serialized value of the single m2m field
                    data = _instance_as_dict(instance, fields = (field, ))
                )


def post_delete_receiver(sender, instance, **kwargs):
    """
    Handles the post_delete signal for tracked models.
    """
    if not state.suspended and app_settings.IS_TRACKED_PREDICATE(sender):
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
    post_init.connect(post_init_receiver, dispatch_uid = _dispatch_uid(post_init_receiver))
    post_save.connect(post_save_receiver, dispatch_uid = _dispatch_uid(post_save_receiver))
    m2m_changed.connect(m2m_changed_receiver, dispatch_uid = _dispatch_uid(m2m_changed_receiver))
    post_delete.connect(post_delete_receiver, dispatch_uid = _dispatch_uid(post_delete_receiver))


def disable():
    """
    Disconnects the tracking signals, and so disables tracking.
    """
    post_init.disconnect(dispatch_uid = _dispatch_uid(post_init_receiver))
    post_save.disconnect(dispatch_uid = _dispatch_uid(post_save_receiver))
    m2m_changed.disconnect(dispatch_uid = _dispatch_uid(m2m_changed_receiver))
    post_delete.disconnect(dispatch_uid = _dispatch_uid(post_delete_receiver))
