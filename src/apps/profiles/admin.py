from django.contrib import admin
from .models import ContactMessage, ProfileSetting

# Register your models here.
class ContactMessageAdmin(admin.ModelAdmin):
    readonly_fields = (
        'name', 
        'email',
        'topic',
        'message',
        'has_user_agreed_tos',
        )
    list_display = ('name', 'email', 'topic', 'status')
    list_filter = ('status', 'topic')
admin.site.register(ContactMessage, ContactMessageAdmin)

class ProfileSettingsAdmin(admin.ModelAdmin):
    readonly_fields = ('user', 'email_notifications', 'generation_notifications', 'viral_alert_notifications')

admin.site.register(ProfileSetting, ProfileSettingsAdmin)