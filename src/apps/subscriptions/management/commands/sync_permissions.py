from typing import Any
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Prefetch

from subscriptions.models import Product

class Command(BaseCommand):
    help = 'Sync subscription permissions to associated groups'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
    
    def handle(self, *args: Any, **options):
        dry_run = options['dry_run']
        verbosity = options.get('verbosity', 1)
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN: No changes will be made')
            )
        
        self.stdout.write('Syncing subscription permissions to groups...')
        
        # Use select_related and prefetch_related to optimize database queries
        subscriptions = Product.objects.filter(active=True).prefetch_related(
            Prefetch('groups'),
            Prefetch('permissions')
        )
        
        subscription_count = 0
        group_count = 0
        error_count = 0
        
        for subscription in subscriptions:
            subscription_count += 1
            
            if verbosity >= 2:
                self.stdout.write(
                    f"Processing subscription: {subscription} "
                    f"({subscription.groups.count()} groups, "
                    f"{subscription.permissions.count()} permissions)"
                )
            
            subscription_permissions = list(subscription.permissions.all())
            
            if not subscription_permissions:
                self.stdout.write(
                    self.style.WARNING(
                        f"Subscription {subscription} has no permissions assigned"
                    ),
                    verbosity=2
                )
            
            for group in subscription.groups.all():
                group_count += 1
                
                try:
                    if not dry_run:
                        # Use atomic transaction for each group to ensure data consistency
                        with transaction.atomic():
                            group.permissions.set(subscription_permissions)
                    
                    if verbosity >= 2:
                        self.stdout.write(
                            f"  → Updated group '{group.name}' with "
                            f"{len(subscription_permissions)} permissions"
                        )
                        
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed to update group '{group.name}' for "
                            f"subscription {subscription}: {str(e)}"
                        )
                    )
        
        # Summary output
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSync completed: "
                f"{subscription_count} subscriptions, "
                f"{group_count} groups processed"
            )
        )
        
        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(f"Errors encountered: {error_count}")
            )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: No actual changes were made"
                )
            )