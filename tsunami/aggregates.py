from django.db.models.signals import post_save

from .models import Event, EventAggregate


def find_aggregates(instance):
    """
    Finds all the aggregates for the given instance.

    By default, the instance itself is the only aggregate, but models can
    define a ``get_event_aggregates`` method that returns an iterable
    of aggregates.

    This is a recursive operation - the aggregates of an instance's aggregates
    are also aggregates of the instance.
    """
    # The instance itself is always an aggregate
    aggregates = set([instance])
    # If the instance defines a get_event_aggregates method, use it
    if hasattr(instance, 'get_event_aggregates'):
        for aggregate in instance.get_event_aggregates():
            aggregates.update(find_aggregates(aggregate))
    return aggregates


def create_aggregates(sender, instance, created, **kwargs):
    """
    Handles the post_save signal for events and creates aggregates.
    """
    if created:
        for aggregate in find_aggregates(instance.target):
            EventAggregate.objects.create(event = instance, aggregate = aggregate)


def connect_signals():
    dispatch_uid = '{}.{}'.format(create_aggregates.__module__, create_aggregates.__qualname__)
    post_save.connect(create_aggregates, sender = Event, dispatch_uid = dispatch_uid)


def disconnect_signals():
    dispatch_uid = '{}.{}'.format(create_aggregates.__module__, create_aggregates.__qualname__)
    post_save.disconnect(dispatch_uid = dispatch_uid)
