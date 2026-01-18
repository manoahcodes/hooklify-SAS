from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.profile_view, name='profile_update'),
    path('settings/', views.profile_settings_view, name='profile_settings'),
    path('billing/', views.billing_view, name='profile_billing'),
    path('cancel/subscription/', views.cancel_sub, name='profile_cancel_subscription'),
    path('request/', views.contact_info, name='contact_info'),
]