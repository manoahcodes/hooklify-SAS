from django.urls import path
from . import views

urlpatterns = [
    path('contact', views.contact_view, name='contact'),
    path('request/', views.contact_info, name='contact_info'),
    path('profile/', views.profile_view, name='profile'),
]