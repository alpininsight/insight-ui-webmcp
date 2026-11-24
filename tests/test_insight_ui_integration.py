"""Exercise the optional adapter against the actually installed Insight UI package.

The core-only test matrix deliberately does not require the optional UI package.
The dedicated interoperability lane requires it and tests both a published
release and an immutable 2.0 API source. A source probe is not RC publication.
"""

from __future__ import annotations

import importlib.util
import json
import os
from importlib.metadata import distribution
from importlib.resources import files
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.staticfiles.finders import find
from django.template import engines
from django.test import RequestFactory, override_settings
from django.urls import include, path
from django.utils import translation

if importlib.util.find_spec("insight_ui") is None:
    if os.environ.get("WEBMCP_REQUIRE_INSIGHT_UI") == "1":
        pytest.fail("The required installed Insight UI package is missing.")
    pytest.skip("optional UI package; covered by the mandatory UI lane", allow_module_level=True)

urlpatterns = [path("i18n/", include("django.conf.urls.i18n"))]

HOST_TEMPLATE = """{% extends "insight_ui/base.html" %}
{% load webmcp_tags %}
{% block content %}<h1>Adapter integration</h1>{% webmcp_attribution %}{% endblock %}
{% block extra_scripts %}{{ block.super }}
{% if webmcp_enabled %}{% webmcp_assets %}{% endif %}{% endblock %}
"""


def test_installed_ui_identity() -> None:
    installed = distribution("insight-ui")
    expected_version = os.environ.get("WEBMCP_EXPECT_INSIGHT_UI_VERSION")
    expected_source = os.environ.get("WEBMCP_EXPECT_INSIGHT_UI_SOURCE")
    if expected_version:
        assert installed.version == expected_version
    if expected_source:
        provenance = json.loads(installed.read_text("direct_url.json") or "null")
        assert provenance["vcs_info"]["commit_id"] == expected_source


@pytest.mark.parametrize("language", ["de", "en"])
@pytest.mark.parametrize("enabled", [False, True])
def test_adapter_composes_with_installed_ui_base(language: str, enabled: bool) -> None:
    apps = ["django.contrib.auth", *settings.INSTALLED_APPS, "insight_ui"]
    templates = [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "APP_DIRS": True,
            "OPTIONS": {
                "context_processors": [
                    "django.template.context_processors.request",
                    "insight_ui.context_processors.insight_ui_context",
                ]
            },
        }
    ]
    with (
        override_settings(
            INSTALLED_APPS=apps,
            TEMPLATES=templates,
            ROOT_URLCONF=__name__,
            LOGIN_URL="",
            USE_I18N=True,
            LANGUAGES=[("de", "Deutsch"), ("en", "English")],
            WEBMCP_ENABLED=enabled,
            WEBMCP_ORIGIN_TRIAL_TOKEN="",
            INSIGHT_UI={"assets": {"cdn_enabled": False}},
        ),
        translation.override(language),
    ):
        engine = engines["django"]
        base = engine.get_template("insight_ui/base.html")
        import insight_ui

        assert Path(base.origin.name).is_relative_to(Path(insight_ui.__file__).parent)
        request = RequestFactory().get("/")
        html = engine.from_string(HOST_TEMPLATE).render(
            {"webmcp_enabled": enabled}, request=request
        )
        assert f'<html lang="{language}"' in html
        assert "<h1>Adapter integration</h1>" in html
        assert ('data-insight-ui-webmcp="register"' in html) is enabled
        assert ('data-insight-ui-webmcp="attribution"' in html) is enabled
        assert find("insight_ui/css/tailwind.css")
        runtime = find("insight_ui_webmcp/js/register.js")
        assert runtime
        assert (
            Path(runtime).read_bytes()
            == files("ais_webmcp").joinpath("assets/register.js").read_bytes()
        )
