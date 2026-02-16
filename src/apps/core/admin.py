from django.contrib import admin
from apps.core.models import (
    Audience, AgeGroup,
    Tone, Style,
    Niche, SubNiche, Region, ReferenceLink,
    Platform, VideoDuration, Generation,
    Notification, Outcome
    )

# Register your models here.
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
admin.site.register(Notification)
admin.site.register(Outcome)


