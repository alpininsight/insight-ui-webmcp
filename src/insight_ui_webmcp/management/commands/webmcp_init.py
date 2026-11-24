"""Django front for ais-webmcp init."""

from pathlib import Path

from django.core.management.base import BaseCommand

from insight_ui_webmcp.management.client import run_client


class Command(BaseCommand):
    help = "Local WebMCP init; same implementation as ais-webmcp"

    def add_arguments(self, parser):
        parser.add_argument("--output", type=Path)
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--static", action="store_true")

    def handle(self, *args, **options):
        arguments = ["init"]
        if options["output"] is not None:
            arguments += ["--output", str(options["output"])]
        for flag in ("force", "static"):
            if options[flag]:
                arguments.append("--" + flag)
        run_client(arguments, self.stdout)
