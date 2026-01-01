from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.contrib.auth.models import User

# Allauth signals
from allauth.account.signals import user_signed_up, email_confirmed
from allauth.socialaccount.signals import social_account_added

from .models import Product, Price, Subscriber, Customer

# Constants
ALLOW_CUSTOM_SUBSCRIPTIONS = True

# -----------------------------------------------------------------------------
# Core Business Logic Signals (Product/Price/Subscriber)
# -----------------------------------------------------------------------------

@receiver(post_save, sender=Product)
def product_post_save(sender, instance, created, **kwargs):
    """Create Paddle subscription when product is created."""
    if created:
        instance.create_paddle_subscription()


@receiver(post_save, sender=Price)
def subscription_price_post_save(sender, instance, created, **kwargs):
    """Create Paddle subscription price when price is created."""
    if created:
        instance.create_paddle_subscription_price()


@receiver(post_save, sender=Subscriber)
def user_subscription_post_save(sender, instance, created, **kwargs):
    """Sync user groups when user subscription changes."""
    user_subscription = instance
    user = user_subscription.user
    subscription = user_subscription.subscription

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
            
        # FIX: Removed the '.value' access on the boolean constant
        elif not ALLOW_CUSTOM_SUBSCRIPTIONS:
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


# -----------------------------------------------------------------------------
# Auth & Customer Lifecycle Signals (Allauth)
# -----------------------------------------------------------------------------

@receiver(user_signed_up, sender=Customer)
def handle_user_signed_up(request, user, **kwargs):
    """
    Handle user sign up: Create Customer profile and sync to Paddle 
    if the email is already verified (rare, but possible).
    """
    customer, created = Customer.objects.get_or_create(user=user)
    
    # Check if email is verified immediately upon signup
    if user.email and user.emailaddress_set.filter(email=user.email, verified=True).exists():
        customer.create_or_update_paddle_customer()


@receiver(social_account_added, sender=Customer)
def handle_social_account_added(request, sociallogin, **kwargs):
    """
    Handle social account connection: Ensure Customer profile exists 
    and sync to Paddle since social accounts often provide verified emails.
    """
    user = sociallogin.user
    customer, created = Customer.objects.get_or_create(user=user)
    
    if user.email:
        customer.has_user_agreed_tos_and_privacy = True
        customer.save()
        customer.create_or_update_paddle_customer()


@receiver(email_confirmed, sender=Customer)
def handle_email_confirmed(request, email_address, **kwargs):
    """
    Handle email confirmation: This is the primary trigger for 
    creating the Paddle customer for standard email/password users.
    """
    user = email_address.user
    customer, created = Customer.objects.get_or_create(user=user)
    
    # If customer doesn't have a Paddle ID yet, create one now that email is verified
    if customer and not customer.paddle_id:
        customer.create_or_update_paddle_customer()