"""Visible attribution notice (#57): on by default, off via setting or tag."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from django.template import Context, Template
from django.test import override_settings

from insight_ui_webmcp.templatetags import webmcp_tags

pytestmark = pytest.mark.django_db(databases=[])

_ROOT = Path(__file__).resolve().parents[1]


def _render(tag: str = "{% webmcp_attribution %}") -> str:
    return Template("{% load webmcp_tags %}" + tag).render(Context())


@override_settings(WEBMCP_ENABLED=True)
def test_default_on_renders_product_license_company_and_link() -> None:
    html = _render()
    assert html.startswith('<small class="insight-ui-webmcp-attribution"')
    assert 'data-insight-ui-webmcp="attribution"' in html
    assert ">Insight UI WebMCP</a>" in html
    assert "Apache-2.0" in html
    assert "MPL-2.0" not in html
    assert "&copy; Alpin Insight Solutions GmbH &amp; Co. KG" in html
    assert '<a href="https://alpininsight.ai">' in html
    # Plain markup only: no script, no inline style, no new tab.
    for forbidden in ("<script", "style=", "target="):
        assert forbidden not in html


@override_settings(WEBMCP_ENABLED=True, WEBMCP_ATTRIBUTION=False)
def test_setting_off_hides_notice() -> None:
    assert _render() == ""


@override_settings(WEBMCP_ENABLED=True, WEBMCP_ATTRIBUTION=False)
def test_tag_override_can_show_when_setting_off() -> None:
    assert "Insight UI WebMCP" in _render("{% webmcp_attribution show=True %}")


@override_settings(WEBMCP_ENABLED=True)
def test_tag_override_can_hide() -> None:
    assert _render("{% webmcp_attribution show=False %}") == ""


@pytest.mark.parametrize("enabled", [False, None, "true", 1])
def test_webmcp_disabled_hides_notice(enabled: object) -> None:
    with override_settings(WEBMCP_ENABLED=enabled, WEBMCP_ATTRIBUTION=True):
        assert _render() == ""
        assert _render("{% webmcp_attribution show=True %}") == ""


def test_webmcp_enabled_unset_hides_notice() -> None:
    # tests.settings does not define WEBMCP_ENABLED; reusable code defaults off.
    assert _render() == ""


@override_settings(WEBMCP_ENABLED=True)
def test_css_class_is_appended_and_escaped() -> None:
    html = _render('{% webmcp_attribution css_class="text-sm opacity-80" %}')
    assert 'class="insight-ui-webmcp-attribution text-sm opacity-80"' in html
    html = _render('{% webmcp_attribution css_class="x\\" onclick=\\"y" %}')
    assert 'onclick="' not in html


@override_settings(WEBMCP_ENABLED=True, WEBMCP_ORIGIN_TRIAL_TOKEN="")
def test_notice_does_not_change_assets_tag() -> None:
    html = _render("{% webmcp_assets %}")
    assert "attribution" not in html
    assert "Alpin Insight" not in html


def test_license_constant_matches_distribution_metadata() -> None:
    pyproject = _ROOT / "pyproject.toml"
    license_expr = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["license"]
    assert webmcp_tags.ATTRIBUTION_LICENSE == license_expr


@pytest.mark.parametrize("readme", ["README.md"])
def test_attribution_documentation_matches_rendered_notice(readme: str) -> None:
    text = (_ROOT / readme).read_text(encoding="utf-8")
    assert f"{webmcp_tags.ATTRIBUTION_PRODUCT} · {webmcp_tags.ATTRIBUTION_LICENSE} ·" in text
