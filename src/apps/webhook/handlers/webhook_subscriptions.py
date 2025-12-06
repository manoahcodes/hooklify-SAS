import logging

from django.db import transaction

from apps.subscriptions.models import Price, Subscriber, Product, Customer
from .webhook_helper_functions import (
    WebhookProcessingError, SubscriptionSyncError, 
    sync_and_cancel_old_subscription, get_free_plan_details
    )

logger = logging.getLogger(__name__)

@transaction.atomic
def handle_subscription_created(data):
    """
    Handle the 'subscription.created' webhook event.

    Steps:
    1. Parse and validate incoming data.
    2. Lookup corresponding database entities.
    3. Cancel any existing active subscription (single subscription rule).
    4. Create or update the subscriber record atomically.
    """
    # Step 1: Validation and parsing
    subscription_id = data.get("id")
    paddle_customer_id = data.get("customer_id")
    items = data.get("items")
    current_billing_period = data.get("current_billing_period", {})

    if not (subscription_id and paddle_customer_id and items):
        raise WebhookProcessingError("Missing required subscription data.")

    try:
        first_item = items[0]
        paddle_product_id = first_item.get("product", {}).get("id")
        paddle_price_id = first_item.get("price", {}).get("id")
        starts_at = current_billing_period.get("starts_at")
        ends_at = current_billing_period.get("ends_at")
    except (IndexError, AttributeError) as e:
        raise WebhookProcessingError("Invalid 'items' structure in payload.") from e

    if not (paddle_product_id and paddle_price_id):
        raise WebhookProcessingError("Missing product or price ID in subscription items.")

    # Step 2: Fetch DB objects
    try:
        customer = Customer.objects.get(paddle_id=paddle_customer_id)
        user = customer.user
        product = Product.objects.get(paddle_id=paddle_product_id)
        price = Price.objects.get(paddle_id=paddle_price_id)
    except Customer.DoesNotExist:
        raise WebhookProcessingError(f"Customer not found with paddle_id={paddle_customer_id}")
    except Product.DoesNotExist:
        raise WebhookProcessingError(f"Product not found with paddle_id={paddle_product_id}")
    except Price.DoesNotExist:
        raise WebhookProcessingError(f"Price not found with paddle_id={paddle_price_id}")
    except Exception as e:
        raise SubscriptionSyncError(f"Unexpected error retrieving models: {e}") from e

    # Step 3: Cancel old subscription if any
    try:
        sync_and_cancel_old_subscription(user=user, new_subscription_id=subscription_id, cancel_immediately=False)
    except Exception as e:
        logger.error(f"Failed to cancel old subscription for user {user.username}: {e}", exc_info=True)
        raise SubscriptionSyncError(f"Failed to cancel old subscription: {e}") from e

    # Step 4: Create/update new subscription
    subscriber, created = Subscriber.objects.update_or_create(
        user=user,
        defaults={
            "subscription": product,
            "price": price,
            "paddle_user_id": paddle_customer_id,
            "paddle_subscriptions_id": subscription_id,
            "paddle_price_id": paddle_price_id,
            "status": Subscriber.StatusChoices.ACTIVE,
            "is_subscription_active": True,
            "is_subscription_cancelled": False,
            "subscription_starts_at": starts_at,
            "subscription_ends_at": ends_at,
        },
    )

    if created:
        logger.info(f"Created new subscription {subscription_id} for user {user.username}.")
    else:
        logger.info(f"Updated subscription {subscription_id} for user {user.username}.")


