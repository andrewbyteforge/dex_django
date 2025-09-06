# APP: Django
# FILE: dex_django/apps/storage/management/commands/clear_mock_traders.py
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.storage.models import FollowedTrader, CopyTrade

class Command(BaseCommand):
    help = 'Clear all mock trader data from database'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion without prompt',
        )
    
    def handle(self, *args, **options):
        if not options['confirm']:
            confirm = input("This will DELETE all traders and copy trades. Are you sure? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Cancelled'))
                return
        
        with transaction.atomic():
            # Delete all copy trades first (foreign key constraint)
            copy_trades_deleted = CopyTrade.objects.all().delete()[0]
            
            # Delete all followed traders
            traders_deleted = FollowedTrader.objects.all().delete()[0]
            
        self.stdout.write(self.style.SUCCESS(
            f'Successfully deleted {traders_deleted} traders and {copy_trades_deleted} copy trades'
        ))