"""
python manage.py mfa_setup <email> [--reset] [--disable] [--show-code]

Turns on two-step login for one account and prints the key to type into an authenticator app
(Google Authenticator, Authy, Microsoft Authenticator: "Enter a setup key"). Needed for every staff role.
Owner: Amina A. (Architecture & Security)
"""
from django.core.management.base import BaseCommand, CommandError

from accounts import mfa
from accounts.models import User


class Command(BaseCommand):
    help = "Enable (or disable) two-step login for a user and print the authenticator setup key."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--reset", action="store_true", help="make a NEW secret even if one exists")
        parser.add_argument("--disable", action="store_true", help="turn two-step login off for this user")
        parser.add_argument("--show-code", action="store_true", help="also print the current 6-digit code (demo only)")

    def handle(self, *args, email, reset, disable, show_code, **opts):
        user = User.objects.select_related("role").filter(email=email.strip().lower()).first()
        if user is None:
            raise CommandError(f"No user {email}")
        if disable:
            user.mfa_enabled, user.mfa_secret = False, ""
            user.save(update_fields=["mfa_enabled", "mfa_secret"])
            self.stdout.write(self.style.WARNING(f"Two-step login OFF for {user.email} ({user.role.name})."))
            return
        if reset or not user.mfa_secret:
            user.mfa_secret = mfa.generate_secret()
        user.mfa_enabled = True
        user.save(update_fields=["mfa_enabled", "mfa_secret"])
        self.stdout.write(self.style.SUCCESS(f"Two-step login ON for {user.email} ({user.role.name})."))
        self.stdout.write(f"  Setup key : {user.mfa_secret}")
        self.stdout.write(f"  otpauth   : {mfa.provisioning_uri(user)}")
        if show_code:
            self.stdout.write(f"  Code now  : {mfa.current_code(user)}   (changes every 30 s)")
