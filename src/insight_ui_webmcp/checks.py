"""Fail clearly when a host omits the installed-Core staticfiles finder."""

from django.conf import settings
from django.core.checks import Error

FINDER = "insight_ui_webmcp.finders.CoreRuntimeFinder"


def check_core_runtime_finder(app_configs, **kwargs):
    if (
        "django.contrib.staticfiles" in settings.INSTALLED_APPS
        and getattr(settings, "WEBMCP_ASSET_MODE", "local") == "local"
        and FINDER not in settings.STATICFILES_FINDERS
    ):
        return [
            Error(
                "Local WebMCP assets require the installed Core runtime finder.",
                hint=f"Append {FINDER!r} to the host's existing STATICFILES_FINDERS.",
                id="insight_ui_webmcp.E001",
            )
        ]
    return []
