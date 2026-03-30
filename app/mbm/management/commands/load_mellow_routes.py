from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Load mellow route fixtures with a single materialized view refresh"

    def add_arguments(self, parser):
        parser.add_argument("fixture", nargs="+", type=str)

    def handle(self, *args, **options):
        self.stdout.write("Disabling clean_ways refresh trigger...")
        with connection.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE mbm_mellowroute "
                "DISABLE TRIGGER refresh_clean_ways_on_mellowroute_insert;"
            )

        try:
            self.stdout.write("Loading fixtures...")
            call_command("loaddata", *options["fixture"])
        finally:
            self.stdout.write("Re-enabling clean_ways refresh trigger...")
            with connection.cursor() as cursor:
                cursor.execute(
                    "ALTER TABLE mbm_mellowroute "
                    "ENABLE TRIGGER refresh_clean_ways_on_mellowroute_insert;"
                )
                self.stdout.write("Refreshing clean_ways materialized view...")
                cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY clean_ways;")

        self.stdout.write(self.style.SUCCESS("Done."))
