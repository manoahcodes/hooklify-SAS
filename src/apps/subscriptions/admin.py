from django.contrib import admin
from .models import Product, Subscriber, Price, Customer

# Register your models here.
class SubscriberAdmin(admin.ModelAdmin):
    readonly_fields = (
        'user', 
        'subscription',
        'price',
        'status',
        'paddle_subscriptions_id', 
        'paddle_price_id', 
        'paddle_user_id',
        'is_free_active',
        'is_subscription_active', 
        'is_subscription_cancelled', 
        'subscription_starts_at', 
        'subscription_ends_at', 
        'original_period_start', 
        'created_at',
        )
    list_display = ('user', 'subscription', 'price', 'status', 'is_subscription_active')
    list_filter = ('subscription', 'status')

admin.site.register(Subscriber, SubscriberAdmin)

class PriceInline(admin.TabularInline):
    model = Price
    extra = 0
    can_delete = False
    readonly_fields = ('uuid',)

class ProductAdmin(admin.ModelAdmin):
    inlines = [PriceInline]
    readonly_fields = ('paddle_id', 'uuid')
    list_display = ('name', 'active', 'paddle_id')
    search_fields = ('name',)
    # list_filter = ('active',)
admin.site.register(Product, ProductAdmin)

class PriceAdmin(admin.ModelAdmin):
    readonly_fields = ('paddle_id', 'uuid')
    list_display = ('subscription', 'price', 'interval', 'paddle_id')
    search_fields = ('subscription__name',)
    list_filter = ('interval',)

admin.site.register(Price, PriceAdmin)


class CustomerAdmin(admin.ModelAdmin):
    readonly_fields = ('user', 'paddle_id', 'has_user_agreed_tos')
    list_display = ('user', 'paddle_id')
    # list_filter = ('user__username',)

admin.site.register(Customer, CustomerAdmin)