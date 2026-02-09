from django.contrib import admin
from apps.core.models import (
    Audience, AgeGroup,
    Tone, Style,
    Niche, SubNiche, Region, ReferenceLink,
    Platform, VideoDuration, Generation
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
admin.site.register(Generation)
