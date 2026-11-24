"""Validate WebMCP manifests with the same schema as ``ais-webmcp validate``."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from insight_ui_webmcp.cli import profile_argument
from insight_ui_webmcp.host_profiles import list_profiles
from insight_ui_webmcp.validate import exit_code, render, validate_path


class Command(BaseCommand):
    """Django front for the shared, Django-free manifest validator."""

    help = (
        "Validate WebMCP manifest files (JSON or YAML) against the shared schema. "
        "Same checks as the Django-free `ais-webmcp validate` command. "
        "Does not register tools or modify a live page."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "manifests",
            nargs="+",
            help="Manifest paths (.json, .yaml, or .yml).",
        )
        parser.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
            help="text (default) or json.",
        )
        parser.add_argument(
            "--allow-profile",
            action="append",
            type=profile_argument,
            default=None,
            help="Additional profile name to accept (repeatable). Built-ins always allowed.",
        )

    def handle(self, *args, **options) -> None:
        extra = [*list_profiles(), *(options["allow_profile"] or ())]
        results = [validate_path(Path(path), extra_profiles=extra) for path in options["manifests"]]
        self.stdout.write(render(results, options["format"]))
        code = exit_code(results)
        if code != 0:
            raise CommandError("WebMCP manifest validation failed", returncode=code)
