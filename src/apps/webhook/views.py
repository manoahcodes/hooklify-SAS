import json
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from decouple import config
from paddle_billing.Notifications import Secret, Verifier

from .handlers.webhook_subscriptions import (
    handle_subscription_created, handle_subscription_updated, 
    handle_subscription_cancelled, handle_subscription_status_changed, 
    WebhookProcessingError
    )

logger = logging.getLogger(__name__)

# Create your views here.
PADDLE_WEBHOOK_SECRET_SUBSCRIPTION_KEY = config("PADDLE_WEBHOOK_SUBSCRIPTION_SECRET_KEY", default="", cast=str)


@csrf_exempt
@require_POST
def paddle_subscription_webhook(request):
    """
    Handles all Paddle subscription webhooks.
    Delegates business logic to service functions.
    """

    # 1. Verify webhook signature
    try:
        if not Verifier().verify(request, Secret(PADDLE_WEBHOOK_SECRET_SUBSCRIPTION_KEY)):
            logger.warning("Invalid webhook signature received.")
            return HttpResponse("Invalid signature", status=400)
    except Exception as e:
        # Catch potential errors from the verifier itself
        logger.error(f"Webhook signature verification failed: {str(e)}")
        return HttpResponse("Signature verification error", status=400)

    # 2. Parse incoming JSON
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON payload received.")
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    event_type = payload.get("event_type")
    data = payload.get("data", {})
    
    logger.info(f"Received Paddle webhook event: {event_type}")

    # 3. Delegate to the correct service based on event type
    try:
        if event_type == "subscription.created":
            handle_subscription_created(data)
            
        elif event_type == "subscription.updated":
            handle_subscription_updated(data)
            
        elif event_type == "subscription.canceled":
            handle_subscription_cancelled(data)

        elif event_type in {"subscription.activated", "subscription.paused", "subscription.past_due", "subscription.resumed", "subscription.trialing"}:
            handle_subscription_status_changed({**data, "event_type": event_type})
            
        else:
            # We don't handle this event, but it's not an error.
            # Return 200 so Paddle stops sending it.
            return JsonResponse({"status": f"Unhandled event type: {event_type}"}, status=200)

    except WebhookProcessingError as e:
        # This is a "known" error (e.g., Customer not found, bad data).
        # We return a 400 so Paddle knows the data is bad and won't retry.
        logger.warning(f"Webhook processing error (400): {str(e)}")
        return JsonResponse({"error": str(e)}, status=400)
    
    except Exception as e:
        # This is an "unknown" error (e.g., database down, API failed).
        # We return a 500 so Paddle *will* retry sending the webhook.
        logger.error(f"Webhook processing failed unexpectedly (500): {str(e)}", exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)

    # 4. Success
    logger.info(f"Successfully processed event: {event_type}")
    return JsonResponse({"status": "success"}, status=200)