from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect

from allauth.socialaccount.models import SocialAccount

from apps.profiles.models import ContactMessage, ProfileSetting
from apps.subscriptions.models import Subscriber

from paddle_billing.Entities.Subscriptions import SubscriptionEffectiveFrom
from utils.billing import get_subscription_plan, cancel_subscription

# Create your views here.
@login_required
def cancel_sub(request):
    user = request.user
    sub_obj = (
        Subscriber.objects
        .select_related("subscription", "price")
        .filter(user=user)
        .first())

    # No subscription at all
    if not sub_obj:
        messages.error(request, "No active subscription found.")
        print("No active subscription found.")
        return redirect("dashboard")

    # Already canceled — do nothing
    if sub_obj.status == "canceled":
        messages.info(request, "Your subscription is already canceled.")
        print("Your subscription is already canceled.")
        return redirect("dashboard")

    # No Paddle subscription ID — can't cancel remotely
    if not sub_obj.paddle_subscriptions_id:
        messages.error(request, "Unable to cancel subscription. Please contact support.")
        print("Unable to cancel subscription. Please contact support.")
        return redirect("dashboard")

    try:
        # Cancel at end of billing period
        cancel_subscription(
            sub_id=sub_obj.paddle_subscriptions_id,
            effective_from=SubscriptionEffectiveFrom.NextBillingPeriod,
            raw=False
        )

        messages.success(
            request,
            "Your subscription will remain active until the end of the current billing period."
        )

    except Exception as e:
        # Log this in real life
        print(e)
        messages.error(
            request,
            "Something went wrong while canceling your subscription. Please try again."
        )
        print("Something went wrong while canceling your subscription. Please try again.")

    return redirect("dashboard")


@csrf_protect
@require_POST
def contact_info(request):
    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    topic = request.POST.get("topic", "").strip()
    message = request.POST.get("message", "").strip()
    tos = request.POST.get("tos")

    # 1️⃣ Hard validation (fail fast)
    if not all([name, email, topic, message]):
        messages.error(request, "All fields are required.")
        return redirect("contact")

    if not tos:
        messages.error(request, "You must agree to the terms to continue.")
        return redirect("contact")

    try:
        ContactMessage.objects.create(
            name=name,
            email=email,
            topic=topic,
            message=message,
            has_user_agreed_tos=True,
        )

        messages.success(request, "Your message has been sent successfully!")

    except Exception:
        # Log exception in real systems
        messages.error(
            request,
            "Something went wrong while sending your message. Please try again."
        )

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
    settings_obj, _ = ProfileSetting.objects.get_or_create(user=user)

    if request.method == "POST":
        settings_obj.email_notifications = "email_notifications" in request.POST
        settings_obj.generation_notifications = "generation_notifications" in request.POST
        settings_obj.viral_alert_notifications = "viral_alert_notifications" in request.POST

        settings_obj.save()

        messages.success(request, "Settings updated successfully.")
        return redirect("profile_settings")

    return render(request, "account/profile/settings.html", {"settings": settings_obj})


@login_required
def billing_view(request):
    user = request.user
    sub_obj = (Subscriber.objects.select_related("subscription", "price").filter(user=user).first())

    # ---- NO SUBSCRIPTION → FREE PLAN ----
    if not sub_obj:
        return render(
            request,
            "account/profile/billing.html",
            {
                "subscription": "Free Plan",
                "status": "FREE",
                "is_active_subscription": False,
                "is_past_due": False,
                "is_paused": False,
                "is_inactive": True,
            }
        )

    status = sub_obj.status.upper()

    # ---- STATUS FLAGS ----
    is_active_subscription = status in {"ACTIVE", "TRIALING"}
    is_past_due = status == "PAST_DUE"
    is_paused = status == "PAUSED"
    inactive = status in {"FREE", "CANCELED"}

    paddle_url = None

    # ---- ONLY HIT PADDLE IF SUB IS MANAGEABLE ----
    if sub_obj.paddle_subscriptions_id and not inactive:
        try:
            ctm_params = get_subscription_plan(
                sub_id=sub_obj.paddle_subscriptions_id
            )
            paddle_url = ctm_params.management_urls.update_payment_method
        except Exception:
            paddle_url = None
            messages.warning(
                request,
                "We couldn't load your subscription management link. Please try again later."
            )

    context = {
        "subscription": f"{sub_obj.subscription.name} Plan",
        "next_bill": sub_obj.subscription_ends_at,
        "renewal": sub_obj.price.interval,
        "price": sub_obj.price.price,
        "status": status,
        "paddle_url": paddle_url,
        "is_active_subscription": is_active_subscription,
        "is_past_due": is_past_due,
        "is_paused": is_paused,
        "inactive": inactive,
    }

    return render(request, "account/profile/billing.html", context)