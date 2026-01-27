import logging

from django.db import transaction
from django.utils import timezone


from apps.subscriptions.models import Price, Subscriber, Product, Customer
from .webhook_helper_functions import (
    WebhookProcessingError,
    SubscriptionSyncError,
    sync_and_cancel_old_subscription,
    get_free_plan_details,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# SUBSCRIPTION CREATED
# ----------------------------------------------------------------------
@transaction.atomic
def handle_subscription_created(data: dict):
    """
    Paddle subscription.created handler (production hardened).
    """

    subscription_id = data.get("id")
    transaction_id = data.get("transaction_id")
    paddle_customer_id = data.get("customer_id")
    items = data.get("items") or []
    billing_period = data.get("current_billing_period") or {}

    if not subscription_id and transaction_id or not paddle_customer_id or not items:
        raise WebhookProcessingError("Incomplete subscription.created payload.")

    try:
        item = items[0]
        product_id = (item.get("product") or {}).get("id")
        price_id = (item.get("price") or {}).get("id")
        starts_at = billing_period.get("starts_at")
        ends_at = billing_period.get("ends_at")

        if not product_id or not price_id:
            raise ValueError
    except Exception:
        raise WebhookProcessingError("Invalid items structure.")

    try:
        customer = Customer.objects.select_related("user").get(
            paddle_id=paddle_customer_id
        )
        user = customer.user
        product = Product.objects.get(paddle_id=product_id)
        price = Price.objects.get(paddle_id=price_id)
    except Exception as e:
        raise SubscriptionSyncError(f"Model resolution failed: {e}") from e

    # Enforce one active subscription
    sync_and_cancel_old_subscription(
        user=user,
        new_subscription_id=str(subscription_id),
        cancel_immediately=True,
    )

    # Lock subscriber row
    Subscriber.objects.select_for_update().filter(user=user)

    subscriber, created = Subscriber.objects.update_or_create(
        user=user,
        defaults={
            "subscription": product,
            "price": price,
            "status": Subscriber.StatusChoices.ACTIVE,
            "is_subscription_active": True,
            "is_free_active": False,
            "paddle_subscriptions_id": subscription_id,
            "paddle_transactions_id": transaction_id,
            "paddle_price_id": price_id,
            "paddle_user_id": paddle_customer_id,
            "subscription_starts_at": starts_at,
            "subscription_ends_at": ends_at,
        },
    )

    logger.info(
        f"[CREATED] {'Created' if created else 'Updated'} "
        f"subscription {subscription_id} for {user.username}"
    )


# ----------------------------------------------------------------------
# SUBSCRIPTION CANCELED
# ----------------------------------------------------------------------
@transaction.atomic
def handle_subscription_canceled(data: dict):
    """
    Paddle subscription.canceled handler.
    Fires when the subscription is FULLY terminated (end of cycle).
    """

    paddle_customer_id = data.get("customer_id")
    subscription_id = data.get("id")

    if not paddle_customer_id or not subscription_id:
        raise WebhookProcessingError("Invalid subscription.canceled payload.")

    try:
        customer = Customer.objects.select_related("user").get(paddle_id=paddle_customer_id)
        user = customer.user
    except Customer.DoesNotExist:
        logger.error(f"[CANCEL] Unknown customer {paddle_customer_id}")
        return

    free_product, free_price = get_free_plan_details()

    try:
        subscriber = Subscriber.objects.select_for_update().get(user=user)
    except Subscriber.DoesNotExist:
        Subscriber.objects.create(
            user=user,
            subscription=free_product,
            price=free_price,
            status=Subscriber.StatusChoices.FREE,
            paddle_subscriptions_id = None,
            paddle_transactions_id = None,
            paddle_user_id = paddle_customer_id,
            paddle_price_id = None,
            is_free_active=True,
            is_subscription_active=False,
            has_paid=False,
            subscription_starts_at = None,
            subscription_ends_at = None
        )
        return

    if subscriber.paddle_subscriptions_id and subscriber.paddle_subscriptions_id != subscription_id:
        logger.info(
            f"[CANCEL IGNORED] Event {subscription_id} "
            f"!= active {subscriber.paddle_subscriptions_id}"
        )
        return

    if subscriber.status == Subscriber.StatusChoices.CANCELED:
        return

    subscriber.subscription = free_product
    subscriber.price = free_price
    subscriber.status = Subscriber.StatusChoices.CANCELED
    subscriber.is_subscription_active = False
    subscriber.is_free_active = True
    subscriber.has_paid = False
    subscriber.subscription_starts_at = None
    subscriber.subscription_ends_at = None

    subscriber.save(update_fields=[
        "subscription",
        "price",
        "status",
        "paddle_subscriptions_id",
        "paddle_transactions_id",
        "paddle_user_id",
        "paddle_price_id",
        "is_free_active",
        "is_subscription_active",
        "has_paid",
        "subscription_starts_at",
        "subscription_ends_at",
    ])

    logger.info(f"[CANCELED] {user.username} downgraded to free.")


# ----------------------------------------------------------------------
# SUBSCRIPTION UPDATED
# ----------------------------------------------------------------------
@transaction.atomic
def handle_subscription_updated(data: dict):
    """
    Paddle subscription.updated webhook.
    Handles any updates from paddle to sync with application.
    """

    subscription_id = data.get("id")
    txn_id = data.get("transaction_id")
    paddle_customer_id = data.get("customer_id")
    paddle_status = data.get("status")
    items = data.get("items") or []
    billing = data.get("current_billing_period") or {}

    if not all([subscription_id, paddle_customer_id, paddle_status, items]):
        raise WebhookProcessingError("Invalid subscription.updated payload")

    item = items[0]
    product_id = (item.get("product") or {}).get("id")
    price_id = (item.get("price") or {}).get("id")

    if not product_id or not price_id:
        raise WebhookProcessingError("Invalid subscription item structure")

    starts_at = billing.get("starts_at")
    ends_at = billing.get("ends_at")

    customer = Customer.objects.select_related("user").get(
        paddle_id=paddle_customer_id
    )

    user = customer.user
    product = Product.objects.get(paddle_id=product_id)
    price = Price.objects.get(paddle_id=price_id)
    free_product, free_price = get_free_plan_details()

    subscriber, _ = Subscriber.objects.select_for_update().get_or_create(
        user=user,
        defaults={
            "subscription": free_product,
            "price": free_price,
            "status": Subscriber.StatusChoices.FREE,
            "is_free_active": True,
            "is_subscription_active": False,
        },
    )

    if not subscriber.paddle_subscriptions_id:
        subscriber.paddle_subscriptions_id = subscription_id

    # Ignore updates for a different subscription
    if (
        subscriber.paddle_subscriptions_id
        and subscriber.paddle_subscriptions_id != subscription_id
    ):
        logger.info(
            f"[SUB UPDATE IGNORED] {subscription_id} != {subscriber.paddle_subscriptions_id}"
        )
        return

    STATUS_MAP = {
        "active": Subscriber.StatusChoices.ACTIVE,
        "trialing": Subscriber.StatusChoices.TRIALING,
        "paused": Subscriber.StatusChoices.PAUSED,
        "past_due": Subscriber.StatusChoices.PAST_DUE,
        "canceled": Subscriber.StatusChoices.CANCELED,
    }

    internal_status = STATUS_MAP.get(paddle_status)
    if not internal_status:
        logger.warning(f"[SUB UPDATE] Unknown status: {paddle_status}")
        return

    # Always sync identifiers
    subscriber.paddle_subscriptions_id = subscription_id
    subscriber.paddle_transactions_id = txn_id
    subscriber.paddle_user_id = paddle_customer_id
    subscriber.paddle_price_id = price_id

    # Sync plan if changed
    if (
        subscriber.subscription != product
        or subscriber.price != price
    ):
        subscriber.subscription = product
        subscriber.price = price

    if not subscriber.paddle_subscriptions_id:
        if subscriber.status in {Subscriber.StatusChoices.FREE, Subscriber.StatusChoices.CANCELED}:
            return  # perfectly valid state

        logger.warning(
            f"[sync] User {user.username}: "
            "Active subscriber missing paddle_subscriptions_id"
        ) 
        return

    if starts_at:
        subscriber.subscription_starts_at = starts_at

    if ends_at:
        subscriber.subscription_ends_at = ends_at

    subscriber.status = internal_status

    # ------------------------
    # ACCESS CONTROL LOGIC
    # ------------------------
    if paddle_status in ("active", "trialing"):
        subscriber.is_subscription_active = True
        subscriber.is_free_active = False

    elif paddle_status == "past_due":
        if subscriber.has_paid:
            subscriber.is_subscription_active = True
        else:
            subscriber.is_subscription_active = False
            
        subscriber.is_free_active = False
        subscriber.has_paid = False

    elif paddle_status == "paused":
        subscriber.is_subscription_active = False
        subscriber.is_free_active = False

    elif paddle_status == "canceled":
        subscriber.subscription = free_product
        subscriber.price = free_price
        subscriber.status = Subscriber.StatusChoices.CANCELED
        subscriber.is_subscription_active = False
        subscriber.is_free_active = True
        subscriber.has_paid = False
        subscriber.paddle_price_id = None

    subscriber.save()

    logger.info(
        f"[SUBSCRIPTION UPDATED SUCCESSFULLY] {subscription_id} → {subscriber.status} for user={user.username}"
    )



@transaction.atomic
def handle_transaction_completed(data: dict):
    """
    Paddle transaction.completed handler.
    This indicates a payment attempt is Successful — ACTIVATE plan and features.
    """

    sub_id = data.get("subscription_id")
    txn_id = data.get("id")
    status = data.get("status")

    if status != "completed" or not sub_id:
        return

    try:
        subscriber = Subscriber.objects.select_for_update().get(
            paddle_subscriptions_id=sub_id
        )
    except Subscriber.DoesNotExist:
        raise WebhookProcessingError("Subscriber not found - forcing retry")

    subscriber.has_paid = True
    subscriber.paddle_transactions_id = txn_id

    # If trial just converted
    if subscriber.status == Subscriber.StatusChoices.TRIALING:
        subscriber.status = Subscriber.StatusChoices.ACTIVE
        subscriber.is_subscription_active = True
        subscriber.is_free_active = False

    subscriber.save()


@transaction.atomic
def handle_transaction_failed(data: dict):
    """
    Paddle transaction.failed handler.
    This indicates a payment attempt failed — NOT a cancellation.
    """

    transaction_id = data.get("id")
    subscription_id = data.get("subscription_id")
    customer_id = data.get("customer_id")

    if not transaction_id or not customer_id:
        raise WebhookProcessingError("Invalid transaction.failed payload")
    
    # -------------------------------
    # Resolve subscriber
    # -------------------------------
    subscriber = None

    if subscription_id:
        subscriber = (
            Subscriber.objects.select_for_update()
            .filter(paddle_subscriptions_id=subscription_id)
            .first()
        )

    if not subscriber:
        try:
            customer = Customer.objects.select_related("user").get(
                paddle_id=customer_id
            )
            subscriber = Subscriber.objects.select_for_update().get(
                user=customer.user
            )
        except (Customer.DoesNotExist, Subscriber.DoesNotExist):
            logger.warning(
                f"[TX FAILED] Subscriber not found for customer {customer_id}"
            )
            return
    
    # -------------------------------
    # Idempotency guard
    # -------------------------------
    if subscriber.paddle_transactions_id == transaction_id:
        logger.info(
            f"[TX FAILED] Duplicate event ignored for {transaction_id}"
        )
        return
    
    # -------------------------------
    # Mark payment issue (NOT cancel)
    # -------------------------------
    subscriber.paddle_transactions_id = transaction_id

    # Transition to past_due ONLY if currently active/trialing
    if subscriber.status in (Subscriber.StatusChoices.ACTIVE, Subscriber.StatusChoices.TRIALING):
        subscriber.status = Subscriber.StatusChoices.PAST_DUE

    # -------------------------------------------------------
    # CRITICAL LOGIC: Distinguish New vs Existing Failures
    # -------------------------------------------------------
    if subscriber.has_paid:
        # Existing user (Renewal failed) -> GRACE PERIOD
        subscriber.is_subscription_active = True
        logger.info(f"[TX FAILED] Grace period active for {subscriber.user.username}")
    else:
        # New user (Signup failed) -> NO ACCESS
        subscriber.is_subscription_active = False
        logger.info(f"[TX FAILED] Signup payment failed for {subscriber.user.username}. Access denied.")

    subscriber.save(update_fields=[
        "paddle_transactions_id",
        "status",
        "is_subscription_active",
        "is_free_active",
    ])

    logger.info(
        f"[TX FAILED] Payment issue recorded for user {subscriber.user.username}"
    )