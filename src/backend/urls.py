from django.contrib import admin
from django.urls import path, include

from backend import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('webhook/', include('apps.webhook.urls')),
    path('pricing/', include('apps.subscriptions.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('accounts/', include('apps.profiles.urls')),
    path('api', include('apps.core.urls')),

    path('', views.index, name='home'),
    path('about/', views.about_us_view, name='about_us'),
    path('terms-of-service/', views.terms_of_service_view, name='terms'),
    path('privacy-policy/', views.privacy_view, name='privacy'),
    path('refunds-policy/', views.refunds_view, name='refunds'),
    path('features/', views.features_view, name='features'),
    path('contact/', views.contact_view, name='contact'),
]

# Custom Error Handlers
handler404 = 'backend.views.custom_404_view'
handler500 = 'backend.views.custom_500_view'
