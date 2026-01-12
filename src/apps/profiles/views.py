from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from allauth.socialaccount.models import SocialAccount

from apps.profiles.models import ContactMessage, ContactChoices

# Create your views here.
def contact_view(request):
    topic = ContactChoices.choices
    context = {
        'form': topic
    }
    return render(request, 'home/contact.html', context)

def contact_info(request):
    topic = ContactChoices.choices
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

    