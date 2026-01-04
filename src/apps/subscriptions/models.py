import uuid
from decimal import Decimal
import logging

from django.db import models
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from utils.billing import create_product, create_price, create_customer, update_customer, update_price

logger = logging.getLogger(__name__)

# Constants
SUBSCRIPTION_PERMISSIONS = [
    ("influencer", "Influencer Permission"),  # To distinguish influencer users
    ("creator", "Creator Permission"),        # To distinguish creator users
    ("free", "Free Permission"),              # To distinguish free users
]


class Product(models.Model):
    """Subscription product model representing different subscription tiers."""
    
    name = models.CharField(max_length=100)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    description = models.TextField(
        blank=True,
        null=True,
        help_text=_("Description of the subscription plan")
    )
    groups = models.ManyToManyField(Group, related_name="subscriptions", blank=True)
    active = models.BooleanField(default=True)
    permissions = models.ManyToManyField(
        Permission,
        related_name="subscriptions",
        limit_choices_to={
            "content_type__app_label": "subscriptions",
            "codename__in": [perm[0] for perm in SUBSCRIPTION_PERMISSIONS],
        },
        blank=True,
    )
    paddle_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    order = models.IntegerField(
        default=1,
        help_text=_("Ordering on Django pricing page")
    )
    featured = models.BooleanField(
        default=True,
        help_text=_("Featured on Django pricing page")
    )
    updated = models.DateTimeField(auto_now=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    features = models.TextField(
        blank=True,
        null=True,
        help_text=_("Features for pricing page, separated by new line")
    )

    class Meta:
        ordering = ["order", "featured", "-updated"]
        permissions = SUBSCRIPTION_PERMISSIONS

    def __str__(self):
        return self.name

    def get_features_as_list(self):
        """Return features as a list of strings."""
        if not self.features:
            return []
        return [feature.strip() for feature in self.features.split("\n")]

    def create_paddle_subscription(self):
        """
        Automatically create Paddle product if missing.
        
        Returns:
            str: Paddle product ID or None if failed
        """
        if self.paddle_id:
            return self.paddle_id
            
        try:
            product_id = create_product(
                raw=False,
                name=self.name,
                desc=self.description or "",
                metadata={
                    "subscription_id": str(self.pk) if self.pk else "",
                    "name": self.name,
                    "uuid": str(self.uuid),
                }
            )
            
            if not product_id:
                raise ValueError("Paddle did not return a valid product ID")
                
            self.paddle_id = product_id
            self.save(update_fields=["paddle_id"])
            
            # Using Django's logging instead of print
            logger.info(f"Paddle product created for {self.name}: {product_id}")
            
            return product_id
        except Exception as e:
            logger.error(f"Failed to create Paddle subscription: {e}")
            return None


class Price(models.Model):
    """Price model for subscription products."""
    
    class IntervalChoices(models.TextChoices):
        MONTHLY = "month", _("Monthly")
        YEARLY = "year", _("Yearly")
        FREE = "free", _("Free")

    subscription = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name="prices"
    )
    paddle_id = models.CharField(max_length=255, null=True, blank=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    interval = models.CharField(
        max_length=10,
        default=IntervalChoices.MONTHLY,
        choices=IntervalChoices.choices,
        help_text=_("Type of recurring method whether monthly, yearly or free")
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Price of the subscription plan")
    )
    display_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Display price of the subscription plan")
    )
    order = models.IntegerField(
        default=1,
        help_text=_("Ordering on Django pricing page")
    )
    featured = models.BooleanField(
        default=True,
        help_text=_("Featured on Pricing page")
    )
    updated = models.DateTimeField(auto_now=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["subscription__order", "order", "featured", "-updated"]
        verbose_name = _("Price")
        verbose_name_plural = _("Prices")

    def __str__(self):
        subscription_name = self.subscription.name if self.subscription else "Plan"
        return f"{subscription_name} - {self.price} {self.paddle_currency} / {self.interval}"

    @property
    def display_features_list(self):
        """Return subscription features as a list."""
        if not self.subscription:
            return []
        return self.subscription.get_features_as_list()

    @property
    def product_paddle_id(self):
        """Return the paddle ID of the associated product."""
        if not self.subscription:
            return None
        return self.subscription.paddle_id

    @property
    def display_subscription_name(self):
        """Return the display name for the subscription."""
        if not self.subscription:
            return _("Plan")
        return self.subscription.name

    @property
    def paddle_currency(self):
        """Return the currency code for Paddle."""
        return "USD"

    @property
    def paddle_price(self):
        """Return the price in cents for Paddle."""
        return int(self.price * 100)

    @property
    def is_free(self):
        """Check if this is a free plan."""
        return self.interval == self.IntervalChoices.FREE or self.price == '0.00'

    @property
    def display_description(self):
        """Return the display description for the subscription."""
        if self.subscription and self.subscription.description:
            return self.subscription.description
        return _("This subscription plan is still in the development phase and is coming soon.")

    def create_paddle_subscription_price(self):
        """
        Automatically create Paddle price product if missing.
        
        Returns:
            str: Paddle price ID or None if failed
        """

        # Handle free plans
        if self.is_free:
            if not self.paddle_id:
                self.interval = Price.IntervalChoices.FREE
                self.paddle_id = "FREE_PLAN"
                self.save(update_fields=["paddle_id"])
                
                subscription_name = self.subscription.name if self.subscription else "Unknown"
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Free plan '{subscription_name}' created locally (no Paddle ID required).")
            return self.paddle_id

        if self.paddle_id:
            return self.paddle_id

        try:
            # Check if subscription exists before proceeding
            if not self.subscription:
                raise ValueError("Subscription is required to create Paddle price")
            
            
            product_id = self.product_paddle_id or ""
            if self.subscription and hasattr(self.subscription, 'paddle_id'):
                product_id = self.subscription.paddle_id or ""
            

            price_id = create_price(
                raw=False,
                product_id=str(product_id),
                amount=str(self.paddle_price),
                currency_code=self.paddle_currency,
                interval=self.interval,
                desc=self.display_description,
                name=self.subscription.name if self.subscription else "",
                metadata={
                    "subscription_plan_id": str(self.subscription.pk) if self.subscription and self.subscription.pk else "",
                    "subscription_plan_name": self.subscription.name if self.subscription else "",
                    "subscription_plan_uuid": str(self.uuid),
                }
            )
            
            if not price_id:
                raise ValueError("Paddle did not return a valid product price ID")
                
            self.paddle_id = price_id
            self.save(update_fields=["paddle_id"])
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Paddle product price created for {self.subscription.name}: {price_id}")
            
            return price_id
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create Paddle subscription price: {e}")
            return None

    def save(self, *args, **kwargs):
        """Override save to ensure only one featured price per subscription."""
        super().save(*args, **kwargs)
        
            # Ensure only one featured price per subscription
        if self.featured and self.subscription:
            Price.objects.filter(
                subscription=self.subscription,
                interval=self.interval,
            ).exclude(pk=self.pk).update(featured=False)


class Subscriber(models.Model):
    """Model representing a user's subscription status."""
    
    class StatusChoices(models.TextChoices):
        ACTIVE = "active", _("Active")
        CANCELED = "canceled", _("Canceled")
        PAST_DUE = "past_due", _("Past Due")
        PAUSED = "paused", _("Paused")
        TRIALING = "trialing", _("Trialing")
        FREE = "free", _("Free")

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="subscriber"
    )
    subscription = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        related_name="subscribers"
    )
    price = models.ForeignKey(
        Price,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscribers"
    )
    paddle_subscriptions_id = models.CharField(max_length=255, null=True, blank=True)
    paddle_user_id = models.CharField(max_length=255, null=True, blank=True)
    paddle_price_id = models.CharField(max_length=255, null=True, blank=True)
    is_free_active = models.BooleanField(
        default=True,
        help_text=_("To determine when the user has an active free package")
    )
    is_subscription_active = models.BooleanField(
        default=False,
        help_text=_("To determine when the user has activated their subscription")
    )
    is_subscription_cancelled = models.BooleanField(
        default=False,
        help_text=_("To determine when the user cancels their subscription")
    )
    status = models.CharField(
        max_length=20,
        default=StatusChoices.FREE,
        choices=StatusChoices.choices
    )
    original_period_start = models.DateTimeField(blank=True, null=True)
    subscription_starts_at = models.DateTimeField(blank=True, null=True, default=None)
    subscription_ends_at = models.DateTimeField(blank=True, null=True, default=None)

    def __str__(self):
        return f"{self.user.username} - {self.status}"

    def save(self, *args, **kwargs):
        """Override save to set original period start if not set."""
        if self.original_period_start is None and self.subscription_starts_at is not None:
            self.original_period_start = self.subscription_starts_at
        super().save(*args, **kwargs)


