from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('ideas/', views.ideas, name='ideas'),
    path('create/', views.create, name='create'),
    path('projects/', views.projects, name='projects'),
    # path('tools/'),
    # path('library/'),

]