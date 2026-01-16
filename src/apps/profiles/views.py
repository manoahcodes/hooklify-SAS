from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from allauth.socialaccount.models import SocialAccount

from apps.profiles.models import ContactMessage, ProfileSettings

# Create your views here.
def contact_info(request):
    contact = ContactMessage.objects.create()

    if request.method == "POST":
        contact.name = request.POST.get('name', '')
        contact.email = request.POST.get('email', '')
        contact.topic = request.POST.get('topic', '')
        contact.message = request.POST.get('message', '')
        contact.has_user_agreed_tos = bool(request.POST.get('tos', ''))
        contact.save()

        messages.success(request, "Your message has been sent successfully!")
        return redirect("contact")
    
@login_required
def profile_view(request):
    user = request.user

    social_accounts = SocialAccount.objects.filter(user=user)
    has_social = social_accounts.exists()
    has_password = user.has_usable_password()

    if request.method == "POST":
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.username = request.POST.get('username', '')
        user.save()

        return redirect("profile")

    context = {
        "has_social": has_social,
        "has_password": has_password,
        "providers": [acc.provider for acc in social_accounts]
    }

    return render(request, 'account/profile/profile.html', context)


@login_required
def profile_settings_view(request):
    user = request.user
    settings_obj, _ = ProfileSettings.objects.get_or_create(user=user)

    if request.method == "POST":
        settings_obj.email_notifications = "email_notifications" in request.POST
        settings_obj.generation_notifications = "generation_notifications" in request.POST
        settings_obj.viral_alert_notifications = "viral_alert_notifications" in request.POST
        settings_obj.low_credits_notifications = "low_credits_notifications" in request.POST

        settings_obj.save()  # ← THIS IS NON-NEGOTIABLE

        messages.success(request, "Settings updated successfully.")
        return redirect("profile_settings")  # PRG pattern

    return render(request, "account/profile/settings.html", {"settings": settings_obj})