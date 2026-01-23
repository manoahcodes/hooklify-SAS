from django.contrib import admin
from apps.webhook.models import WebhookEvents

# Register your models here.
class WebhookEventsAdmin(admin.ModelAdmin):
    readonly_fields = (
        'event_id', 
        'event_type',
        'received_at',
        'processed_at',
        )
    list_display = ('event_type', 'event_id', 'processed_at')

admin.site.register(WebhookEvents, WebhookEventsAdmin)