@transaction.atomic
def handle_subscription_cancelled(data):
    """
    Hardened Paddle cancellation handler that tolerates:
    - out-of-order events
    - retry events
    - historical subscription cancellations
    - multiple Paddle subscriptions tied to same user
    - missing or stale subscriber records
    - upgraded/downgraded active subscriptions
    - delayed trial cancellations

    This handler NEVER overwrites an active subscription with outdated webhook data.
    """

    paddle_customer_id = data.get("customer_id")
    subscription_id = data.get("id")

    if not paddle_customer_id or not event_subscription_id:
        raise WebhookProcessingError("Invalid webhook payload.")

    # -------------------------------------------------------------------------
    # 1. Fetch the customer → user
    # -------------------------------------------------------------------------
    try:
        customer = Customer.objects.get(paddle_id=paddle_customer_id)
    except Customer.DoesNotExist:
        logger.error(f"CANCEL: Unknown paddle customer {paddle_customer_id}")
        return  # ignore ghost events

    user = customer.user

    # -------------------------------------------------------------------------
    # 2. Load free plan configuration
    # -------------------------------------------------------------------------
    try:
        free_product, free_price = get_free_plan_details()
    except Exception as e:
        logger.critical("CANCEL: Free plan configuration missing.", exc_info=True)
        raise SubscriptionSyncError("Missing free plan configuration.") from e

    # -------------------------------------------------------------------------
    # 3. Fetch subscriber record securely
    # -------------------------------------------------------------------------
    try:
        subscriber = (
            Subscriber.objects.select_for_update().get(user=user)
        )
    except Subscriber.DoesNotExist:
        logger.warning(f"CANCEL: No Subscriber for {user}. Creating brand-new free record.")

        return Subscriber.objects.update_or_create(
            user=user,
            subscription=free_product,
            price=free_price,
            status=Subscriber.StatusChoices.CANCELED,
            is_free_active=True,
            is_subscription_active=False,
            is_subscription_cancelled=False,
            paddle_subscriptions_id=subscription_id,  # best guess
            paddle_user_id=paddle_customer_id,
            subscription_starts_at=None,
            subscription_ends_at=None,
        )

    # -------------------------------------------------------------------------
    # 4. If user has NO Paddle subscription stored, do not blindly overwrite.
    # -------------------------------------------------------------------------
    if not subscriber.paddle_subscriptions_id:
        logger.error(
            f"CANCEL: User {user} has no recorded Paddle subscription. "
            f"Event {event_subscription_id} ignored."
        )
        return

    db_subscription_id = subscriber.paddle_subscriptions_id

    # -------------------------------------------------------------------------
    # 5. Reject cancellations for NON-ACTIVE or NON-MATCHING subscriptions.
    #    This is the biggest protection against data corruption.
    # -------------------------------------------------------------------------
    if db_subscription_id != subscription_id:
        logger.info(
            f"CANCEL IGNORED: Event {subscription_id} does not match "
            f"active subscription {db_subscription_id}."
        )
        return

    # -------------------------------------------------------------------------
    # 6. Reject cancellation if already canceled (webhook retry).
    # -------------------------------------------------------------------------
    if subscriber.status == Subscriber.StatusChoices.CANCELED:
        logger.info(f"CANCEL RETRY: {subscription_id} already canceled.")
        return

    # -------------------------------------------------------------------------
    # 7. Handle cases where Paddle marks a future-dated cancellation.
    # -------------------------------------------------------------------------
    if data.get("scheduled_change"):
        effective = data["scheduled_change"]
        subscriber.subscription_ends_at = effective  # optional but correct

        logger.info(
            f"CANCEL SCHEDULED: Subscription {subscription_id} ends at {effective}. "
            "Not downgrading yet."
        )

        subscriber.is_subscription_active = True
        subscriber.is_subscription_cancelled = False
        subscriber.status = Subscriber.StatusChoices.ACTIVE
        subscriber.save()
        return

    # -------------------------------------------------------------------------
    # 8. Handle immediate cancellation → downgrade to free
    # -------------------------------------------------------------------------
    subscriber.subscription = free_product
    subscriber.price = free_price
    subscriber.status = Subscriber.StatusChoices.CANCELED
    subscriber.is_free_active = True
    subscriber.is_subscription_cancelled = True
    subscriber.is_subscription_active = False
    subscriber.subscription_starts_at = None
    subscriber.subscription_ends_at = None
    subscriber.save()

    logger.info(f"CANCELLED: User {user.username} downgraded to free.")


