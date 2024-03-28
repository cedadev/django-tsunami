import uuid

from django.db import models, router, transaction
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.conf import settings
from django.core.validators import RegexValidator

from jsonfield import JSONField


def _default_user():
    """
    Returns the user from the tracking state.
    """
    from . import tracking
    return tracking.state.user


def _find_aggregates(instance):
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
            aggregates.update(_find_aggregates(aggregate))
    return aggregates


class Event(models.Model):
    """
    Model representing an event that has been produced by a change to a model.
    """
    class Meta:
        indexes = [
            # Make an index for the generic fk
            models.Index(fields=['target_ctype', 'target_id']),
        ]
        ordering = ('-created_at', )

    # Use a UUID for the primary key
    id = models.UUIDField(primary_key = True, editable = False, default = uuid.uuid4)
    # Event type is a free field - apps should know how to display their own events when required
    event_type = models.CharField(
        max_length = 250,
        validators = (RegexValidator('^[a-zA-Z0-9.-_@\\/]+$'), )
    )
    # Every event has a target, which is a generic foreign key
    target_ctype = models.ForeignKey(ContentType, models.CASCADE)
    # This should be big enough to hold a UUID
    target_id = models.CharField(max_length = 40)
    target = GenericForeignKey('target_ctype', 'target_id')
    # Event data is stored as a JSON blob
    data = JSONField(default = dict)
    # Events can optionally have an associated user
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.SET_NULL,
        null = True,
        default = _default_user
    )
    # All events record a created time
    created_at = models.DateTimeField(auto_now_add = True)

    @property
    def short_id(self):
        return str(self.id)[:8]

    def save(self, force_insert = False,
                   force_update = False,
                   using = None,
                   update_fields = None):
        # Save the event and the aggregates in the same transaction
        # Assume the event and event aggregates are saved in the same db
        using = using or router.db_for_write(self.__class__, instance = self)
        with transaction.atomic(using = using):
            super().save(force_insert, force_update, using, update_fields)
            EventAggregate.objects.bulk_create([
                EventAggregate(event = self, aggregate = aggregate)
                for aggregate in _find_aggregates(self.target)
            ])


class EventAggregate(models.Model):
    """
    Model representing the relationship of an event to an aggregate.

    An event may be related to several aggregates.
    """
    class Meta:
        indexes = [
            # Make an index for the generic fk
            models.Index(fields=['aggregate_ctype', 'aggregate_id']),
        ]
        ordering = (
            'aggregate_ctype__app_label',
            'aggregate_ctype__model',
            'aggregate_id'
        )

    event = models.ForeignKey(
        Event,
        models.CASCADE,
        related_name = 'aggregates',
        related_query_name = 'aggregate'
    )
    # The aggregate is a generic foreign key
    aggregate_ctype = models.ForeignKey(ContentType, models.CASCADE)
    # This should be big enough to hold a UUID
    aggregate_id = models.CharField(max_length = 40)
    aggregate = GenericForeignKey('aggregate_ctype', 'aggregate_id')
