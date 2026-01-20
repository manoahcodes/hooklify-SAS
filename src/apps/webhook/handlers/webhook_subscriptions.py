import logging

from django.db import transaction

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
        new_subscription_id=subscription_id,
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
    """

    paddle_customer_id = data.get("customer_id")
    subscription_id = data.get("id")

    if not paddle_customer_id or not subscription_id:
        raise WebhookProcessingError("Invalid subscription.canceled payload.")

    try:
        customer = Customer.objects.select_related("user").get(
            paddle_id=paddle_customer_id
        )
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
            subscription_starts_at = None,
            subscription_ends_at = None
        )
        return

    if subscriber.paddle_subscriptions_id != subscription_id:
        logger.info(
            f"[CANCEL IGNORED] Event {subscription_id} "
            f"!= active {subscriber.paddle_subscriptions_id}"
        )
        return

    if subscriber.status == Subscriber.StatusChoices.CANCELED:
        return

    scheduled = data.get("scheduled_change") or {}
    ends_at = scheduled.get("effective_at")

    if ends_at:
        subscriber.subscription_ends_at = ends_at
        subscriber.save(update_fields=["subscription_ends_at"])
        logger.info(f"[CANCEL SCHEDULED] {subscription_id} → {ends_at}")
        return

    subscriber.subscription = free_product
    subscriber.price = free_price
    subscriber.status = Subscriber.StatusChoices.CANCELED
    subscriber.is_subscription_active = False
    subscriber.is_free_active = True
    subscriber.subscription_starts_at = None
    subscriber.subscription_ends_at = None

    subscriber.save(update_fields=[
        "subscription",
        "price",
        "status",
        "paddle_subscriptions_id"
        "paddle_transactions_id",
        "paddle_user_id",
        "paddle_price_id",
        "is_free_active",
        "is_subscription_active",
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
    Paddle subscription.updated handler.
    """

    subscription_id = data.get("id")
    txn_id = data.get("transaction_id")
    paddle_customer_id = data.get("customer_id")
    paddle_status = data.get("status")
    items = data.get("items") or []
    billing = data.get("current_billing_period") or {}

    if not subscription_id or not paddle_customer_id or not items or not paddle_status:
        raise WebhookProcessingError("Invalid subscription.updated payload.")

    try:
        item = items[0]
        product_id = (item.get("product") or {}).get("id")
        price_id = (item.get("price") or {}).get("id")
        starts_at = billing.get("starts_at")
        ends_at = billing.get("ends_at")

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
            subscription_starts_at = None,
            subscription_ends_at = None
        )
        return

    if subscriber.paddle_subscriptions_id != subscription_id:
        logger.info(
            f"[UPDATE IGNORED] {subscription_id} != {subscriber.paddle_subscriptions_id}"
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
        logger.error(f"[UPDATE] Unknown status {paddle_status}")
        return

    if (
        not subscriber.subscription
        or subscriber.subscription.paddle_id != product_id
        or subscriber.price.paddle_id != price_id
    ):
        subscriber.subscription = product
        subscriber.price = price

    if starts_at:
        subscriber.subscription_starts_at = starts_at

    if ends_at:
        if not subscriber.subscription_ends_at or ends_at >= subscriber.subscription_ends_at:
            subscriber.subscription_ends_at = ends_at

    subscriber.status = internal_status
    subscriber.paddle_transactions_id = txn_id
    subscriber.paddle_price_id = price_id

    if paddle_status in ("active", "trialing", "paused"):
        subscriber.is_subscription_active = True
        subscriber.is_free_active = False
    else:
        subscriber.is_subscription_active = False
        subscriber.is_free_active = paddle_status == "canceled"

    subscriber.save(update_fields=[
        "subscription",
        "price",
        "status",
        "paddle_subscriptions_id"
        "paddle_transactions_id",
        "paddle_user_id",
        "paddle_price_id",
        "is_free_active",
        "is_subscription_active",
        "subscription_starts_at",
        "subscription_ends_at",
    ])

    logger.info(
        f"[UPDATE SUCCESS] {subscription_id} synced for {user.username} ({paddle_status})"
    )
