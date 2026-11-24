from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tracker.seed_data import seed_user_demo_data, seed_categories
from tracker.models import UserProfile

class Command(BaseCommand):
    help = 'Seeds initial categories, demo user and sample transactions'

    def handle(self, *args, **options):
        seed_categories()
        self.stdout.write(self.style.SUCCESS('Successfully seeded categories.'))

        # Check or create demo user
        demo_user, created = User.objects.get_or_create(
            username='demo@spendwise.com',
            defaults={
                'email': 'demo@spendwise.com',
                'first_name': 'Alex',
                'last_name': 'Morgan',
            }
        )
        if created or not demo_user.has_usable_password():
            demo_user.set_password('password123')
            demo_user.save()

        # Ensure profile exists
        if not hasattr(demo_user, 'profile'):
            UserProfile.objects.create(user=demo_user, currency='$', theme='light')

        seed_user_demo_data(demo_user, force_reset=True)
        self.stdout.write(self.style.SUCCESS(f'Successfully seeded demo data for {demo_user.email} (password: password123)'))
