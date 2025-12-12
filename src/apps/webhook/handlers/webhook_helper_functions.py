import logging

from django.conf import settings
from django.db import transaction
from paddle_billing.Exceptions.ApiError import ApiError
from paddle_billing.Entities.Subscriptions import SubscriptionEffectiveFrom

from utils.billing import cancel_subscription, get_subscription_plan
from apps.subscriptions.models import Price, Subscriber, Product

logger = logging.getLogger(__name__)


class WebhookProcessingError(ValueError):
    """Client error → return 400. Paddle does not retry."""
    pass


class SubscriptionSyncError(Exception):
    """Server/API error → return 500. Paddle *will* retry."""
    pass


def sync_and_cancel_old_subscription(
    user, 
    new_subscription_id: str,
    cancel_immediately: bool = False
):
    """
    Safely handles subscription switching:
    - Cancels old Paddle subscription either immediately or at the next billing period.
    - Skips cancellation if old subscription is already scheduled to cancel.
    - Protects against race conditions, API quirks and incomplete Paddle objects.
    """

    with transaction.atomic():

        # -------------------------------
        # 1. Get Subscriber record
        # -------------------------------
        try:
            sub_record = Subscriber.objects.select_for_update().get(user=user)
        except Subscriber.DoesNotExist:
            logger.info(f"[sync] User {user.id}: no subscription; nothing to cancel.")
            return

        old_sub_id = sub_record.paddle_subscriptions_id

        if not old_sub_id:
            logger.warning(
                f"[sync] User {user.id}: Subscriber row missing paddle_subscriptions_id."
            )
            return

        # -------------------------------
        # 2. If switching to same plan → ignore
        # -------------------------------
        if old_sub_id == new_subscription_id:
            logger.info(
                f"[sync] User {user.id}: already on subscription {new_subscription_id}."
            )
            return

        # -------------------------------
        # 3. Fetch old subscription from Paddle
        # -------------------------------
        try:
            old_sub = get_subscription_plan(sub_id=old_sub_id)
        except ApiError as e:
            code = getattr(e.response, "status_code", None)
            if code == 404:
                logger.warning(f"[sync] Paddle 404: old subscription {old_sub_id} missing. Skipping.")
                return
            logger.error(f"[sync] Paddle API error fetching subscription {old_sub_id}: {e}", exc_info=True)
            raise SubscriptionSyncError(f"Subscription fetch error: {e}") from e
        except Exception as e:
            logger.error(f"[sync] Unexpected error fetching subscription {old_sub_id}: {e}", exc_info=True)
            raise SubscriptionSyncError(f"Unexpected Paddle response: {e}") from e

        status = getattr(old_sub, "status", None)
        scheduled_change = getattr(old_sub, "scheduled_change", None)

        if status is None:
            raise SubscriptionSyncError(
                f"Paddle returned subscription {old_sub_id} without status."
            )

        # -------------------------------
        # 4. Skip if already cancelled/paused
        # -------------------------------
        if status in ("canceled", "paused"):
            logger.info(f"[sync] Old subscription {old_sub_id} already {status}. Nothing to cancel.")
            return

        # -------------------------------
        # 5. Skip if Paddle already scheduled cancellation
        # -------------------------------
        if scheduled_change and getattr(scheduled_change, "action", None) == "cancel":
            logger.info(
                f"[sync] Old subscription {old_sub_id} already scheduled to cancel at "
                f"{scheduled_change.effective_at}. Skipping."
            )
            return

        # -------------------------------
        # 6. Attempt cancellation
        # -------------------------------
        effective_setting = (
            SubscriptionEffectiveFrom.Immediately
            if cancel_immediately
            else SubscriptionEffectiveFrom.NextBillingPeriod
        )

        logger.info(
            f"[sync] Cancelling old subscription {old_sub_id} "
            f"(user {user.id}, status {status}, immediate={cancel_immediately})."
        )

        try:
            cancel_res = cancel_subscription(
                sub_id=old_sub_id,
                effective_from=effective_setting
            )
        except ApiError as e:
            logger.error(f"[sync] Paddle cancellation error for {old_sub_id}: {e}", exc_info=True)
            raise SubscriptionSyncError(f"Cancellation API error: {e}") from e
        except Exception as e:
            logger.error(f"[sync] Unexpected cancellation error for {old_sub_id}: {e}", exc_info=True)
            raise SubscriptionSyncError(f"Unexpected cancellation error: {e}") from e

        # -------------------------------
        # 7. Validate cancellation result
        # -------------------------------
        cancel_status = getattr(cancel_res, "status", None)
        cancel_sc = getattr(cancel_res, "scheduled_change", None)

        # NEXT PERIOD CANCELLATION
        if cancel_status == "active":
            if cancel_sc and getattr(cancel_sc, "action", None) == "cancel":
                logger.info(
                    f"[sync] Old subscription {old_sub_id} scheduled for cancellation at "
                    f"{cancel_sc.effective_at}."
                )
                return

            raise SubscriptionSyncError(
                f"Subscription {old_sub_id} remained active without a scheduled cancellation."
            )

        # IMMEDIATE CANCELLATION
        if cancel_status == "canceled":
            logger.info(f"[sync] Old subscription {old_sub_id} canceled immediately.")
            return

        raise SubscriptionSyncError(
            f"Unexpected cancellation status '{cancel_status}' for {old_sub_id}."
        )


def get_free_plan_details():
    """
    Fetches the free plan Product + Price safely.
    Hard-fails with a 400-level exception if config or DB objects are missing.
    """

    product_id = getattr(settings, "FREE_PRODUCT_DB_ID", None)
    price_id = getattr(settings, "FREE_PRICE_DB_ID", None)

    if not product_id or not price_id:
        raise WebhookProcessingError(
            "FREE_PRODUCT_DB_ID or FREE_PRICE_DB_ID missing from settings."
        )

    try:
        free_product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        raise WebhookProcessingError(
            f"Free Product (ID {product_id}) not found in database."
        )

    try:
        free_price = Price.objects.get(pk=price_id)
    except Price.DoesNotExist:
        raise WebhookProcessingError(
            f"Free Price (ID {price_id}) not found in database."
        )

    return free_product, free_price