from django.contrib import admin
from apps.core.models import (
    Audience, AgeGroup, VideoScriptParams, 
    Tone, Style, GeneratedScript, 
    Niche, SubNiche, Country, ReferenceLink,
    Platform
    )

# Register your models here.
admin.site.register(Audience)
admin.site.register(Platform)
admin.site.register(AgeGroup)
admin.site.register(VideoScriptParams)
admin.site.register(Tone)
admin.site.register(Style)
admin.site.register(GeneratedScript)
admin.site.register(Niche)
admin.site.register(SubNiche)
admin.site.register(Country)
admin.site.register(ReferenceLink)
