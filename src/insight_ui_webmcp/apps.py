"""Django application configuration for Insight UI WebMCP."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class InsightUiWebmcpConfig(AppConfig):
    """Register static files and template tags without owning database state."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "insight_ui_webmcp"
    label = "insight_ui_webmcp"
    verbose_name = _("Insight UI WebMCP")

    def ready(self):
        from django.core.checks import Tags, register

        from .checks import check_core_runtime_finder

        register(Tags.staticfiles)(check_core_runtime_finder)
