from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
# from django.shortcuts import resolve_url

from apps.profiles.models import ProfileSetting

class AllAuthProfilesettingsAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit)
        ProfileSetting.objects.create(user=user)
        return user


class AllAuthSocialProfileSettingsAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        ProfileSetting.objects.create(user=user)
        return user