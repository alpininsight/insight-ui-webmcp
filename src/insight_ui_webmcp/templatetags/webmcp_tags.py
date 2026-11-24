"""Template tags for the opt-in WebMCP browser helper and attribution notice."""

from __future__ import annotations

from django import template
from django.conf import settings
from django.forms import BaseForm
from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe

from insight_ui_webmcp.assets import register_url
from insight_ui_webmcp.declarative import render_experimental_declarative_form

register = template.Library()

# Attribution notice (#57). Shown only when the host enabled WebMCP
# (``WEBMCP_ENABLED``); on by default, off with ``WEBMCP_ATTRIBUTION = False``.
ATTRIBUTION_PRODUCT = "Insight UI WebMCP"
ATTRIBUTION_LICENSE = "Apache-2.0"  # must match License-Expression in pyproject.toml
ATTRIBUTION_COMPANY = "Alpin Insight Solutions GmbH & Co. KG"
ATTRIBUTION_URL = "https://alpininsight.ai"


@register.simple_tag
def webmcp_assets() -> SafeString:
    """Emit a script tag for the WebMCP register helper (staticfiles).

    Usage in a host ``base.html``::

        {% load webmcp_tags %}
        {% webmcp_assets %}
    """
    url = register_url()
    script = format_html('<script src="{}" defer data-insight-ui-webmcp="register"></script>', url)
    token = getattr(settings, "WEBMCP_ORIGIN_TRIAL_TOKEN", "")
    if not isinstance(token, str) or not token.strip():
        return script
    # The token belongs in the page meta tag only. Callers must not log it.
    meta = format_html('<meta http-equiv="origin-trial" content="{}">', token.strip())
    return format_html("{}{}", meta, script)


@register.simple_tag
def webmcp_assets_inline_hint() -> SafeString:
    """Return an HTML comment reminding hosts to load the tag once in base.html."""
    return mark_safe("<!-- insight-ui-webmcp: prefer {% load webmcp_tags %}{% webmcp_assets %} -->")


def attribution_enabled(show: bool | None = None) -> bool:
    """Return whether the attribution notice should render.

    ``WEBMCP_ENABLED`` (host switch, default false) gates everything. A per-tag
    ``show`` overrides ``WEBMCP_ATTRIBUTION`` (default true) in both directions.
    """
    if getattr(settings, "WEBMCP_ENABLED", False) is not True:
        return False
    if show is not None:
        return bool(show)
    return getattr(settings, "WEBMCP_ATTRIBUTION", True) is not False


@register.simple_tag
def webmcp_attribution(show: bool | None = None, css_class: str = "") -> SafeString:
    """Render a small, accessible attribution notice, e.g. in the site footer.

    Usage::

        {% load webmcp_tags %}
        {% webmcp_attribution %}
        {% webmcp_attribution css_class="text-sm opacity-80" %}
        {% webmcp_attribution show=False %}

    Renders nothing unless ``WEBMCP_ENABLED`` is true. Plain server-rendered HTML:
    no script, no inline style; it inherits the host's text colour and font.
    """
    if not attribution_enabled(show):
        return mark_safe("")
    classes = " ".join(["insight-ui-webmcp-attribution", *str(css_class).split()])
    return format_html(
        '<small class="{}" data-insight-ui-webmcp="attribution" lang="en">'
        '<a href="{}">{}</a> &middot; {} &middot; &copy; {}</small>',
        classes,
        ATTRIBUTION_URL,
        ATTRIBUTION_PRODUCT,
        ATTRIBUTION_LICENSE,
        ATTRIBUTION_COMPANY,
    )


@register.simple_tag(takes_context=True)
def webmcp_experimental_declarative_form(
    context: template.Context,
    form: BaseForm,
    tool_name: str,
    tool_description: str,
    autosubmit: bool = False,
    method: str = "post",
    action: str = "",
    submit_label: str = "Submit",
) -> SafeString:
    """Render a Django form with the experimental declarative WebMCP attributes.

    Usage::

        {% load webmcp_tags %}
        {% webmcp_experimental_declarative_form form "search-cars" "Perform a car make/model search" %}
        {% webmcp_experimental_declarative_form form "search-cars" "Perform a car make/model search" autosubmit=True %}

    Field ``help_text`` is copied to ``toolparamdescription``. The tag does
    not register a tool and does not emit ``outputSchema``. See
    ``insight_ui_webmcp.declarative`` and ``docs/declarative-api.md``.
    """
    token = context.get("csrf_token") if hasattr(context, "get") else None
    return render_experimental_declarative_form(
        form,
        tool_name=tool_name,
        tool_description=tool_description,
        autosubmit=autosubmit,
        method=method,
        action=action,
        submit_label=submit_label,
        csrf_token=token,
    )
