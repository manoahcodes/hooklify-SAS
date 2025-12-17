from django.contrib import admin
from .models import ContactMessage

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