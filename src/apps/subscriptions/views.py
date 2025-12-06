from django.shortcuts import render
from django.urls import reverse
from django.contrib.auth.decorators import login_required

from apps.subscriptions.models import Price, Subscriber, Customer

# Create your views here.
def plans_view(request, interval="monthly"):
    subpri_qs = Price.objects.filter(
        subscription__active=True,
        featured=True,
    ).select_related('subscription').order_by(
        'subscription__order', 'order'
    )

    monthly = Price.IntervalChoices.MONTHLY
    yearly = Price.IntervalChoices.YEARLY
    free = Price.IntervalChoices.FREE

    # Check availability of each interval
    has_monthly = subpri_qs.filter(interval=monthly).exists()
    has_yearly = subpri_qs.filter(interval=yearly).exists()

    # Build URLs only for existing intervals
    namepath = 'plans_interval'
    mo_url = reverse(namepath, kwargs={"interval": "monthly"}) if has_monthly else None
    yr_url = reverse(namepath, kwargs={"interval": "yearly"}) if has_yearly else None

    # If only one option exists → force interval to that one
    if has_monthly and not has_yearly:
        interval = "monthly"
    elif has_yearly and not has_monthly:
        interval = "yearly"

    # Determine active plans
    if interval == "yearly" and has_yearly:
        active = "yearly"
        object_list = subpri_qs.filter(interval=yearly)
    else:
        active = "monthly"
        object_list = subpri_qs.filter(interval=monthly)

    # Append free plans
    free_plans = subpri_qs.filter(interval=free)
    object_list = (object_list | free_plans).distinct()

    # Grab active user subscription
    user_subscription = None
    if request.user.is_authenticated:
        user_subscription = (
            Subscriber.objects
            .filter(user=request.user)
            .select_related("price", "price__subscription")
            .first()
        )


    # Show toggle buttons only if both exist
    show_toggle = has_monthly and has_yearly

    return render(request, "subscriptions/pricing.html", {
        "yr_url": yr_url,
        "mo_url": mo_url,
        "plans_list": object_list,
        "user_subscription": user_subscription,
        "active": active,
        "show_toggle": show_toggle,
    })