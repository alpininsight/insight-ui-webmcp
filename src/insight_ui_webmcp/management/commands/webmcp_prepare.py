"""Prepare a host-facing WebMCP manifest for an Insight UI website host."""

from __future__ import annotations

import json
from pathlib import Path

from ais_webmcp.files import write_files
from django.core.management.base import BaseCommand, CommandError

from insight_ui_webmcp.host_profiles import get_profile, list_profiles
from insight_ui_webmcp.output_schemas import apply_builtin_output_schemas
from insight_ui_webmcp.validate import validate_data

MANIFEST_FILENAME = "webmcp.manifest.json"


class Command(BaseCommand):
    """Write (or dry-run) a WebMCP manifest for the selected profile."""

    help = (
        "Prepare webmcp.manifest.json for a webpage-style Insight UI host. "
        "Does not monkey-patch foreign repositories; writes into the current "
        "working directory so hosts can place and commit the file themselves."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--profile",
            default="webpage",
            help=f"Profile name (known: {', '.join(list_profiles()) or 'none'}).",
        )
        parser.add_argument(
            "--force", action="store_true", help="Explicitly replace an existing manifest"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print planned files and tools without writing.",
        )
        parser.add_argument(
            "--output",
            default=MANIFEST_FILENAME,
            help=f"Output path relative to cwd (default: {MANIFEST_FILENAME}).",
        )
        parser.add_argument(
            "--manifest-version",
            default="1",
            dest="manifest_version",
            help="Manifest version string (default: 1).",
        )
        parser.add_argument(
            "--debug-annotations",
            action="store_true",
            dest="debug_annotations",
            help=(
                "Emit annotations.debugging=true only for tools the profile marks "
                "as debugging tools (issue #9). Never derived from Django DEBUG "
                "or window.JS_DEBUG."
            ),
        )

    def handle(self, *args, **options) -> None:
        profile_name: str = options["profile"]
        dry_run: bool = options["dry_run"]
        output: str = options["output"]
        manifest_version: str = options["manifest_version"]

        try:
            profile = get_profile(profile_name)
        except KeyError as exc:
            raise CommandError(str(exc)) from exc

        # Explicit CLI opt-in only. Do not read django.conf.settings.DEBUG here.
        include_debugging = bool(options["debug_annotations"])
        manifest = profile.build_manifest(version=manifest_version)
        payload = apply_builtin_output_schemas(
            manifest.to_dict(include_debugging=include_debugging)
        )
        target = Path.cwd() / output
        # Same schema as `ais-webmcp validate` / webmcp_validate (issue #20 P0).
        checked = validate_data(payload, source=str(target), extra_profiles=list_profiles())
        if not checked.ok:
            details = "\n".join(f"{issue.path}: {issue.message}" for issue in checked.issues)
            raise CommandError(f"Refusing to write an invalid WebMCP manifest:\n{details}")

        self.stdout.write(self.style.NOTICE(f"Profile: {profile.name}"))
        self.stdout.write(f"Planned output: {target}")
        self.stdout.write(f"Anchors ({len(manifest.anchors)}): {', '.join(manifest.anchors)}")
        self.stdout.write(f"Tools ({len(manifest.tools)}):")
        for tool in manifest.tools:
            flag = " [consequential]" if tool.consequential else ""
            self.stdout.write(f"  - {tool.id}: {tool.description}{flag}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: no files written."))
            self.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))
            self._remind_tags()
            return

        result = write_files(
            {target: json.dumps(payload, indent=2, ensure_ascii=False) + "\n"},
            force=options["force"],
        )
        if result.exit_code:
            raise CommandError(result.report.strip(), returncode=result.exit_code)
        self.stdout.write(self.style.SUCCESS(f"Wrote {target}"))
        self.stdout.write(
            "Hosts should place/commit this file next to the site root "
            "(or document its deploy path). This command does not patch "
            "foreign repositories."
        )
        self._remind_tags()

    def _remind_tags(self) -> None:
        self.stdout.write("")
        self.stdout.write(
            "Reminder: add the following to your host base.html:\n"
            "  {% load webmcp_tags %}{% webmcp_assets %}\n"
            "Then call registerFromManifest with host handlers. "
            "The assets tag loads the installed Core runtime so each "
            "outputSchema reaches document.modelContext.registerTool. "
            "Consequential tools, including subscribe_newsletter, are written enabled false.\n"
            "An existing manifest is kept unless --force is passed, so a host enable is not cleared.\n"
            "Origin Trial tokens are not written here. Set WEBMCP_ORIGIN_TRIAL_TOKEN on the host "
            "to emit the meta tag; the value is not stored in this file.\n"
            "annotations.debugging is opt-in via --debug-annotations for tools marked "
            "debugging in the profile; Django DEBUG / JS_DEBUG never set it (#9)."
        )
