"""Extension namespace adapter: local by default, immutable matching CDN pin."""

import re
from urllib.parse import urlsplit

from ais_webmcp import __version__ as core_version
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.templatetags.static import static


def register_url():
    mode = getattr(settings, "WEBMCP_ASSET_MODE", "local")
    if mode == "local":
        return static("insight_ui_webmcp/js/register.js")
    if mode != "cdn":
        raise ImproperlyConfigured("WEBMCP_ASSET_MODE must be local or cdn")
    pin = getattr(settings, "WEBMCP_CDN_VERSION", "")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", pin) or pin != core_version:
        raise ImproperlyConfigured(
            "WEBMCP_CDN_VERSION must be an immutable version matching the installed ais-webmcp core"
        )
    origin = getattr(settings, "WEBMCP_CDN_BASE_URL", "https://cdn.alpininsight.ai").rstrip("/")
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
    ):
        raise ImproperlyConfigured("WEBMCP_CDN_BASE_URL must be an HTTPS origin")
    return f"{origin}/ais-webmcp/v{pin}/register.js"
