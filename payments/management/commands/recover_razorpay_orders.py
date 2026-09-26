from django.core.management.base import BaseCommand

from payments.services import recover_stale_razorpay_orders


class Command(BaseCommand):
    help = "Manually reconcile CHECKOUT_PENDING Razorpay orders the webhook/callback never confirmed."

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes',
            type=int,
            default=15,
            help='Recover orders older than this many minutes (default 15)'
        )

    def handle(self, *args, **options):
        recovered = recover_stale_razorpay_orders(minutes=options['minutes'])
        if not recovered:
            self.stdout.write("Recovery complete. No abandoned paid orders found to recover.")
            return
        for entry in recovered:
            self.stdout.write(self.style.SUCCESS(f"Recovered order {entry['order_number']}"))
        self.stdout.write(self.style.SUCCESS(f"Recovery complete. {len(recovered)} order(s) recovered."))
