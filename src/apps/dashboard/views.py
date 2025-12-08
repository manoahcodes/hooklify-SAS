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
    sub = Subscriber.objects.filter(user=request.user).first()
    status = getattr(sub, 'status', 'FREE')

    context = {
        'user': request.user,
        'subscription_status': status,
    }

    return render(request, "dashboard/base.html", context)
