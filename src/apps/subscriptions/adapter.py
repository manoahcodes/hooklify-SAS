from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import resolve_url
from apps.subscriptions.models import Subscriber
from apps.webhook.handlers.webhook_subscriptions import get_free_plan_details

class AllAuthAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit)
        free_product, free_price = get_free_plan_details()
        Subscriber.objects.get_or_create(
            user=user,
            subscription=free_product,
            price=free_price
        )
        return user
    
    # def get_login_redirect_url(self, request):
    #     user = request.user
    #     if not user.first_name or not user.last_name:
    #         return resolve_url('user_profile')  # redirect to profile setup
    #     return resolve_url('dashboard')


class AllAuthSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        free_product, free_price = get_free_plan_details()
        Subscriber.objects.get_or_create(
            user=user,
            subscription=free_product,
            price=free_price
        )
        return user