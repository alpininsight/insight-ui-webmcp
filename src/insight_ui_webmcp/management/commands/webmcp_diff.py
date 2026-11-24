"""Django front for ais-webmcp diff."""

from pathlib import Path

from django.core.management.base import BaseCommand

from insight_ui_webmcp.host_profiles import list_profiles
from insight_ui_webmcp.management.client import run_client


class Command(BaseCommand):
    help = "Local WebMCP diff; same implementation as ais-webmcp"

    def add_arguments(self, parser):
        parser.add_argument("left", type=Path)
        parser.add_argument("right", type=Path)

    def handle(self, *args, **options):
        arguments = ["diff", str(options["left"]), str(options["right"])]
        for name in list_profiles():
            arguments += ["--allow-profile", name]
        run_client(arguments, self.stdout)
