from django.urls import path
from . import views

urlpatterns = [
    path('subscriptions/', views.paddle_subscription_webhook, name='paddle_subscriptions_webhook')
]