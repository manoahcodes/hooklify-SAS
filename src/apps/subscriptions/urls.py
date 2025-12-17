from django.urls import path
from . import views

urlpatterns = [
    path('', views.plans_view, name='plans'),
    path('<str:interval>/', views.plans_view, name='plans_interval'),
]