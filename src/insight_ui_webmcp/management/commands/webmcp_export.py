"""Django front for ais-webmcp export."""

from pathlib import Path

from django.core.management.base import BaseCommand

from insight_ui_webmcp.host_profiles import list_profiles
from insight_ui_webmcp.management.client import run_client


class Command(BaseCommand):
    help = "Local WebMCP export; same implementation as ais-webmcp"

    def add_arguments(self, parser):
        parser.add_argument("source", type=Path)
        parser.add_argument("--output", type=Path, required=True)
        parser.add_argument(
            "--kind",
            choices=("manifest", "tools", "snippet"),
            default="manifest",
            help="manifest (canonical JSON/YAML), tools (JSON list), or snippet (HTML, no token).",
        )
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        arguments = [
            "export",
            str(options["source"]),
            "--output",
            str(options["output"]),
            "--kind",
            options["kind"],
        ]
        if options["force"]:
            arguments.append("--force")
        for name in list_profiles():
            arguments += ["--allow-profile", name]
        run_client(arguments, self.stdout)
