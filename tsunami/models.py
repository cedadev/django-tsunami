import uuid

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.conf import settings

from jsonfallback.fields import FallbackJSONField


def _default_user():
    """
    Returns the user from the tracking state.
    """
    from . import tracking
    return tracking.state.user


class Event(models.Model):
    """
    Model representing an event that has been produced by an action.
    """
    class Meta:
        index_together = (
            # Make an index for the generic target
            ('target_ctype', 'target_id'),
        )
        ordering = ('-created_at', )

    # Use a UUID for the primary key
    id = models.UUIDField(primary_key = True, editable = False, default = uuid.uuid4)
    # Event type is a free field - apps should know how to display their own events when required
    event_type = models.SlugField()
    # Every event has a target, which is a generic foreign key
    target_ctype = models.ForeignKey(ContentType, models.CASCADE)
    # This should be big enough to hold a UUID
    target_id = models.CharField(max_length = 40)
    target = GenericForeignKey('target_ctype', 'target_id')
    # Event data is stored as a JSON blob
    data = FallbackJSONField(default = dict)
    # Events can optionally have an associated user
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.SET_NULL,
        null = True,
        default = _default_user
    )
    # All events record a created time
    created_at = models.DateTimeField(auto_now_add = True)
