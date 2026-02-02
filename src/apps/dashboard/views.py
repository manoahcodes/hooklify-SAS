from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from apps.subscriptions.models import Subscriber

# Create your views here.

def _render_page(request, full_template, partial_template, context=None):
    context = context or {}
    if getattr(request, "htmx", False):
        return render(request, partial_template, context)
    return render(request, full_template, context)

@login_required
def dashboard(request):
    return render(request, 'dashboard/pages/dashboard.html')

@login_required
def ideas(request):
    return render(request, 'dashboard/pages/ideas.html')

@login_required
def create(request):
    return render(request, 'dashboard/pages/create.html')

@login_required
def projects(request):
    return render(request, 'dashboard/pages/projects.html')
