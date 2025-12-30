from paddle_billing import Client, Environment, Options
from paddle_billing.Resources.Customers.Operations import CreateCustomer, UpdateCustomer, ListCustomers
from paddle_billing.Resources.Products.Operations import CreateProduct, UpdateProduct
from paddle_billing.Resources.Prices.Operations import CreatePrice, UpdatePrice
from paddle_billing.Resources.Subscriptions.Operations import UpdateSubscription, ListSubscriptions, CancelSubscription
from paddle_billing.Entities.Shared.TaxCategory import TaxCategory
from paddle_billing.Entities.Shared.Money import Money

from decouple import config

# --- Paddle Client Setup ---
PADDLE_API_KEY = config("PADDLE_API_KEY", default="", cast=str)
paddle = Client(PADDLE_API_KEY, options=Options(Environment.SANDBOX))

# --- Utilities ---
def serialize_subscription_plan(subscription):
    """Safely serialize Paddle subscription details."""
    status = getattr(subscription, "status", None)
    period = getattr(subscription, "current_billing_period", None)

    start_at = getattr(period, "starts_at", None) if period else None
    end_at = getattr(period, "ends_at", None) if period else None

    data = {"status": status}
    if start_at:
        data["starts_at"] = start_at
    if end_at:
        data["ends_at"] = end_at
    return data


# --- Customer Operations ---
def create_customer(name="", email="", metadata=None, raw=False):
    metadata = metadata or {}
    response = paddle.customers.create(
        CreateCustomer(name=name, email=email, custom_data=metadata)
    )
    return response if raw else response.id


def update_customer(customer_id="", name="", email="", metadata=None, raw=False):
    metadata = metadata or {}
    response = paddle.customers.update(
        customer_id=customer_id,
        operation=UpdateCustomer(name=name, email=email, custom_data=metadata),
    )
    return response if raw else response.id


def get_customer(ctm_id, raw=True):
    response = paddle.customers.get(customer_id=ctm_id)
    return response if raw else response.id


# --- Product Operations ---
def create_product(name="", desc="", metadata=None, raw=False):
    metadata = metadata or {}
    response = paddle.products.create(
        CreateProduct(
            name=name, 
            description=desc, 
            custom_data=metadata, 
            tax_category=TaxCategory.Saas,
            )
    )
    return response if raw else response.id



def update_product(product_id="", name="", desc="", metadata=None, raw=False):
    metadata = metadata or {}
    response = paddle.products.update(
        product_id=product_id,
        operation=UpdateProduct(
            name=name,
            description=desc,
            custom_data=metadata,
            tax_category=TaxCategory.Saas,
        ),
    )
    return response if raw else response.id


# --- Price Operations ---

def create_price(
    product_id="",
    name="",
    desc="",
    amount="",
    currency_code="",
    interval="month",
    metadata=None,
    raw=False,
):
    metadata = metadata or {}
    response = paddle.prices.create(
        CreatePrice(
            description=desc,
            product_id=product_id,
            name=name,
            unit_price=Money(amount=str(amount), currency_code=currency_code),
            billing_cycle={"interval": interval, "frequency": 1},
            custom_data=metadata,
        )
    )
    return response if raw else response.id



def update_price(
    price_id="",
    name="",
    desc="",
    amount="",
    currency_code="",
    interval="month",
    metadata=None,
    raw=False,
):
    metadata = metadata or {}
    response = paddle.prices.update(
        price_id=price_id,
        operation=UpdatePrice(
            description=desc,
            name=name,
            unit_price=Money(amount=str(amount), currency_code=currency_code),
            billing_cycle={"interval": interval, "frequency": 1},
            custom_data=metadata,
        ),
    )
    return response if raw else response.id


# --- Subscription Operations ---

def update_subscription(sub_id="", price_id="", quantity=1, effective_option=str, raw=False):
    """
    Update a Paddle subscription's items or plan.
    :param sub_id: The subscription ID to update.
    :param price_id: The new price ID to switch to.
    :param quantity: The item quantity (default 1).
    :param effective_from: When to apply the change ("immediately" or "next_billing_period").
    """
    if not sub_id or not price_id:
        # This will be caught by the ValueError block in the decorator
        raise ValueError("Both sub_id and price_id must be provided.")


    response = paddle.subscriptions.update(
        subscription_id=sub_id,
        operation=UpdateSubscription(
            effective_from=effective_option,
            items=[
                {
                    "price_id": price_id,
                    "quantity": quantity,
                }
            ],
        ),
    )

    return response if raw else serialize_subscription_plan(response)



def get_subscription_plan(sub_id, raw=True):
    response = paddle.subscriptions.get(subscription_id=sub_id)
    return response if raw else serialize_subscription_plan(response)



def get_customer_subscription_plans(customer_id, status=[]):
    # This function doesn't use the 'raw' argument, so if an error occurs, 
    # the decorator will print the error and return None.
    return paddle.subscriptions.list(
        operation=ListSubscriptions(
            customer_ids=[customer_id],
            statuses=status,
        )
    )


def cancel_subscription(sub_id, effective_from, raw=True):
    response = paddle.subscriptions.cancel(
        subscription_id=sub_id,
        operation=CancelSubscription(
            effective_from=effective_from,
        ),
    )
    return response if raw else serialize_subscription_plan(response)