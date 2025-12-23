from django.shortcuts import render

# Custom Error Handlers
def custom_404_view(request, exception):
    return render(request, '404.html', status=404)

def custom_500_view(request):
    return render(request, '500.html', status=500)

# View Functions
def index(request):
    return render(request, 'landing.html')

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