class Customer(models.Model):
    """Customer model for handling Paddle customer information."""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="customer_profile"
    )
    paddle_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    has_user_agreed_tos_and_privacy = models.BooleanField(default=False)
    created_at = models.DateField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - Customer"

    def create_or_update_paddle_customer(self):
        """
        Create or update Paddle customer.
        
        Returns:
            str: Paddle customer ID or None if failed
        """
        if not self.user.email:
            return None
            
        user_id = str(self.user.pk) if self.user.pk else ""
            
        payload = {
            "name": self.user.first_name or self.user.username,
            "email": self.user.email,
            "metadata": {
                "user_id": user_id,
                "username": self.user.username,
                "email": self.user.email,
            },
        }
        
        try:
            # CASE 1: Customer already exists → Update it
            if self.paddle_id:
                update_customer(
                    customer_id=str(self.paddle_id),
                    raw=False,
                    **payload,
                )
                return self.paddle_id

            # CASE 2: Customer does not exist → Create it
            customer_id = create_customer(
                raw=False,
                **payload,
            )
            
            if not customer_id:
                raise ValueError("Paddle did not return a valid customer ID")
                
            self.paddle_id = customer_id
            self.save(update_fields=["paddle_id"])
            return customer_id
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to sync Paddle customer for user {user_id}: {e}")
            return None
