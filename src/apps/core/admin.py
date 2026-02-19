from django.contrib import admin
from apps.core.models import (
    Audience, AgeGroup,
    Tone, Style,
    Niche, SubNiche, Region, ReferenceLink,
    Platform, VideoDuration, Generation,
    Notification, Outcome
    )
from apps.core.services import send_system_broadcast

# Register your models here.
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'category', 'is_read', 'created_at')
    list_filter = ('category', 'is_read')
    search_fields = ('recipient__username', 'title')

    # Custom Action: Send to All Users (This adds a button in the admin)
    actions = ['broadcast_to_everyone']

    @admin.action(description='Broadcast this message content to ALL users')
    def broadcast_to_everyone(self, request, queryset):
        # We take the first selected notification as a "Template"
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one notification to use as a template.", level='error')
            return

        template = queryset.first()
        
        send_system_broadcast(
            title=template.title,
            message=template.message,
            link=template.external_link,
            category=template.category
        )
        
        self.message_user(request, "Broadcast queued successfully!", level='success')

admin.site.register(Audience)
admin.site.register(VideoDuration)
admin.site.register(Platform)
admin.site.register(AgeGroup)
admin.site.register(Tone)
admin.site.register(Style)
admin.site.register(Niche)
admin.site.register(SubNiche)
admin.site.register(Region)
admin.site.register(ReferenceLink)

class GenerationAdmin(admin.ModelAdmin):
    readonly_fields = (
        'user', 
        'title',
        'platform',
        'niche',
        'sub_niche',
        'video_duration', 
        'country', 
        'target_audiences',
        'age_groups',
        'desired_tones',
        'visual_styles',
        'endgoal', 
        'video_reference_url', 
        'core_concept',
        'generate_hooks',
        'generate_scripts',
        'generate_cta',
        'created_at',        
        'updated_at',
        )
    list_filter = ('niche',)

admin.site.register(Generation, GenerationAdmin)
admin.site.register(Outcome)


