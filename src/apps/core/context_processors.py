from apps.core.models import *

def user_notifications(request):
    # Fetch all notifications (cached by Django after the first query in a request)
    notif_obj = Notification.objects.filter(recipient=request.user)
    
    # Get selection from session or default to the first platform
    
    return {
        'notifications': notif_obj
    }