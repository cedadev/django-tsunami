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


def _event_type(instance, diff, default):
    """
    Returns a namespaced event type for a change event.
    """
    # For a model that is tsunami-aware, give it a chance to set the event type based on the diff
    # If not, return the default with the model label as a namespace
    event_type = None
    if hasattr(instance, 'get_event_type'):
        event_type = instance.get_event_type(diff)
    if event_type:
        return event_type
    else:
        return '{}.{}'.format(instance._meta.label_lower, default)


def _instance_as_dict(instance, fields = None):
    """
    Returns the instance as a dictionary.
    """
    # By default, use all fields except M2M as they require extra queries
    # This function is run for every tracked instance that is loaded from the DB, so extra
    # queries are not good for performance!
    if fields is None:
        fields = tuple(
            f.name
            for f in instance._meta.get_fields()
            if f.concrete and not f.many_to_many
        )
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
    if not app_settings.IS_TRACKED_PREDICATE(sender):
        return
    # If the instance is loaded from the DB, store the initial serialized state
    # This will allow us to diff with the current state when we create an event
    try:
        # Try to serialize the instance - this will fail for new instances
        instance._tsunami_state = _instance_as_dict(instance)
    except ValueError:
        pass


def post_save_receiver(sender, instance, created, **kwargs):
    """
    Handles the post_save signal by saving a create or update event for tracked instances.
    """
    if state.suspended:
        return
    if not app_settings.IS_TRACKED_PREDICATE(sender):
        return
    # Only produce an event if the diff is non-empty
    diff = _instance_diff(instance, created)
    if diff:
        Event.objects.create(
            event_type = _event_type(instance, diff, 'created' if created else 'updated'),
            target = instance,
            data = diff
        )


def m2m_changed_receiver(sender, instance, action, reverse, model, pk_set, **kwargs):
    """
    Handles the m2m_changed signal by saving an update event for tracked instances.
    """
    if state.suspended:
        return
    # Only process post-change events
    if not action.startswith("post_"):
        return
    # Only process the forward side of the relation
    if reverse:
        return
    # If the instance should not be tracked, return
    if not app_settings.IS_TRACKED_PREDICATE(instance.__class__):
        return
    # Get the name of the many-to-many field for the relation
    m2m_field = next(
        (
            f.name
            for f in instance._meta.get_fields()
            if f.many_to_many and
               f.related_model == model and
               f.remote_field.through == sender
        ),
        None
    )
    if m2m_field:
        # The diff is the serialized value of the single m2m field
        diff = _instance_as_dict(instance, fields = (m2m_field, ))
        Event.objects.create(
            event_type = _event_type(instance, diff, 'updated'),
            target = instance,
            # The data is the serialized value of the single m2m field
            data = diff
        )


def post_delete_receiver(sender, instance, **kwargs):
    """
    Handles the post_delete signal by saving a deleted event for tracked instances.
    """
    if state.suspended:
        return
    if not app_settings.IS_TRACKED_PREDICATE(sender):
        return
    Event.objects.create(
        event_type = '{}.deleted'.format(sender._meta.label_lower),
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
