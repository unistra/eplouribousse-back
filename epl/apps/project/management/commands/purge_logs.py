import datetime
import re
from typing import Annotated

import typer
from django.utils import timezone
from django_tenants.utils import schema_context
from django_typer.management import TyperCommand

from epl.apps.project.models import ActionLog
from epl.apps.tenant.models import Consortium


class Command(TyperCommand):
    @staticmethod
    def parse_duration(value) -> datetime.timedelta | None:
        m = re.match(r"^(\d+)([DMYW])$", value)
        if not m:
            return None

        match m[2]:
            case "D":
                return datetime.timedelta(days=int(m[1]))
            case "W":
                return datetime.timedelta(weeks=int(m[1]))
            case "M":
                return datetime.timedelta(days=int(m[1]) * 30)
            case "Y":
                return datetime.timedelta(days=int(m[1]) * 365)
            case _:
                return None

    def handle(
        self,
        schema: Annotated[str, typer.Option(help="Schema to purge logs from")] = None,
        older_than: Annotated[
            str,
            typer.Option(help="Duration string (e.g., 30D for 30 days, 12M for 12 months)"),
        ] = "1Y",
        dry_run: Annotated[
            bool,
            typer.Option(help="If set, only count the logs that would be deleted without actually deleting them"),
        ] = False,
    ):
        """
        Purge logs older than the specified duration.

        Example duration strings: 30D (30 days), 4W (4 weeks), 12M (12 months), 1Y (1 year).

        Optionally specify a schema to target a specific tenant, by default all tenants' logs are purged.
        """

        now = timezone.now()
        delta = self.parse_duration(older_than)
        cutoff_date = now - delta

        self.secho(f"> Purging logs older than {cutoff_date} for schema: {schema or 'all'}", fg="green", bold=True)

        if not schema:
            schemas = self.get_schemas()
        else:
            schemas = [schema]

        for s in schemas:
            self.purge_schema(s, cutoff_date, dry_run)

    @staticmethod
    def get_schemas() -> list[str]:
        return [consortium.schema_name for consortium in Consortium.objects.all()]

    def purge_schema(self, schema: str, cutoff_date: datetime.datetime, dry_run: bool = False) -> int:
        with schema_context(schema):
            if dry_run:
                deleted_count = ActionLog.objects.filter(action_time__lt=cutoff_date).count()
            else:
                deleted_count, _ = ActionLog.objects.filter(action_time__lt=cutoff_date).delete()
            self.secho(
                f"🗑️ {schema}: Purged {deleted_count} log entries older than {cutoff_date:%Y-%m-%d %H:%M:%S%z}",
                bold=True,
                fg="red",
            )
            return deleted_count
