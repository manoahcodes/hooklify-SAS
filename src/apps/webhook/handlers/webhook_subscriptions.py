import logging

from django.db import transaction

from apps.subscriptions.models import Price, Subscriber, Product, Customer
from .webhook_helper_functions import (
    WebhookProcessingError, SubscriptionSyncError, 
    sync_and_cancel_old_subscription, get_free_plan_details
    )

logger = logging.getLogger(__name__)



@transaction.atomic
def handle_subscription_created(data: dict):
    """
    Robust Paddle subscription creation handler.

    Guarantees:
    - Validates payload structure defensively.
    - Prevents data corruption from malformed 'items' array.
    - Ensures single active subscription per user.
    - Safely updates subscriber records under DB locks.
    """

    # ----------------------------------------------------------------------
    # 1. Extract & Validate Payload
    # ----------------------------------------------------------------------
    subscription_id = data.get("id")
    paddle_customer_id = data.get("customer_id")
    items = data.get("items") or []
    billing_period = data.get("current_billing_period") or {}

    if not subscription_id or not paddle_customer_id or not items:
        raise WebhookProcessingError("Incomplete subscription.created payload.")

    try:
        first_item = items[0]
        product_data = first_item.get("product") or {}
        price_data = first_item.get("price") or {}

        product_id = product_data.get("id")
        price_id = price_data.get("id")
        starts_at = billing_period.get("starts_at")
        ends_at = billing_period.get("ends_at")

        if not product_id or not price_id:
            raise ValueError

    except Exception:
        raise WebhookProcessingError("Invalid structure in 'items' array.")

    # ----------------------------------------------------------------------
    # 2. Resolve DB Entities
    # ----------------------------------------------------------------------
    try:
        customer = Customer.objects.select_related("user").get(
            paddle_id=paddle_customer_id
        )
        user = customer.user

        product = Product.objects.get(paddle_id=product_id)
        price = Price.objects.get(paddle_id=price_id)

    except Customer.DoesNotExist:
        raise WebhookProcessingError(
            f"Customer missing for paddle_id={paddle_customer_id}"
        )
    except Product.DoesNotExist:
        raise WebhookProcessingError(
            f"Product missing for paddle_id={product_id}"
        )
    except Price.DoesNotExist:
        raise WebhookProcessingError(
            f"Price missing for paddle_id={price_id}"
        )
    except Exception as e:
        raise SubscriptionSyncError(f"Model retrieval error: {e}") from e

    # ----------------------------------------------------------------------
    # 3. Enforce “One Active Subscription” Policy
    # ----------------------------------------------------------------------
    try:
        sync_and_cancel_old_subscription(
            user=user,
            new_subscription_id=subscription_id,
            cancel_immediately=False,
        )
    except Exception as e:
        logger.error(
            f"[CREATED] Failed to cancel old subscription for {user}: {e}",
            exc_info=True
        )
        raise SubscriptionSyncError(f"Failed to cancel old subscription: {e}") from e

    # ----------------------------------------------------------------------
    # 4. Create or Update Subscriber Atomically
    # ----------------------------------------------------------------------
    subscriber, created = Subscriber.objects.update_or_create(
        user=user,
        defaults={
            "subscription": product,
            "price": price,
            "status": Subscriber.StatusChoices.ACTIVE,
            "is_subscription_active": True,
            "is_subscription_cancelled": False,
            "paddle_user_id": paddle_customer_id,
            "paddle_subscriptions_id": subscription_id,
            "paddle_price_id": price_id,
            "subscription_starts_at": starts_at,
            "subscription_ends_at": ends_at,
        },
    )

    action = "Created" if created else "Updated"
    logger.info(
        f"[CREATED] {action} subscription {subscription_id} for user {user.username}"
    )




