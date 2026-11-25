"""Print role matrix for admin and analytics endpoints. Owner: Amina A."""
from django.core.management.base import BaseCommand

from core.permission_matrix import print_permission_matrix


class Command(BaseCommand):
    help = "Print the HTTP role permission matrix"

    def handle(self, *args, **options):
        print_permission_matrix(lambda line: self.stdout.write(line))
