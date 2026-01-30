from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('ideas/', views.ideas, name='ideas'),
    # path('tools/'),
    # path('library/'),

]