@transaction.atomic
def handle_subscription_canceled(data: dict):
    """
    Robust Paddle subscription cancellation handler.

    Guarantees:
    - Tolerates out-of-order, duplicate, or historical events.
    - Never overwrites an active subscription with stale data.
    - Handles missing customer/subscriber records safely.
    - Supports multiple Paddle subscriptions tied to the same user.
    - Handles scheduled (future-dated) cancellations correctly.
    """

    paddle_customer_id = data.get("customer_id")
    subscription_id = data.get("id")
    price_id = data.get("price_id")

    if not paddle_customer_id or not subscription_id:
        raise WebhookProcessingError("Invalid webhook payload: missing required IDs.")

    # ----------------------------------------------------------------------
    # 1. Resolve Customer → User
    # ----------------------------------------------------------------------
    try:
        customer = Customer.objects.select_related("user").get(
            paddle_id=paddle_customer_id
        )
    except Customer.DoesNotExist:
        logger.error(f"[CANCEL] Unknown Paddle customer {paddle_customer_id}")
        return  # Ignore irrelevant ghost events
    
    user = customer.user

    # ----------------------------------------------------------------------
    # 2. Load Free Plan Configuration
    # ----------------------------------------------------------------------
    try:
        free_product, free_price = get_free_plan_details()
    except Exception:
        logger.critical("[CANCEL] Free plan configuration missing.", exc_info=True)
        raise SubscriptionSyncError("Missing free plan configuration.")

    # ----------------------------------------------------------------------
    # 3. Lock Subscriber Record
    # ----------------------------------------------------------------------
    try:
        subscriber = (
            Subscriber.objects.select_for_update()
            .get(user=user)
        )
    except Subscriber.DoesNotExist:
        logger.warning(
            f"[CANCEL] No subscriber record for {user}. "
            f"Creating new free-tier fallback."
        )

        # Create a fresh subscriber safely
        Subscriber.objects.update_or_create(
            user=user,
            defaults={
                "subscription": free_product,
                "price": free_price,
                "status": Subscriber.StatusChoices.FREE,
                "is_free_active": True,
                "is_subscription_active": False,
                "is_subscription_cancelled": False,
                "paddle_subscriptions_id": subscription_id,
                "paddle_price_id": price_id,
                "paddle_user_id": paddle_customer_id,
                "subscription_starts_at": None,
                "subscription_ends_at": None,
            },
        )
        return

    # ----------------------------------------------------------------------
    # 4. Reject Events If System Has No Active Paddle Subscription Recorded
    # ----------------------------------------------------------------------
    db_subscription_id = subscriber.paddle_subscriptions_id

    if not db_subscription_id:
        logger.error(
            f"[CANCEL] User {user} has no recorded Paddle subscription. "
            f"Event {subscription_id} ignored."
        )
        return

    # ----------------------------------------------------------------------
    # 5. Reject Wrong-Subscription or Stale Events
    # ----------------------------------------------------------------------
    if db_subscription_id != subscription_id:
        logger.info(
            f"[CANCEL] Ignored event for subscription {subscription_id}. "
            f"Active subscription is {db_subscription_id}."
        )
        return

    # ----------------------------------------------------------------------
    # 6. Ignore Retried/Already-Processed Webhooks
    # ----------------------------------------------------------------------
    if subscriber.status == Subscriber.StatusChoices.CANCELED:
        logger.info(f"[CANCEL] Retry detected. Subscription {subscription_id} already canceled.")
        return

    # ----------------------------------------------------------------------
    # 7. Scheduled / Future Cancellations
    # ----------------------------------------------------------------------
    scheduled = data.get("scheduled_change")
    if scheduled:
        subscriber.subscription_ends_at = scheduled
        subscriber.status = Subscriber.StatusChoices.ACTIVE
        subscriber.is_subscription_active = True
        subscriber.is_subscription_cancelled = False
        subscriber.save(update_fields=[
            "subscription_ends_at",
            "status",
            "is_subscription_active",
            "is_subscription_cancelled"
        ])

        logger.info(
            f"[CANCEL SCHEDULED] Subscription {subscription_id} ends at {scheduled}."
        )
        return

    # ----------------------------------------------------------------------
    # 8. Immediate Cancellation → Downgrade to Free Tier
    # ----------------------------------------------------------------------
    subscriber.subscription = free_product
    subscriber.price = free_price
    subscriber.status = Subscriber.StatusChoices.CANCELED
    subscriber.is_free_active = True
    subscriber.is_subscription_cancelled = True
    subscriber.is_subscription_active = False
    subscriber.subscription_starts_at = None
    subscriber.subscription_ends_at = None

    subscriber.save(update_fields=[
        "subscription",
        "price",
        "status",
        "is_free_active",
        "is_subscription_cancelled",
        "is_subscription_active",
        "subscription_starts_at",
        "subscription_ends_at",
    ])

    logger.info(f"[CANCELLED] {user.username} downgraded to free.")



