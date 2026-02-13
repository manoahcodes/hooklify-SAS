import json
import logging

from django.utils import timezone
from django.db import transaction, IntegrityError
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


from decouple import config
from paddle_billing.Notifications import Secret, Verifier

from apps.webhook.models import WebhookEvents
from apps.core.models import Notification
from apps.webhook.handlers.webhook_subscriptions import (
    handle_subscription_created, handle_subscription_updated, 
    handle_subscription_canceled, handle_transaction_completed,
    handle_transaction_failed, WebhookProcessingError
    )

logger = logging.getLogger(__name__)

PADDLE_WEBHOOK_SECRET_SUBSCRIPTION_KEY = config("PADDLE_WEBHOOK_SUBSCRIPTION_SECRET_KEY", cast=str)

# Create your views here.

@csrf_exempt
@require_POST
def paddle_subscription_webhook(request):
    """ 
    Handles all Paddle subscription webhooks. 
    Delegates business logic to service functions. 
    """

    try:
        if not Verifier().verify(request, Secret(str(PADDLE_WEBHOOK_SECRET_SUBSCRIPTION_KEY))):
            return HttpResponse("Invalid signature", status=400)
    except Exception:
        return HttpResponse("Signature verification error", status=400)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    event_id = payload.get("event_id")
    event_type = payload.get("event_type")
    data = payload.get("data", {})

    if not event_id or not event_type:
        return JsonResponse({"error": "Missing event metadata"}, status=400)

    # --------- IDEMPOTENCY GUARD ----------
    try:
        with transaction.atomic():
            WebhookEvents.objects.create(
                event_id=event_id,
                event_type=event_type,
            )
    except IntegrityError:
        logger.info(f"[WEBHOOK DUPLICATE] {event_id}")
        return JsonResponse({"status": "duplicate"}, status=200)
    # -------------------------------------

    try:
        if event_type == "subscription.created":
            handle_subscription_created(data)
            


        elif event_type == "subscription.updated":
            handle_subscription_updated(data)

        elif event_type == "subscription.canceled":
            handle_subscription_canceled(data)

        elif event_type == "transaction.completed":
            handle_transaction_completed(data)

        elif event_type == "transaction.payment_failed":
            handle_transaction_failed(data)

        else:
            return JsonResponse({"status": "ignored"}, status=200)

    except WebhookProcessingError as e:
        return JsonResponse({"error": str(e)}, status=400)

    except Exception as e:
        logger.error("Webhook processing failed", exc_info=True)
        raise  # allow retry

    WebhookEvents.objects.filter(event_id=event_id).update(
        processed_at=timezone.now()
    )

    return JsonResponse({"status": "success"}, status=200)
