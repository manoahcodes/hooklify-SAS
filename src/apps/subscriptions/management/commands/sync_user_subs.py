from typing import Any
from django.core.management.base import BaseCommand

from apps.subscriptions.utils import utils as sub_utils

class Command(BaseCommand):
    help = "Synchronize subscriptions and normalize billing state"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear-inactive-subs",
            action="store_true",
            help="Cancel orphan Paddle subscriptions",
        )

        parser.add_argument(
            "--normalize-canceled",
            action="store_true",
            help="Convert canceled subscriptions into FREE accounts",
        )

        parser.add_argument(
            "--all",
            action="store_true",
            help="Run all subscription sync tasks (recommended)",
        )

    def handle(self, *args: Any, **options):
        run_all = options.get("all")
        clear_inactive = options.get("clear_inactive_subs")
        normalize_canceled = options.get("normalize_canceled")

        if not any([run_all, clear_inactive, normalize_canceled]):
            self.stdout.write(
                self.style.WARNING(
                    "No options provided. Use --all or --help for details."
                )
            )
            return

        self.stdout.write("▶ Starting subscription sync tasks...")

        if run_all or clear_inactive:
            self.stdout.write("• Clearing orphan Paddle subscriptions...")
            sub_utils.clear_inactive_subscriptions()

        if run_all or normalize_canceled:
            self.stdout.write("• Normalizing canceled subscriptions → FREE...")
            sub_utils.normalize_canceled_subscribers()

        self.stdout.write(self.style.SUCCESS("✔ Subscription sync completed"))
