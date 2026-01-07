from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

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
    context = {

    }
    return render(request, 'account/profile/profile.html', context)