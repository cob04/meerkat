from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

USERNAME = "e2e"
PASSWORD = "e2e-password"


class Command(BaseCommand):
    help = "Create or reset the E2E test user with known credentials."

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=USERNAME,
            defaults={"is_staff": True, "is_superuser": True},
        )
        user.is_staff = True
        user.is_superuser = True
        user.set_password(PASSWORD)
        user.save()
        verb = "Created" if created else "Reset"
        self.stdout.write(f"{verb} test user '{USERNAME}'.")
