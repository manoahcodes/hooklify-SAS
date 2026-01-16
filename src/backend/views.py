from django.shortcuts import render, redirect
from apps.profiles.models import ContactMessage, ContactChoices
from django.contrib import messages

# Custom Error Handlers
def custom_404_view(request, exception):
    return render(request, '404.html', status=404)

def custom_500_view(request):
    return render(request, '500.html', status=500)

# View Functions
def index(request):
    return render(request, 'landing.html')

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

def about_us_view(request):
    return render(request, 'home/about.html')

def privacy_view(request):
    return render(request, 'home/privacy.html')

def refunds_view(request):
    return render(request, 'home/refunds.html')

def terms_of_service_view(request):
    return render(request, 'home/tos.html')

def features_view(request):
    return render(request, 'home/features.html')