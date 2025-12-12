import uuid

from django.db import models, transaction
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver

from utils.billing import create_product, create_price, create_customer, update_customer
from allauth.account.signals import user_signed_up, email_confirmed
from allauth.socialaccount.signals import social_account_added

# Create your models here.
ALLOW_CUSTOM_SUBSCRIPTIONS = True
SUBSCRIPTION_PERMS = [
    ("influencer", "Influencer Permission"),  # to distinguish tutor users, subscription.tutor
    ("creator", "Creator Permission"),  # to distinguish creator users, subscription.creator
    ("free", "Free Permission")  # to distinguish free users, subscription.free
]


class Product(models.Model):
    name = models.CharField(max_length=100)
    uuid = models.UUIDField(default=uuid.uuid4, null=True, unique=True)
    description = models.TextField(
        null=True, blank=True, help_text="Description of the subscription plan"
    )
    groups = models.ManyToManyField(Group, related_name="subscriptions")
    active = models.BooleanField(default=True)
    permissions = models.ManyToManyField(
        Permission,
        related_name="subscriptions",
        limit_choices_to={
            "content_type__app_label": "subscriptions",
            "codename__in": [x[0] for x in SUBSCRIPTION_PERMS],
        },
    )
    paddle_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    order = models.IntegerField(default=1, help_text="Ordering on Django pricing page")
    featured = models.BooleanField(
        default=True, help_text="Featured on Django pricing page"
    )
    updated = models.DateTimeField(auto_now=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    features = models.TextField(
        help_text="Features for pricing page, seperated by new line",
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.name

    def create_paddle_subscription(self):
        """Automatically create Paddle product if missing."""
        if self.paddle_id:
            return self.paddle_id

        try:
            sub_id = create_product(
                raw=False,
                name=self.name,
                desc=self.description if self.description else "",
                metadata={
                    "subscription_id": self.id, 
                    "name": self.name,
                    "uuid": str(self.uuid),
                    },
            )

            if not sub_id:
                raise ValueError("Paddle did not return a valid product ID")

            self.paddle_id = sub_id
            self.save(update_fields=["paddle_id"])
            print(f"[OK] Paddle product created for {self.name}: {sub_id}")
            return sub_id

        except Exception as e:
            print(f"[ERROR] Failed to create Paddle subscription: {e}")
            return None

    class Meta:
        ordering = ["order", "featured", "-updated"]
        permissions = SUBSCRIPTION_PERMS

    def get_features_as_list(self):
        if not self.features:
            return []
        return [x.strip() for x in self.features.split("\n")]


@receiver(post_save, sender=Product)
def product_post_save(sender, instance, created, **kwargs):
    if created:
        instance.create_paddle_subscription()


class Price(models.Model):
    class IntervalChoices(models.TextChoices):
        MONTHLY = "month", "Monthly"
        YEARLY = "year", "Yearly"
        FREE = "free", "Free"

    subscription = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, related_name="prices"
    )
    paddle_id = models.CharField(max_length=255, null=True, blank=True)
    uuid = models.UUIDField(default=uuid.uuid4, null=True, unique=True)
    interval = models.CharField(
        max_length=255,
        default=IntervalChoices.MONTHLY,
        choices=IntervalChoices.choices,
        help_text="Type of recurring method whether monthly, yearly or free",
    )
    price = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        default=0.00,
        help_text="Price of the subscription plan",
    )
    display_price = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        default=0.00,
        help_text="Display price of the subscription plan",
    )
    order = models.IntegerField(default=1, help_text="Ordering on Django pricing page")
    featured = models.BooleanField(default=True, help_text="Featured on Pricing page")
    updated = models.DateTimeField(auto_now=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["subscription__order", "order", "featured", "-updated"]

    @property
    def display_features_list(self):
        if not self.subscription:
            return []
        return self.subscription.get_features_as_list()

    @property
    def product_paddle_id(self):
        if not self.subscription:
            return None
        return self.subscription.paddle_id

    @property
    def display_subscription_name(self):
        if not self.subscription:
            return "Plan"
        return self.subscription.name

    @property
    def paddle_currency(self):
        return "USD"

    @property
    def paddle_price(self):
        return int(self.price * 100)
    
    @property
    def retail_price(self):
        return int(self.retail_price * 100)

    @property
    def is_free(self):
        return self.interval == self.IntervalChoices.FREE or self.price == 0

    @property
    def display_description(self):
        return (
            self.subscription.description
            if self.subscription.description
            else "This subscription plan is still in the development pharse and is coming soon."
        )

    def __str__(self):
        return f"{self.subscription.name} - {self.price} {self.paddle_currency} / {self.interval}"

    def create_paddle_subscription_price(self):
        """Automatically create Paddle price product if missing."""
        if self.interval == self.IntervalChoices.FREE or self.price == 0:
            if not self.paddle_id:
                self.paddle_id = "FREE_PLAN"
                self.save(update_fields=["paddle_id"])
            print(
                f"[OK] Free plan '{self.subscription.name}' created locally (no Paddle ID required)."
            )
            return self.paddle_id

        if self.paddle_id:
            return self.paddle_id

        try:
            sub_id = create_price(
                raw=False,
                product_id=self.product_paddle_id,
                amount=self.paddle_price,
                currency_code=self.paddle_currency,
                interval=self.interval,
                desc=self.display_description,
                name=self.subscription.name,
                metadata={
                    "subscription_plan_id": self.subscription.id,
                    "subscription_plan_name": self.subscription.name,
                    "subscription_plan_uuid": str(self.uuid),
                },
            )

            if not sub_id:
                raise ValueError("Paddle did not return a valid product price ID")

            self.paddle_id = sub_id
            self.save(update_fields=["paddle_id"])

            print(
                f"[OK] Paddle product price created for {self.subscription.name}: {sub_id}"
            )
            return sub_id

        except Exception as e:
            print(f"[ERROR] Failed to create Paddle subscription price: {e}")
            return None

        if self.featured and self.subscription:
            # Ensure only one featured price per subscription
            qs = SubscriptionPrice.objects.filter(
                subscription=self.subscription,
                interval=self.interval,
            ).exclude(id=self.id)
            qs.update(featured=False)


@receiver(post_save, sender=Price)
def subscription_price_post_save(sender, instance, created, **kwargs):
    if created:
        instance.create_paddle_subscription_price()


class Subscriber(models.Model):
    class StatusChoices(models.TextChoices):
        ACTIVE = "active", "Active"
        CANCELED = "canceled", "Canceled"
        PASTDUE = "past_due", "Past Due"
        PAUSED = "paused", "Paused"
        TRIALING = "trialing", "Trialing"
        FREE = "free", "Free"


    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="subscriber", null=False
    )
    subscription = models.ForeignKey(
        Product, on_delete=models.CASCADE, null=True, related_name="subscription_product"
    )
    price = models.ForeignKey(
        Price,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscription_price",
    )
    paddle_subscriptions_id = models.CharField(max_length=255, null=True, blank=True)
    paddle_user_id = models.CharField(max_length=255, null=True, blank=True)
    paddle_price_id = models.CharField(max_length=255, null=True, blank=True)
    is_free_active = models.BooleanField(default=True, help_text="To determine when the user has an active free package, which the default")
    is_subscription_active = models.BooleanField(default=False, help_text="To determine when the user has activated their subscription")
    is_subscription_cancelled = models.BooleanField(default=False, help_text="To determine when the user cancels their subscription")
    status = models.CharField(default=StatusChoices.FREE, max_length=50, choices=StatusChoices.choices)
    original_period_start = models.DateTimeField(auto_now=False, auto_now_add=False, blank=True, null=True)
    subscription_starts_at = models.DateTimeField(auto_now=False, auto_now_add=False, blank=True, null=True, default=None)
    subscription_ends_at = models.DateTimeField(auto_now=False, auto_now_add=False, blank=True, null=True, default=None)
    created_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    
    def save(self, *args, **kwargs):
        if (self.original_period_start is None and self.subscription_starts_at is not None):
            self.original_period_start = self.subscription_starts_at

        super().save(*args, **kwargs)

    def __str__(self):
        return self.user.username


