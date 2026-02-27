from apps.core.models import *

def user_notifications(request):
    if not request.user.is_authenticated:
        return {'notifications': []}
    
    notif_obj = Notification.objects.filter(recipient=request.user)
    
    return {
        'notifications': notif_obj
    }