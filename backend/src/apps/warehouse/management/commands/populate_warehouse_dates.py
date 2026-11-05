from datetime import date, timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from apps.warehouse.models import DateDimension


class Command(BaseCommand):
    help = "Populate the warehouse calendar dimension (defaults to 2000 through 2035)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--start-year", type=int, default=2000)
        parser.add_argument("--end-year", type=int, default=2035)

    @transaction.atomic
    def handle(self, *_args: Any, **options: Any) -> None:
        start_year = int(options["start_year"])
        end_year = int(options["end_year"])
        if start_year < 1 or end_year > 9999 or start_year > end_year:
            raise CommandError("Years must form an inclusive range between 1 and 9999.")

        current = date(start_year, 1, 1)
        final = date(end_year, 12, 31)
        rows: list[DateDimension] = []
        while current <= final:
            row = DateDimension(calendar_date=current)
            row.sync_calendar_fields()
            rows.append(row)
            current += timedelta(days=1)

        DateDimension.objects.bulk_create(rows, batch_size=1000, ignore_conflicts=True)
        self.stdout.write(
            self.style.SUCCESS(
                f"Warehouse calendar covers {start_year}-01-01 through {end_year}-12-31."
            )
        )
