import json

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType

from django_admin_listfilter_dropdown.filters import DropdownFilter, RelatedDropdownFilter

from rangefilter.filter import DateRangeFilter

from .models import Event


class ContentTypeFilter(RelatedDropdownFilter):
    """
    Related filter for content types that includes the app label.
    """
    def field_choices(self, field, request, model_admin):
        return tuple(
            (ct.pk, '{}.{}'.format(ct.app_label, ct.model))
            for ct in ContentType.objects.all()
        )


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'event_type_formatted',
        'target_ctype_formatted',
        'target_id_link',
        'user_link',
        'created_at'
    )
    list_filter = (
        ('event_type', DropdownFilter),
        ('target_ctype', ContentTypeFilter),
        ('user', RelatedDropdownFilter),
        ('created_at', DateRangeFilter),
    )
    date_hierarchy = 'created_at'
    # Use readonly fields and exclude to format the fields nicely
    readonly_fields = (
        'id',
        'event_type_formatted',
        'target_ctype_formatted',
        'target_id_link',
        'data_formatted',
        'user_link',
        'created_at'
    )
    exclude = ('event_type', 'target_ctype', 'target_id', 'data', 'user')

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

    def target_id_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse(
                'admin:{}_{}_change'.format(obj.target_ctype.app_label, obj.target_ctype.model),
                args = (obj.target_id, )
            ),
            obj.target_id
        )
    target_id_link.short_description = 'target id'

    def data_formatted(self, obj):
        return format_html(
            '<pre>{}</pre>',
            json.dumps(obj.data, indent = 2, sort_keys = True)
        )
    data_formatted.short_description = 'data'

    def user_link(self, obj):
        if obj.user:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:auth_user_change', args = (obj.user.id, )),
                obj.user
            )
    user_link.short_description = 'user'

    # Disallow all edit permissions for events
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj = None):
        return False

    def has_delete_permission(self, request, obj = None):
        return False
