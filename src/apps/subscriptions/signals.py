from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db import transaction

from allauth.account.signals import user_signed_up, email_confirmed
from allauth.socialaccount.signals import social_account_added

from .models import Product, Price, Subscriber, Customer


# Constants
ALLOW_CUSTOM_SUBSCRIPTIONS = True


@receiver(post_save, sender=Product)
def product_post_save(sender, instance, created, **kwargs):
    """Signal handler to create Paddle subscription when product is created."""
    if created:
        instance.create_paddle_subscription()


@receiver(post_save, sender=Price)
def subscription_price_post_save(sender, instance, created, **kwargs):
    """Signal handler to create Paddle subscription price when price is created."""
    if created:
        instance.create_paddle_subscription_price()


@receiver(post_save, sender=Subscriber)
def user_subscription_post_save(sender, instance, created, **kwargs):
    """
    Signal handler to update user groups when user subscription changes.
    
    Args:
        sender: The model class that sent the signal
        instance: The actual Subscriber instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    user_subscription = instance
    user = user_subscription.user
    subscription = user_subscription.subscription

    # Validate required relationships
    if not user:
        return

    with transaction.atomic():
        if not subscription:
            # Remove all subscription-based groups
            subscription_groups = (
                Product.objects.filter(active=True)
                .values_list("groups__id", flat=True)
                .distinct()
            )
            user.groups.remove(*subscription_groups)
        elif not getattr(ALLOW_CUSTOM_SUBSCRIPTIONS, "value", False):
            # Simple mode: set exact subscription groups
            subscription_groups = subscription.groups.all()
            user.groups.set(subscription_groups)
        else:
            # Custom mode: preserve custom groups while avoiding conflicts
            current_subscription_groups = set(
                subscription.groups.values_list("id", flat=True)
            )
            other_subscription_groups = set(
                Product.objects.filter(active=True)
                .exclude(id=subscription.id)
                .values_list("groups__id", flat=True)
                .distinct()
            )
            current_user_groups = set(
                user.groups.exclude(id__in=other_subscription_groups).values_list(
                    "id", flat=True
                )
            )
            final_groups = current_user_groups | current_subscription_groups
            user.groups.set(final_groups)

@receiver(post_save, sender=Customer)
def customer_signed_up(sender, instance, created, **kwargs):
    """Handle user sign up to create or update customer profile."""
    if created:
        customer, created = Customer.objects.get_or_create(user=instance.user)
        if instance.user.email and instance.user.emailaddress_set.filter(email=instance.user.email, verified=True).exists():
            customer.create_or_update_paddle_customer()

@receiver(post_save, sender=Customer)
def customer_email_confirmed(sender, instance, created, **kwargs):
    """Handle email confirmation to create or update customer profile."""
    if created:
        user = instance.user
        customer, created = Customer.objects.get_or_create(user=user)
        if customer and not customer.paddle_id:
            customer.create_or_update_paddle_customer()


# Handle user signed up signal from allauth
def handle_user_signed_up_signal(request, user, **kwargs):
    """Handle user sign up to create or update customer profile."""
    # Create customer profile for the user
    customer, created = Customer.objects.get_or_create(user=user)
    # If user has a verified email, create/update Paddle customer
    if user.email and user.emailaddress_set.filter(email=user.email, verified=True).exists():
        customer.create_or_update_paddle_customer()

# Handle social account added signal
def handle_social_account_added_signal(request, sociallogin, **kwargs):
    """Handle social account added to create or update customer profile."""
    user = sociallogin.user
    # Create customer profile for the user
    customer, created = Customer.objects.get_or_create(user=user)
    # If user has an email, create/update Paddle customer
    if user.email:
        customer.create_or_update_paddle_customer()

# Handle email confirmed signal
def handle_email_confirmed_signal(email_address, **kwargs):
    """Handle email confirmation to create or update customer profile."""
    user = email_address.user
    # Get or create customer profile for the user
    customer, created = Customer.objects.get_or_create(user=user)
    # If customer doesn't have a Paddle ID, create one
    if customer and not customer.paddle_id:
        customer.create_or_update_paddle_customer()

# Connect signals
user_signed_up.connect(handle_user_signed_up_signal)
social_account_added.connect(handle_social_account_added_signal)
email_confirmed.connect(handle_email_confirmed_signal)
