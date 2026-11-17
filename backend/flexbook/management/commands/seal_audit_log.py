"""
python manage.py seal_audit_log           seal audit rows that have no seal yet (run once after installing FlexBook)
python manage.py seal_audit_log --verify  only check the chain and print the result (exit code 1 if broken)
"""
from django.core.management.base import BaseCommand, CommandError

from flexbook.sealing import seal_missing, verify_chain


class Command(BaseCommand):
    help = "Back-fill / verify the tamper-evident audit chain."

    def add_arguments(self, parser):
        parser.add_argument("--verify", action="store_true")

    def handle(self, *args, **opts):
        if not opts["verify"]:
            self.stdout.write(f"sealed {seal_missing()} audit row(s)")
        r = verify_chain()
        self.stdout.write(f"status={r['status']} rows={r['total_rows']} sealed={r['sealed_rows']} "
                          f"unsealed={r['unsealed_rows']} head={r['head_hash']}")
        if r["status"] == "broken":
            raise CommandError(f"AUDIT LOG TAMPERED near audit row {r['first_break']['audit_id']} ({r['first_break']['reason']})")
