from .models import Subscriber

def subscriber(request):
    if not request.user.is_authenticated:
        return {}

    sub = (
        Subscriber.objects
        .select_related("subscription", "price")
        .filter(user=request.user)
        .first()
    )

    return {
        "subscriber": sub
    }
