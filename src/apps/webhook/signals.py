from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.core.models import Notification
from apps.subscriptions.models import Subscriber

# ==========================================
# 1. SUBSCRIPTION SIGNALS
# ==========================================

@receiver(post_save, sender=Subscriber)
def notify_on_subscription_change(sender, instance, created, **kwargs):
    """
    Triggers when a Subscriber model is created or updated.
    """
    # Safety Check: Ensure the subscriber is linked to a user
    if not instance.user:
        return

    # Scenario A: New Subscription Created
    if instance.status == 'active' and instance.is_subscription_active == True:
        Notification.objects.create(
            recipient=instance.user,
            category='success',
            title=f'Subscription Activated',
            message=f'Your subscription to the {instance.subscription.name} plan is now active.',
            content_object=instance
        )

    # Scenario B: Subscription Status Changes (e.g., Canceled or Past Due)
    else:
        # You can add logic here to check specific status fields if your model has them
        if instance.status == 'canceled' and instance.is_subscription_active == False:
            Notification.objects.create(
                recipient=instance.user,
                category='success',
                title='Subscription Canceled',
                message='Your subscription has been canceled. You will retain access until the end of the billing period.',
                content_object=instance
            )
        
        elif instance.status == 'past_due':
             Notification.objects.create(
                recipient=instance.user,
                category='error',
                title='Payment Failed',
                message='We could not process your latest payment. Please update your billing info.',
                content_object=instance
            )