@transaction.atomic
def handle_subscription_updated(data):
    """
    A hardened handler for `subscription.updated` events.

    This MUST correctly handle:
    - plan upgrades/downgrades
    - price changes
    - billing period updates
    - retry/out-of-order Paddle events
    - partial payloads
    - updates belonging to an OLD subscription (must ignore)
    """

    subscription_id = data.get("id")
    paddle_customer_id = data.get("customer_id")
    items = data.get("items")
    current_billing_period = data.get("current_billing_period", {})

    if not (subscription_id and paddle_customer_id and items):
        raise WebhookProcessingError("Invalid payload: missing subscription data.")

    # Extract item details
    try:
        item = items[0]
        paddle_product_id = item.get("product", {}).get("id")
        paddle_price_id = item.get("price", {}).get("id")
        starts_at = current_billing_period.get("starts_at")
        ends_at = current_billing_period.get("ends_at")
    except Exception:
        raise WebhookProcessingError("Invalid 'items' structure.")

    if not (paddle_product_id and paddle_price_id):
        raise WebhookProcessingError("Missing product or price info.")

    # -------------------------------------------------------------------------
    # Load models safely
    # -------------------------------------------------------------------------
    try:
        customer = Customer.objects.get(paddle_id=paddle_customer_id)
        user = customer.user
        product = Product.objects.get(paddle_id=paddle_product_id)
        price = Price.objects.get(paddle_id=paddle_price_id)
    except Customer.DoesNotExist:
        logger.error(f"UPDATE: Unknown paddle customer {paddle_customer_id}")
        return  # ghost customer → ignore
    except (Product.DoesNotExist, Price.DoesNotExist):
        logger.error(
            f"UPDATE: Payload references unknown product={paddle_product_id}, "
            f"price={paddle_price_id}. Cannot sync."
        )
        raise SubscriptionSyncError("Mismatched Paddle product or price.")
    except Exception as e:
        raise SubscriptionSyncError(f"Unexpected model retrieval error: {e}") from e
    
    try:
        free_product, free_price = get_free_plan_details()
    except Exception as e:
        logger.critical("CANCEL: Free plan configuration missing.", exc_info=True)
        raise SubscriptionSyncError("Missing free plan configuration.") from e

    # -------------------------------------------------------------------------
    # Fetch subscriber or create new free fallback if nonexistent
    # -------------------------------------------------------------------------
    try:
        subscriber = Subscriber.objects.select_for_update().get(user=user)
    except Subscriber.DoesNotExist:
        logger.warning(f"UPDATE: No subscriber exists for {user}. Creating new record.")

        return Subscriber.objects.update_or_create(
            user=user,
            subscription=free_product,
            price=free_price,
            paddle_user_id=paddle_customer_id,
            paddle_subscriptions_id=subscription_id,
            status=Subscriber.StatusChoices.FREE,
            is_subscription_active=False,
            is_subscription_cancelled=False,
            subscription_starts_at=None,
            subscription_ends_at=None,
        )

    # -------------------------------------------------------------------------
    # Only update if this webhook corresponds to the CURRENT subscription
    # -------------------------------------------------------------------------
    db_subscription_id = subscriber.paddle_subscriptions_id

    if not db_subscription_id:
        logger.error(f"UPDATE IGNORED: User {user} has no stored subscription ID.")
        return

    if db_subscription_id != subscription_id:
        logger.info(
            f"UPDATE IGNORED: Event {subscription_id} does not match active "
            f"subscription {db_subscription_id} for {user}."
        )
        return

    # -------------------------------------------------------------------------
    # Update changes safely
    # -------------------------------------------------------------------------
    previous_product = subscriber.subscription
    previous_price = subscriber.price

    # Detect plan change (upgrade/downgrade)
    plan_changed = (
        previous_product.paddle_id != paddle_product_id
        or previous_price.paddle_id != paddle_price_id
    )

    if plan_changed:
        logger.info(
            f"UPDATE: {user.username} changed plan from "
            f"{previous_product.name}/{previous_price.paddle_id} → "
            f"{product.name}/{price.paddle_id}"
        )

    # Update record
    subscriber.subscription = product
    subscriber.price = price
    subscriber.subscription_starts_at = starts_at
    subscriber.subscription_ends_at = ends_at

    subscriber.status = Subscriber.StatusChoices.ACTIVE
    subscriber.is_subscription_active = True
    subscriber.is_subscription_cancelled = False

    subscriber.save()

    logger.info(
        f"UPDATE SUCCESS: Synced subscription {subscription_id} for user {user.username}."
    )

