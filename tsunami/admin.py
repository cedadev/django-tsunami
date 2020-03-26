import json

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils.encoding import force_text

from django_admin_listfilter_dropdown.filters import (
    DropdownFilter,
    RelatedDropdownFilter,
    RelatedOnlyDropdownFilter
)

from rangefilter.filter import DateRangeFilter

from .models import Event, EventAggregate


def _make_link(obj_or_ctype, obj_id = None):
    if obj_id is None:
        ctype = ContentType.objects.get_for_model(obj_or_ctype)
        obj_id = obj_or_ctype.pk
        link_text = str(obj_or_ctype)
    else:
        ctype = obj_or_ctype
        link_text = obj_id
    try:
        return format_html(
            '<a href="{}">{}</a>',
            reverse(
                'admin:{}_{}_change'.format(ctype.app_label, ctype.model),
                args = (obj_id, )
            ),
            link_text
        )
    except NoReverseMatch:
        return str(link_text)


class GfkContentTypeFilter(RelatedDropdownFilter):
    """
    Related filter for the content type of a GFK that includes the app label.

    It will remove the configured id parameter when the content type changes.
    """
    def field_choices(self, field, request, model_admin):
        return tuple(
            (ct.pk, '{}.{}'.format(ct.app_label, ct.model))
            for ct in ContentType.objects.all()
        )

    def choices(self, changelist):
        # We override choices in order to remove the id parameter from the query string
        # if the content type changes
        yield {
            'selected': self.lookup_val is None and not self.lookup_val_isnull,
            'query_string': changelist.get_query_string(
                remove = [self.lookup_kwarg, self.lookup_kwarg_isnull, self.id_parameter_name]
            ),
            'display': 'All',
        }
        for pk_val, val in self.lookup_choices:
            if self.lookup_val == str(pk_val):
                to_remove = [self.lookup_kwarg_isnull]
            else:
                to_remove = [self.id_parameter_name, self.lookup_kwarg_isnull]
            yield {
                'selected': self.lookup_val == str(pk_val),
                'query_string': changelist.get_query_string(
                    { self.lookup_kwarg: pk_val },
                    to_remove
                ),
                'display': val,
            }
        if self.include_empty_choice:
            yield {
                'selected': bool(self.lookup_val_isnull),
                'query_string': changelist.get_query_string(
                    {self.lookup_kwarg_isnull: 'True'},
                    [self.lookup_kwarg, self.id_parameter_name]
                ),
                'display': self.empty_value_display,
            }


class AggregateContentTypeFilter(GfkContentTypeFilter):
    id_parameter_name = 'aggregate__aggregate_id'


class TargetContentTypeFilter(GfkContentTypeFilter):
    id_parameter_name = 'target_id'


class GfkIdFilter(admin.SimpleListFilter):
    """
    Filter for the id of a GFK.

    Only takes effect when the corresponding content type filter is also present.
    """
    # Use the dropdown filter template
    template = 'django_admin_listfilter_dropdown/dropdown_filter.html'

    def __init__(self, request, params, model, model_admin):
        # Find the content type referred to by the related content type parameter
        self.content_type = None
        ctype_id = request.GET.get(self.ctype_parameter_name)
        if ctype_id:
            try:
                self.content_type = ContentType.objects.get(pk = ctype_id)
            except ObjectDoesNotExist:
                pass
        super().__init__(request, params, model, model_admin)

    def lookups(self, request, model_admin):
        if not self.content_type:
            return ()
        # Display all the options for the selected ctype
        return tuple(
            (obj.pk, str(obj))
            for obj in self.content_type.model_class().objects.all()
        )

    def queryset(self, request, queryset):
        if self.value():
            # Find the events that match the ctype and id
            return queryset.filter(**{
                self.ctype_parameter_name: self.content_type.pk,
                self.parameter_name: self.value()
            })


class AggregateIdFilter(GfkIdFilter):
    title = 'Aggregate'
    # Parameter for the aggregate primary key
    parameter_name = 'aggregate__aggregate_id'
    # Parameter that the content type pk will use
    ctype_parameter_name = 'aggregate__aggregate_ctype__id__exact'


class TargetIdFilter(GfkIdFilter):
    title = 'Target'
    # Parameter for the aggregate primary key
    parameter_name = 'target_id'
    # Parameter that the content type pk will use
    ctype_parameter_name = 'target_ctype__id__exact'


class EventAggregateInline(admin.TabularInline):
    model = EventAggregate

    readonly_fields = ('aggregate_ctype_formatted', 'aggregate_link')
    exclude = ('aggregate_ctype', 'aggregate_id')

    def aggregate_ctype_formatted(self, obj):
        # Display the full label for the content type
        return format_html(
            '<code>{}.{}</code>',
            obj.aggregate_ctype.app_label,
            obj.aggregate_ctype.model
        )
    aggregate_ctype_formatted.short_description = 'aggregate ctype'

    def aggregate_link(self, obj):
        return _make_link(obj.aggregate_ctype, obj.aggregate_id)
    aggregate_link.short_description = 'aggregate'

    # Disallow all edit permissions
    def has_add_permission(self, request, obj):
        return False

    def has_change_permission(self, request, obj = None):
        return False

    def has_delete_permission(self, request, obj = None):
        return False


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        'short_id',
        'event_type_formatted',
        'target_ctype_formatted',
        'target_link',
        'num_aggregates',
        'user_link',
        'created_at'
    )
    list_select_related = ('target_ctype', 'user')
    list_filter = (
        ('aggregate__aggregate_ctype', AggregateContentTypeFilter),
        AggregateIdFilter,
        ('target_ctype', TargetContentTypeFilter),
        TargetIdFilter,
        ('event_type', DropdownFilter),
        ('user', RelatedOnlyDropdownFilter),
        ('created_at', DateRangeFilter),
    )
    inlines = (EventAggregateInline, )
    # Use readonly fields and exclude to format the fields nicely
    readonly_fields = (
        'id',
        'event_type_formatted',
        'target_ctype_formatted',
        'target_link',
        'data_formatted',
        'user_link',
        'created_at'
    )
    exclude = ('event_type', 'target_ctype', 'target_id', 'data', 'user')

    def get_queryset(self, request):
        # Annotate the queryset with information about the number of aggregates
        qs = super().get_queryset(request)
        return qs.annotate(
            num_aggregates = models.Count('aggregate')
        )

    def event_type_formatted(self, obj):
        return format_html('<code>{}</code>', obj.event_type)
    event_type_formatted.short_description = 'event type'

    def target_ctype_formatted(self, obj):
        # Display the full label for the content type
        return format_html(
            '<code>{}.{}</code>',
            obj.target_ctype.app_label,
            obj.target_ctype.model
        )
    target_ctype_formatted.short_description = 'target ctype'

    def target_link(self, obj):
        return _make_link(obj.target_ctype, obj.target_id)
    target_link.short_description = 'target id'

    def num_aggregates(self, obj):
        return obj.num_aggregates
    num_aggregates.short_description = '# aggregates'

    def data_formatted(self, obj):
        return format_html(
            '<pre>{}</pre>',
            json.dumps(obj.data, indent = 2, sort_keys = True)
        )
    data_formatted.short_description = 'data'

    def user_link(self, obj):
        if obj.user:
            return _make_link(obj.user)
    user_link.short_description = 'user'

    # Disallow all edit permissions
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj = None):
        return False

    def has_delete_permission(self, request, obj = None):
        return False
