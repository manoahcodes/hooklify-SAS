from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('ideas/', views.ideas, name='ideas'),
    path('create/', views.create, name='create'),
    path('library/projects/', views.projects, name='projects'),
    path('library/templates/', views.user_templates, name='templates'),
    path('library/history/', views.user_generation_history, name='history'),
    path('studio/', views.studio, name='studio')
    # path('tools/'),
    # path('library/'),

]