from django.contrib.auth import get_user_model
from apps.core.models import Notification

def send_system_broadcast(title, message, link=None, category='info'):
    """
    Efficiently creates a notification for EVERY active user in the system.
    """
    User = get_user_model()
    
    # 1. Get all active users IDs (fetching huge objects is slow, just get IDs)
    #    If you have >10k users, this should be done in a Celery task.
    user_ids = User.objects.filter(is_active=True).values_list('id', flat=True)

    # 2. Prepare the list of Notification objects in memory
    notifications = [
        Notification(
            recipient_id=user_id,  # Use _id to avoid fetching User objects
            title=title,
            message=message,
            category=category,
            external_link=link or '',
            is_read=False
        )
        for user_id in user_ids
    ]

    # 3. Bulk Insert (1 Query instead of N queries)
    #    batch_size=1000 protects your DB memory if you have massive user counts
    Notification.objects.bulk_create(notifications, batch_size=1000)

    print(f"Broadcast sent to {len(notifications)} users.")