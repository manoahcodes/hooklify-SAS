from typing import Any
from django.core.management.base import BaseCommand

from apps.subscriptions.utils import utils as sub_utils

class Command(BaseCommand):
    def add_arguments(self, parser):
           parser.add_argument("--clear-inactive-subs", action="store_true", help="Sync and clear inactive subscriptions", default=False)
    
    def handle(self, *args: Any, **options):
        # print(options)
        # python manage.py sync_user_subs --clear-inactive-subs
        clear_inactive = options.get("clear_inactive_subs")
        if clear_inactive:
            print("Syncing and clearing inactive subscriptions...")
            sub_utils.clear_inactive_subscriptions()
        else:
             print("No valid options provided. Use --help for more information.")
             print("Done.")
        