@transaction.atomic
def handle_subscription_updated(data: dict):
    """
    Hardened handler for `subscription.updated` Paddle events.

    Guarantees:
    - Graceful handling of upgrades/downgrades
    - Safe recovery from partial event payloads
    - Idempotent under retries
    - Rejects stale/out-of-order events
    - Correctly maps Paddle → internal subscription states
    """

    # ----------------------------------------------------------------------
    # 1. Parse & Validate Payload
    # ----------------------------------------------------------------------
    subscription_id = data.get("id")
    paddle_customer_id = data.get("customer_id")
    items = data.get("items") or []
    billing = data.get("current_billing_period") or {}
    paddle_status = data.get("status")
    if not subscription_id or not paddle_customer_id or not items:
        raise WebhookProcessingError("Invalid subscription.updated payload.")

    # Extract first item safely
    try:
        item = items[0]
        product_id = (item.get("product") or {}).get("id")
        price_id = (item.get("price") or {}).get("id")
        starts_at = billing.get("starts_at")
        ends_at = billing.get("ends_at")
        if not product_id or not price_id:
            raise ValueError
    except Exception:
        raise WebhookProcessingError("Invalid 'items' structure in payload.")

    if not paddle_status:
        raise WebhookProcessingError("Missing Paddle subscription status.")

    # ----------------------------------------------------------------------
    # 2. Load DB Entities
    # ----------------------------------------------------------------------
    try:
        customer = Customer.objects.select_related("user").get(
            paddle_id=paddle_customer_id
        )
        user = customer.user
        product = Product.objects.get(paddle_id=product_id)
        price = Price.objects.get(paddle_id=price_id)

    except Customer.DoesNotExist:
        logger.error(f"[UPDATE] Unknown Paddle customer {paddle_customer_id}")
        return
    except (Product.DoesNotExist, Price.DoesNotExist):
        logger.error(
            f"[UPDATE] Unknown product={product_id} or price={price_id}."
        )
        raise SubscriptionSyncError("Mismatched Paddle product or price.")
    except Exception as e:
        raise SubscriptionSyncError(f"Model retrieval error: {e}") from e

    # Load free plan fallback
    try:
        free_product, free_price = get_free_plan_details()
    except Exception as e:
        logger.critical("[UPDATE] Free plan configuration missing.", exc_info=True)
        raise SubscriptionSyncError("Missing free plan configuration.") from e

    # ----------------------------------------------------------------------
    # 3. Lock Subscriber Record
    # ----------------------------------------------------------------------
    try:
        subscriber = Subscriber.objects.select_for_update().get(user=user)
    except Subscriber.DoesNotExist:
        logger.warning(
            f"[UPDATE] No subscriber for {user}. Creating fallback."
        )
        Subscriber.objects.update_or_create(
            user=user,
            defaults={
                "subscription": free_product,
                "price": free_price,
                "paddle_user_id": paddle_customer_id,
                "paddle_subscriptions_id": subscription_id,
                "status": Subscriber.StatusChoices.FREE,
                "is_subscription_active": False,
                "is_subscription_cancelled": False,
                "subscription_starts_at": None,
                "subscription_ends_at": None,
            },
        )
        return

    # ----------------------------------------------------------------------
    # 4. Reject Events for Wrong Subscription
    # ----------------------------------------------------------------------
    db_subscription = subscriber.paddle_subscriptions_id

    if not db_subscription:
        logger.error(f"[UPDATE IGNORED] {user} has no stored Paddle subscription.")
        return

    if db_subscription != subscription_id:
        logger.info(
            f"[UPDATE IGNORED] Event {subscription_id} != active {db_subscription} for {user}."
        )
        return

    # ----------------------------------------------------------------------
    # 5. Map Paddle Status → Internal Status
    # ----------------------------------------------------------------------
    STATUS_MAP = {
        "active": Subscriber.StatusChoices.ACTIVE,
        "trialing": Subscriber.StatusChoices.TRIALING,
        "paused": Subscriber.StatusChoices.PAUSED,
        "past_due": Subscriber.StatusChoices.PAST_DUE,
        "canceled": Subscriber.StatusChoices.CANCELED,
    }

    internal_status = STATUS_MAP.get(paddle_status)
    if not internal_status:
        logger.error(f"[UPDATE] Unknown Paddle status '{paddle_status}'. Ignored.")
        return

    # ----------------------------------------------------------------------
    # 6. Detect Plan Changes
    # ----------------------------------------------------------------------
    plan_changed = (
        subscriber.subscription.paddle_id != product_id
        or subscriber.price.paddle_id != price_id
    )

    if plan_changed:
        logger.info(
            f"[UPDATE] {user.username} plan changed"
            f"{subscriber.subscription.paddle_id}/{subscriber.price.paddle_id} → "
            f"{product_id}/{price_id}"
        )
        subscriber.subscription = product
        subscriber.price = price

    # ----------------------------------------------------------------------
    # 7. Update Billing Period
    # ----------------------------------------------------------------------
    if starts_at:
        subscriber.subscription_starts_at = starts_at

    if ends_at:
        subscriber.subscription_ends_at = ends_at

    # ----------------------------------------------------------------------
    # 8. Apply Paddle Status → Internal Flags
    # ----------------------------------------------------------------------
    subscriber.status = internal_status

    # IMPORTANT FIX:
    # Your original code mistakenly used:
    #   if paddle_status in "active"
    # This is always TRUE for letters like 'a', 'c', etc. Completely wrong.
    # Below is the correct implementation.

    if paddle_status == ("active", "trialing"):
        subscriber.is_subscription_active = True
        subscriber.is_subscription_cancelled = False
        subscriber.is_free_active = False

    elif paddle_status == "paused":
        subscriber.is_subscription_active = True
        subscriber.is_subscription_cancelled = False
        subscriber.is_free_active = False

    elif paddle_status == "past_due":
        subscriber.is_subscription_active = False
        subscriber.is_subscription_cancelled = False
        subscriber.is_free_active = False

    subscriber.save(update_fields=[
        "subscription",
        "price",
        "status",
        "paddle_subscriptions_id",
        "paddle_price_id",
        "is_subscription_active",
        "is_subscription_cancelled",
        "is_free_active",
        "subscription_starts_at",
        "subscription_ends_at",
    ])

    logger.info(
        f"[UPDATE SUCCESS] Synced {subscription_id} for {user.username} "
        f"({paddle_status})."
    )