"""Host wiring for Origin Trial meta and the default-off newsletter tool."""

import pytest
from ais_webmcp.manifest import ToolSpec
from django.template import Context, Template

TOKEN = "OT-TOKEN-DO-NOT-LOG"


def _render():
    return Template("{% load webmcp_tags %}{% webmcp_assets %}").render(Context())


@pytest.mark.django_db
def test_assets_omit_origin_trial_meta_by_default(settings):
    settings.WEBMCP_ORIGIN_TRIAL_TOKEN = ""
    html = _render()
    assert "data-insight-ui-webmcp" in html
    assert "origin-trial" not in html
    assert TOKEN not in html


@pytest.mark.django_db
def test_assets_emit_origin_trial_meta_only_when_configured(settings):
    settings.WEBMCP_ORIGIN_TRIAL_TOKEN = f"  {TOKEN}  "
    html = _render()
    assert html.index("origin-trial") < html.index("register.js")
    assert f'content="{TOKEN}"' in html
    settings.WEBMCP_ORIGIN_TRIAL_TOKEN = "  "
    assert "origin-trial" not in _render()


@pytest.mark.django_db
def test_origin_trial_token_is_escaped_and_status_hides_it(settings, capsys):
    from django.core.management import call_command

    settings.WEBMCP_ORIGIN_TRIAL_TOKEN = '<script>alert("x")</script>'
    html = _render()
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    call_command("webmcp_status")
    out = capsys.readouterr().out
    assert "Origin Trial token: configured (value not printed)" in out
    assert "alert" not in out
    assert "subscribe_newsletter: generated manifests keep enabled false" in out
    assert "InsightUiWebmcp.status()" in out
    assert "no-origin-trial-meta" in out


def test_shipped_helper_exposes_browser_status():
    from importlib import resources

    script = (
        resources.files("ais_webmcp").joinpath("assets", "register.js").read_text(encoding="utf-8")
    )
    for reason in ("no-origin-trial-meta", "no-model-context"):
        assert reason in script
    assert "meta[http-equiv]" in script


def test_consequential_tool_cannot_opt_itself_in():
    tool = ToolSpec("subscribe_newsletter", "Subscribe", "Subscribe", consequential=True)
    payload = tool.to_dict()
    assert payload["enabled"] is False
    assert payload["annotations"]["consequentialHint"] is True
