# django-tsunami

Tsunami is a Django application that records model events for Django applications.

## Installation

This package can be installed directly from GitHub:

```sh
pip install git+https://github.com/cedadev/django-tsunami.git
```

Once installed, add the Tsunami app to your `INSTALLED_APPS`. If you want Tsunami to
record the authenticated user when an event is created, you will also need to install
the user tracking middleware **after any authentication-related middlewares**:

```python
INSTALLED_APPS = [
    # ... other apps ...
    'tsunami',
]

MIDDLEWARE = [
    # ... other middleware ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # ... other middleware ...
    'tsunami.middleware.user_tracking',  # Installed after auth middleware
]
```

### Database transactions and events

In order to ensure that the events are consistent with the model state, it is recommended
that you somehow ensure that all database changes are made within a
[transaction](https://docs.djangoproject.com/en/stable/topics/db/transactions/). Doing this
ensures that a change to a model and the corresponding event are either saved together
or not at all.

There are several ways to do this, but the simplest is to use the
`ATOMIC_REQUESTS` database setting to
[tie database transactions to HTTP requests](https://docs.djangoproject.com/en/3.2/topics/db/transactions/#tying-transactions-to-http-requests):

```python
DATABASES = {
    'default': {
        # ... other database settings ...
        'ATOMIC_REQUESTS': True,
    },
}
```

## Usage

Tsunami can be used, and be useful, with zero changes to your application code. Unless
events are explicitly suspended or a model is excluded using the settings, an event will
be created automatically for any change made to a model instance. These automatic events
have an `event_type` of the form `{app label}.{model name}.{created|updated|deleted}` and
have the diff with the previous model state as the event data. For example, a change
to the email address of a standard user would produce an event with `auth.user.updated`
as the event type and `{ "email": "<new email>" }` as the data.

Tsunami includes a
[ModelAdmin](https://docs.djangoproject.com/en/3.2/ref/contrib/admin/#modeladmin-objects)
that is automatically registered with the default admin site, making all the events
visible within the admin interface where they can be filtered and inspected. Tsunami
also makes it easy to see all the events relating to a particular object by replacing
the default history view in the Django admin interface, which usually only shows changes
made via the admin, with a redirect to a pre-filtered list of events for the object.

> **WARNING**
>
> Automatic events will not be created for bulk changes, which do not trigger the
> [Django signals](https://docs.djangoproject.com/en/3.2/topics/signals/) that Tsunami
> uses to detect model changes.

Applications are also free to create their own events, and can associate whatever data
is appropriate with those events.

### Listening to events

Events can be listened for and reacted to be simply connecting to the standard
[post_save signal](https://docs.djangoproject.com/en/3.2/ref/signals/#post-save) for the
`Event` model.

However Tsunami provides a couple of decorators to simplify the process of listening to
events with specific event types. These are just wrappers around the `post_save` signal
for the `Event` model:

<dl>
    <dt><code>event_listener(*event_types, **kwargs)</code></dt>
    <dd>
        <p>Register the decorated function as a listener for events of the specified event types.</p>
        <p>Any <code>kwargs</code> are passed when connecting the signal.</p>
    </dd>
    <dt><code>model_event_listener(model, event_types, **kwargs)</code></dt>
    <dd>
        <p>
            Shorthand for <code>event_listener</code> where the event types are prepended with
            the model label.
        </p>
        <p>
            Used to avoid hard-coding the model label. This is especially useful when dealing
            with swappable models such as <code>settings.AUTH_USER_MODEL</code>, as the
            model label is not known until runtime.
        </p>
    </dd>
</dl>

For example, the following usage of `event_listener` and `model_event_listener` are equivalent
in the case where `django.contrib.auth.models.User` is used. However the `model_event_listener`
variant would continue to work if another user model was swapped in:

```python
from django.contrib.auth import get_user_model

from tsunami.helpers import event_listener, model_event_listener


@event_listener('auth.user.created', 'auth.user.updated')
def using_event_listener(event):
    # ... do something with the event ...


@model_event_listener(get_user_model(), ['created', 'updated'])
def using_model_event_listener(event):
    # ... do something with the event ...
```


## Concepts

Tsunami has two main concepts which manifest as models - `Event` and `EventAggregate`.
These are intended to be immutable, i.e. they should never be modified or deleted after
they have been created. The admin integration for events enforce this.

### Event

An `Event` represents some change or other occurence of interest that affects a model
instance. It has the following fields:

<dl>
    <dt><code>event_type</code></dt>
    <dd>
        <p>The event type.</p>
        <p>
            This is a free string (subject to the regex <code>^[a-zA-Z0-9.-_@\\/]+$</code>)
            and has no special meaning to Tsunami other than as a filter value in the events admin.
            Applications that produce and consume events should agree on a convention for this
            field.
        </p>
    </dd>
    <dt><code>target</code></dt>
    <dd>
        <p>The model instance that was directly affected by the event.</p>
        <p>
            This is a
            <a href="https://docs.djangoproject.com/en/3.2/ref/contrib/admin/#modeladmin-objects">generic foreign key</a>
            composed of the fields <code>target_ctype</code> and <code>target_id</code>, which can
            be accessed separately if required, e.g. for efficiency reasons or if the target
            object no longer exists.
        </p>
    </dd>
    <dt><code>data</code></dt>
    <dd><p>Any JSON-serializable object containing data associated with the event.</p></dd>
    <dt><code>user</code></dt>
    <dd>
        <p>The user associated with the event.</p>
        <p>
            When the user tracking middleware is enabled, this will default to the authenticated
            user. If the tracking middleware is not enabled or their is no authenticated user,
            e.g. if the model change happens within a management command, this will default to
            <code>None</code>.
        </p>
    </dd>
    <dt><code>created_at</code></dt>
    <dd><p>The <code>datetime</code> at which the event was created.</p></dd>
</dl>

### EventAggregate

An `EventAggregate` represents a relationship between an event and a model instance that is
directly or indirectly affected by the event.

The `target` of the event, i.e. the model instance that is **directly** affected by the event,
is always an aggregate - by default it is the only aggregate. However the `EventAggregate` model
allows additional model instances to be associated with an event when they are only indirectly
affected.

These relationships are not currently inferred automatically, so a model instance must declare the
indirectly affected objects using the `get_event_aggregates` method. In the future, the indirectly
affected objects may be inferred using foreign key relationships.

As a worked example, consider the following case:

```python
from django.db import models


class Car(models.Model):
    # The manufacturer of the car
    manufacturer = models.CharField(max_length = 50)


class Engine(models.Model):
    # The car that the engine belongs to
    car = models.OneToOneField(Car, models.CASCADE)
    # The number of cylinders that the engine has
    num_cylinders = models.IntegerField(default = 4)
```

In this case, changes to the engine also affect the car as a whole, so it would be nice if
events for the engine showed up when we search for all events that affect a particular car.

The way to express this relationship is for the car to be an aggregate for events where the
corresponding engine is the target. This is done by implementing `get_event_aggregates` for
the `Engine` model:

```python
class Engine(models.Model):
    # The car that the engine belongs to
    car = models.OneToOneField(Car, models.CASCADE)
    # The number of cylinders that the engine has
    num_cylinders = models.IntegerField(default = 4)

    def get_event_aggregates(self):
        # The return value should be an iterable of aggregates
        return (self.car, )
```

We can then find all the events that affect a car, either directly or indirectly, by searching
for all events that have the car as an aggregate:

```python
from django.contrib.contenttypes.models import ContentType

from tsunami.models import Event


car = Car.objects.first()

events = Event.objects.filter(
    aggregate__aggregate_ctype = ContentType.objects.get_for_model(car),
    aggregate__aggregate_id = car.pk
)
```

The aggregate relationship is recursive, so in the following case events for a cylinder will
have the (indirectly) affected engine **and car** as aggregates:

```python
from django.db import models


class Car(models.Model):
    # The manufacturer of the car
    manufacturer = models.CharField(max_length = 50)


class Engine(models.Model):
    # The car that the engine belongs to
    car = models.OneToOneField(Car, models.CASCADE)

    def get_event_aggregates(self):
        # The return value should be an iterable of aggregates
        return (self.car, )


class Cylinder(models.Model):
    engine = models.ForeignKey(Engine, models.CASCADE)

    def get_event_aggregates(self):
        # The return value should be an iterable of aggregates
        return (self.engine, )
```
