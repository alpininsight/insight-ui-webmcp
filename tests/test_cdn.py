from importlib.metadata import version

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.template import Context, Template

from insight_ui_webmcp.assets import register_url


def test_cdn_explicit_immutable_pin(settings, monkeypatch):
    monkeypatch.setattr("insight_ui_webmcp.assets.core_version", "1.2.3")
    settings.WEBMCP_ASSET_MODE = "cdn"
    settings.WEBMCP_CDN_VERSION = "1.2.3"
    settings.DEBUG = False
    url = "https://cdn.alpininsight.ai/ais-webmcp/v1.2.3/register.js"
    assert register_url() == url
    assert url in Template("{% load webmcp_tags %}{% webmcp_assets %}").render(Context())


@pytest.mark.parametrize("pin", ["latest", "develop", "main", "", "1.2.4", "v1.2.3", "1.2.3/other"])
def test_invalid_or_stale_pin(settings, monkeypatch, pin):
    monkeypatch.setattr("insight_ui_webmcp.assets.core_version", "1.2.3")
    settings.WEBMCP_ASSET_MODE = "cdn"
    settings.WEBMCP_CDN_VERSION = pin
    with pytest.raises(ImproperlyConfigured):
        register_url()


def test_wrong_cdn_namespace_or_origin(settings, monkeypatch):
    monkeypatch.setattr("insight_ui_webmcp.assets.core_version", "1.2.3")
    settings.WEBMCP_ASSET_MODE = "cdn"
    settings.WEBMCP_CDN_VERSION = "1.2.3"
    settings.WEBMCP_CDN_BASE_URL = "https://cdn.alpininsight.ai/insight-ui"
    with pytest.raises(ImproperlyConfigured):
        register_url()


def test_cdn_uses_installed_core_version_and_namespace(settings):
    installed = version("ais-webmcp")
    settings.WEBMCP_ASSET_MODE = "cdn"
    settings.WEBMCP_CDN_VERSION = installed
    settings.DEBUG = False
    url = f"https://cdn.alpininsight.ai/ais-webmcp/v{installed}/register.js"
    assert register_url() == url
    assert url in Template("{% load webmcp_tags %}{% webmcp_assets %}").render(Context())
    settings.WEBMCP_CDN_VERSION = "0.0.0"
    with pytest.raises(ImproperlyConfigured):
        register_url()
