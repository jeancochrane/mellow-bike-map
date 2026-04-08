from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    """Management command that acts as a thin wrapper around the builtin
    `loaddata` management command, designed specifically for loading
    `MellowRoute` objects from fixtures.

    Since the `MellowRoute` model has a database trigger that refreshes the
    `clean_ways` materialized view on every edit, a naive `loaddata` call
    would refresh the materialized view for every `MellowRoute` in the fixture,
    thereby wasting a lot of time and hogging database resources. This command
    handles disabling that trigger prior to the `loaddata` call, then
    re-enabling it and refreshing the view once the data has finished loading."""

    help = "Load mellow route fixtures with a single materialized view refresh"

    def add_arguments(self, parser):
        parser.add_argument("fixture", nargs="+", type=str)

    def handle(self, *args, **options):
        self.stdout.write("Disabling clean_ways refresh trigger...")
        with connection.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE mbm_mellowroute "
                "DISABLE TRIGGER refresh_clean_ways_on_mellowroute_edit;"
            )

        try:
            self.stdout.write("Loading fixtures...")
            call_command("loaddata", *options["fixture"])
        finally:
            self.stdout.write("Re-enabling clean_ways refresh trigger...")
            with connection.cursor() as cursor:
                cursor.execute(
                    "ALTER TABLE mbm_mellowroute "
                    "ENABLE TRIGGER refresh_clean_ways_on_mellowroute_edit;"
                )
                self.stdout.write("Refreshing clean_ways materialized view...")
                cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY clean_ways;")

        self.stdout.write(self.style.SUCCESS("Done."))
