from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('ideas/', views.ideas, name='ideas'),
    path('create/', views.create, name='create'),
    path('library/projects/', views.projects, name='projects'),
    path('library/templates/', views.user_templates, name='templates'),
    path('library/history/', views.user_generation_history, name='history'),
    path('studio/', views.studio, name='studio'),

    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/mark-read/<int:pk>/', views.MarkNotificationReadView.as_view(), name='mark_notification_read'),
    path('notifications/mark-all-read/', views.MarkAllReadView.as_view(), name='mark_all_notifications_read'),
    path('notifications/delete/<int:pk>/', views.DeleteNotificationView.as_view(), name='delete_notification'),
    path('tools/viral/breakdown/', views.viral_breakdown_tool_view, name='viral_breakdown'),

]