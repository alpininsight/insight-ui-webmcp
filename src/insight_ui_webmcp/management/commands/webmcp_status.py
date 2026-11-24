"""Report WebMCP static asset availability and registered profiles."""

from __future__ import annotations

from importlib import resources

from ais_webmcp import __version__ as core_version
from django.conf import settings
from django.contrib.staticfiles.finders import find
from django.core.management.base import BaseCommand

from insight_ui_webmcp import __version__ as adapter_version
from insight_ui_webmcp.host_profiles import list_profiles

STATIC_REL = "insight_ui_webmcp/js/register.js"


class Command(BaseCommand):
    """Print whether the WebMCP static helper is importable and list profiles."""

    help = "Show WebMCP package status: static JS presence and registered profiles."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", type=str)
        parser.add_argument("--html", type=str)
        parser.add_argument(
            "--tree",
            action="store_true",
            help="With --manifest: print Atomic Design grouping (atom → molecule → organism).",
        )

    def handle(self, *args, **options) -> None:
        if options.get("manifest"):
            from django.core.management import call_command

            arguments = [options["manifest"]]
            if options.get("html"):
                arguments += ["--html", options["html"]]
            if options.get("tree"):
                arguments.append("--tree")
            call_command("webmcp_doctor", *arguments, stdout=self.stdout)
            return
        self.stdout.write(self.style.NOTICE("Insight UI WebMCP status"))
        self.stdout.write(f"Adapter version: {adapter_version}")
        self.stdout.write(f"Core/runtime version: {core_version}")
        self.stdout.write("")

        # Package resource check (works without STATICFILES_DIRS / collectstatic).
        package_ok = False
        try:
            root = resources.files("ais_webmcp")
            candidate = root.joinpath("assets/register.js")
            package_ok = candidate.is_file()
        except (TypeError, FileNotFoundError, ModuleNotFoundError, AttributeError):
            package_ok = False

        if package_ok:
            self.stdout.write(self.style.SUCCESS(f"Package static resource: OK ({STATIC_REL})"))
        else:
            self.stdout.write(self.style.ERROR(f"Package static resource: MISSING ({STATIC_REL})"))

        # Django staticfiles finder (optional; may be unset outside a host).
        found = find(STATIC_REL)
        if found:
            self.stdout.write(self.style.SUCCESS(f"staticfiles finder: {found}"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "staticfiles finder: not resolved "
                    "(configure insight_ui_webmcp.finders.CoreRuntimeFinder and run collectstatic)"
                )
            )

        profiles = list_profiles()
        self.stdout.write("")
        self.stdout.write(f"Registered profiles ({len(profiles)}):")
        if profiles:
            for name in profiles:
                self.stdout.write(f"  - {name}")
        else:
            self.stdout.write("  (none)")

        token = getattr(settings, "WEBMCP_ORIGIN_TRIAL_TOKEN", "")
        if isinstance(token, str) and token.strip():
            self.stdout.write("Origin Trial token: configured (value not printed)")
        else:
            self.stdout.write(
                "Origin Trial token: absent (helper stays a no-op without the browser API)"
            )
        self.stdout.write(
            "Browser check: this command cannot see document.modelContext. "
            "In the page, InsightUiWebmcp.status() reports ok, "
            "no-origin-trial-meta or no-model-context."
        )
        self.stdout.write(
            "subscribe_newsletter: generated manifests keep enabled false; "
            "this package does not register a newsletter handler."
        )
