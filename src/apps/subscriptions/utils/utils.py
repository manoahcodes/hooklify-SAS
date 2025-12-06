import logging
from django.db.models import Q
from paddle_billing.Entities.Subscriptions import (
    SubscriptionStatus,
    SubscriptionEffectiveFrom,
)

from subscriptions.models import Subscriber, Customer
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
                    effective_from=SubscriptionEffectiveFrom.NextBillingPeriod,
                    raw=False,
                )
            except Exception as e:
                logger.error(
                    f"[sync-clear] Failed cancelling subscription {sub_id}: {e}",
                    exc_info=True,
                )
                continue