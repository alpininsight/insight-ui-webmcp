"""Django configuration front for the shared local doctor."""

import json

from ais_webmcp import __version__ as core_version
from ais_webmcp.operations import doctor, format_atomic_tree
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from insight_ui_webmcp import __version__ as adapter_version
from insight_ui_webmcp.host_profiles import list_profiles


class Command(BaseCommand):
    help = "Read-only local configuration checks; browser support remains unverified"

    def add_arguments(self, parser):
        parser.add_argument(
            "manifest", help="Local manifest path. http and https URLs are refused."
        )
        parser.add_argument("--html", help="Optional local HTML file. Remote URLs are refused.")
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument(
            "--tree",
            action="store_true",
            help="Print Atomic Design grouping: atom → molecule → organism (tool.group).",
        )

    def handle(self, *args, **options):
        report, code = doctor(
            options["manifest"],
            html=options["html"],
            extra_profiles=list_profiles(),
            origin_trial_configured=bool(getattr(settings, "WEBMCP_ORIGIN_TRIAL_TOKEN", "")),
            tree=options["tree"],
        )
        report["adapter_version"] = adapter_version
        report["core_version"] = core_version
        if options["format"] == "json":
            self.stdout.write(json.dumps(report, sort_keys=True))
        else:
            self.stdout.write(
                f"Core/runtime version: {core_version}; adapter version: {adapter_version}"
            )
            for row in report["checks"]:
                line = f"{row['check']}: {row['status']}"
                if row.get("detail"):
                    line = f"{line} ({row['detail']})"
                self.stdout.write(line)
            self.stdout.write(report["note"])
            if report.get("tree"):
                self.stdout.write(format_atomic_tree(report["tree"]).rstrip("\n"))
        if code:
            raise CommandError("WebMCP doctor failed", returncode=code)
