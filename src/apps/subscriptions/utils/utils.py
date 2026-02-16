import logging
from django.db.models import Q
from django.conf import settings
from paddle_billing.Entities.Subscriptions import (
    SubscriptionStatus,
    SubscriptionEffectiveFrom,
)

from apps.subscriptions.models import Subscriber, Customer, Product, Price
from utils.billing import (
    get_customer_subscription_plans,
    cancel_subscription,
    get_subscription_plan,
)

logger = logging.getLogger(__name__)


def clear_inactive_subscriptions():
    """
    Ensures internal subscriber records match Paddle.

    For each customer:
    - Fetch active Paddle subscriptions.
    - If the subscription does not exist in our Subscriber table:
        • Skip if it already has a scheduled change (e.g. cancel or pause).
        • Otherwise, cancel it at the next billing period.

    This prevents orphaned or duplicate subscriptions from remaining active.
    """

    customers = Customer.objects.all()

    for customer in customers:
        user = customer.user
        paddle_customer_id = customer.paddle_id

        logger.info(
            f"[sync-clear] Processing user={user.id} paddle_customer={paddle_customer_id}"
        )

        try:
            active_subs = get_customer_subscription_plans(
                customer_id=paddle_customer_id,
                status=[SubscriptionStatus.Active],
            )
        except Exception as e:
            logger.error(
                f"[sync-clear] Failed fetching subscription list for customer {paddle_customer_id}: {e}",
                exc_info=True,
            )
            continue

        for paddle_sub in active_subs:
            sub_id = paddle_sub.id

            # Check if this subscription already belongs to a user in our DB and is active
            if Subscriber.objects.filter(
                paddle_subscriptions_id__iexact=str(sub_id).strip(),
                is_subscription_active=True,
                status=Subscriber.StatusChoices.ACTIVE,
            ).exists():
                continue

            logger.info(
                f"[sync-clear] Found orphan subscription {sub_id} for user={user.id}. Inspecting..."
            )

            # Fetch full subscription details
            try:
                full_sub = get_subscription_plan(sub_id=sub_id)
            except Exception as e:
                logger.error(
                    f"[sync-clear] Error fetching details for subscription {sub_id}: {e}",
                    exc_info=True,
                )
                continue

            scheduled_change = getattr(full_sub, "scheduled_change", None)

            # --------------------------------------------------------
            # Skip if Paddle already scheduled any change (cancel/pause/etc.)
            # --------------------------------------------------------
            if scheduled_change:
                action = getattr(scheduled_change, "action", None)
                effective_at = getattr(scheduled_change, "effective_at", None)

                logger.info(
                    f"[sync-clear] Skipping subscription {sub_id}: "
                    f"pending scheduled_change action={action} effective_at={effective_at}"
                )
                continue

            # --------------------------------------------------------
            # Cancel at next billing period
            # --------------------------------------------------------
            logger.info(
                f"[sync-clear] Cancelling orphan subscription {sub_id} for user={user.id} "
                "(no scheduled changes detected)"
            )

            try:
                cancel_subscription(
                    sub_id=sub_id,
                    effective_from=SubscriptionEffectiveFrom.Immediately,
                    raw=False,
                )
            except Exception as e:
                logger.error(
                    f"[sync-clear] Failed cancelling subscription {sub_id}: {e}",
                    exc_info=True,
                )
                continue



def normalize_canceled_subscribers():
    """
    Normalize all canceled subscriptions into FREE accounts.

    Why:
    - Prevent UI confusion
    - Avoid leaking historical billing states
    - Keep a single source of truth: FREE == no subscription

    This is SAFE to run daily.
    """
    product_id = getattr(settings, "FREE_PRODUCT_DB_ID", None)
    price_id = getattr(settings, "FREE_PRICE_DB_ID", None)

    product = Product.objects.get(pk=product_id)
    price = Price.objects.get(pk=price_id)

    canceled_qs = Subscriber.objects.filter(
        Q(status=Subscriber.StatusChoices.FREE) | 
        Q(status=Subscriber.StatusChoices.CANCELED)
    )

    count = canceled_qs.count()

    if count == 0:
        logger.info("[normalize-canceled] No canceled subscriptions found.")
        return

    logger.info(
        f"[normalize-canceled] Normalizing {count} canceled subscriptions to FREE."
    )

    for sub in canceled_qs:
        logger.info(
            f"[normalize-canceled] User={sub.user} "
            f"sub_id={sub.paddle_subscriptions_id} → FREE"
        )

        sub.subscription = product
        sub.price = price
        sub.status = Subscriber.StatusChoices.FREE
        sub.paddle_subscriptions_id = None
        sub.paddle_transactions_id = None
        sub.paddle_price_id = None
        sub.is_free_active = True
        sub.is_subscription_active = False
        sub.has_paid = False
        sub.subscription_starts_at = None
        sub.subscription_ends_at = None

        sub.save(
            update_fields=[
                "subscription",
                "price",
                "status",
                "paddle_subscriptions_id",
                "paddle_transactions_id",
                "paddle_price_id",
                "is_subscription_active",
                "is_free_active",
                "subscription_starts_at",
                "subscription_ends_at",
            ]
        )
