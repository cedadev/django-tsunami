from django.db.models.signals import post_save

from .models import Event


def event_listener(*event_types, **kwargs):
    """
    Decorator that registers a listener function for the given event types.
    """
    def decorator(listener):
        def signal_receiver(sender, instance, **kwargs):
            if instance.event_type in event_types:
                listener(instance)
        # Register the wrapper as a signal handler for the event model
        post_save.connect(signal_receiver, Event, **kwargs)
        # Return the signal receiver to allow weak references to be made
        return signal_receiver
    return decorator


def model_event_listener(model, event_types, **kwargs):
    """
    Decorator that registers a listener function for the given model and event types.

    This is just a shorthand for registering for events of the form "<model label>.<event type>".
    """
    model_label = model._meta.label_lower
    event_types = ["{}.{}".format(model_label, event_type) for event_type in event_types]
    return event_listener(*event_types, **kwargs)