@transaction.atomic
def handle_subscription_status_changed(data):
    """
    Handles state-only changes from Paddle, covering:
        - subscription.activated
        - subscription.past_due
        - subscription.paused
        - subscription.resumed
        - subscription.trialing

    These events NEVER modify product/price.
    They ONLY affect status and access flags.
    """

    subscription_id = data.get("id")
    paddle_customer_id = data.get("customer_id")
    current_billing_period = data.get("current_billing_period", {})
    event_type = data.get("event_type")  # You should pass this in from the router.

    if not subscription_id or not paddle_customer_id:
        raise WebhookProcessingError("Status webhook missing required fields.")

    # -------------------------------------------------------------------------
    # Load customer & subscriber
    # -------------------------------------------------------------------------
    try:
        customer = Customer.objects.get(paddle_id=paddle_customer_id)
        starts_at = current_billing_period.get("starts_at")
        ends_at = current_billing_period.get("ends_at")
        user = customer.user
    except Customer.DoesNotExist:
        logger.error(f"STATUS: Unknown user for customer {paddle_customer_id}")
        return

    try:
        subscriber = Subscriber.objects.select_for_update().get(user=user)
    except Subscriber.DoesNotExist:
        logger.error(f"STATUS: No subscriber for event {event_type} → ignoring.")
        return

    # Ignore stale events
    if subscriber.paddle_subscriptions_id != subscription_id:
        logger.info(
            f"STATUS IGNORED: Event {event_type} for {subscription_id} "
            f"does not match active subscription {subscriber.paddle_subscriptions_id}"
        )
        return

    # -------------------------------------------------------------------------
    # Apply status logic
    # -------------------------------------------------------------------------
    if event_type == "subscription.activated":
        subscriber.status = Subscriber.StatusChoices.ACTIVE
        subscriber.is_subscription_active = True
        subscriber.is_subscription_cancelled = False

    elif event_type == "subscription.past_due":
        # DO NOT cancel the sub. Just restrict features.
        subscriber.status = Subscriber.StatusChoices.PASTDUE
        subscriber.is_subscription_active = False  # Access restricted
        subscriber.is_subscription_cancelled = False
        subscriber.subscription_starts_at = None
        subscriber.subscription_ends_at = None

    elif event_type == "subscription.paused":
        subscriber.status = Subscriber.StatusChoices.PAUSED
        subscriber.is_subscription_active = False
        subscriber.is_subscription_paused = True

    elif event_type == "subscription.resumed":
        subscriber.status = Subscriber.StatusChoices.ACTIVE
        subscriber.is_subscription_active = True
        subscriber.is_subscription_cancelled = False

    elif event_type == "subscription.trialing":
        subscriber.status = Subscriber.StatusChoices.TRIALING
        subscriber.paddle_subscriptions_id = subscription_id
        subscriber.is_subscription_active = False
        subscriber.is_subscription_trialing = True
        subscriber.subscription_starts_at = starts_at
        subscriber.subscription_ends_at = ends_at

    else:
        logger.error(f"STATUS: Unknown subscription status event: {event_type}")
        return

    subscriber.save()
    logger.info(f"STATUS UPDATED: {user.username} → {subscriber.status}")
