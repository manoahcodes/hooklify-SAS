from django.urls import path, include
from apps.core import views

urlpatterns = [
    path('', views.update_platform, name='update_platform'),
]