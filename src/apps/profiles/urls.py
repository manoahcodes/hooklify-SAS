from django.urls import path
from . import views

urlpatterns = [
    path('', views.contact_view, name='contact'),
    path('request/', views.contact_info, name='contact_info'),
]