def user_subscription_post_save(sender, instance, created, **kwargs):
    """
    Signal handler to update user groups when user subscription changes.

    Args:
        sender: The model class that sent the signal
        instance: The actual UserSubscription instance being saved
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


post_save.connect(user_subscription_post_save, sender=Subscriber)

class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer_profile")
    paddle_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}"

    def create_or_update_paddle_customer(self):

        if not self.user.email:
            return None
        
        payload = {
            "name": self.user.first_name or self.user.username,
            "email": self.user.email,
            "metadata": {
                "user_id": self.user.id,
                "username": self.user.username,
                "email": self.user.email,
            },
        }

        try:
            # CASE 1: Customer already exists → Update it
            if self.paddle_id:
                update_customer(
                    customer_id=self.paddle_id,
                    raw=False,
                    **payload,
                )
                return self.paddle_id
            

            # CASE 2: Customer does not exist → Create it
            pdl_id = create_customer(
                raw=False,
                **payload,
            )

            if not pdl_id:
                raise ValueError("Paddle did not return a valid customer ID")
            
            self.paddle_id = pdl_id
            self.save(update_fields=["paddle_id"])
            return pdl_id
        
        except Exception as e:
            print(f"Failed to sync Paddle customer for user {self.user.id}: {e}")
            return None


def handle_user_signed_up(request, user, **kwargs):
    customer, created = Customer.objects.get_or_create(user=user)

    if user.email and user.emailaddress_set.filter(email=user.email, verified=True).exists():
        customer.create_or_update_paddle_customer()

def handle_email_confirmed(request, email_address, **kwargs):
    user = email_address.user
    customer, created = Customer.objects.get_or_create(user=user)

    if customer and not customer.paddle_id:
        customer.create_or_update_paddle_customer()

user_signed_up.connect(handle_user_signed_up)
social_account_added.connect(handle_user_signed_up)
email_confirmed.connect(handle_email_confirmed)