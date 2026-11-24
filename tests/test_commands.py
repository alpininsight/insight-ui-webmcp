"""Management-command contracts for prepare and status."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import Resolver404, get_resolver, resolve
from webmcp_manifest.profiles.webpage import WebpageProfile
from webmcp_manifest.validate import validate_data

from insight_ui_webmcp.output_schemas import (
    apply_builtin_output_schemas,
)


@pytest.mark.integration
def test_root_urlconf_is_a_module_and_resolves(rf) -> None:
    """``ROOT_URLCONF=[]`` is unhashable on Django 6.1; use a real module."""
    resolver = get_resolver()
    assert resolver.url_patterns == []
    request = rf.get("/")
    assert request.get_host() == "testserver"
    with pytest.raises(Resolver404):
        resolve("/")


@pytest.mark.integration
def test_prepare_dry_run_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    call_command("webmcp_prepare", "--profile", "webpage", "--dry-run")
    assert list(tmp_path.iterdir()) == []
    out = capsys.readouterr().out
    assert "Dry-run: no files written." in out
    assert "subscribe_newsletter" in out
    assert "webmcp.manifest.json" in out


@pytest.mark.integration
def test_prepare_refuses_existing_file_and_force_replaces_safely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    call_command("webmcp_prepare", "--profile", "webpage", "--manifest-version", "1")
    target = tmp_path / "webmcp.manifest.json"
    first = json.loads(target.read_text(encoding="utf-8"))
    expected = apply_builtin_output_schemas(WebpageProfile().build_manifest(version="1").to_dict())
    assert first == expected
    assert first["profile"] == "webpage"
    assert {tool["id"] for tool in first["tools"]} >= {"list_sections", "go_to_section"}

    target.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(CommandError, match="refusing to overwrite"):
        call_command("webmcp_prepare", "--profile", "webpage")
    assert target.read_text() == "{ this is not json"
    call_command("webmcp_prepare", "--profile", "webpage", "--manifest-version", "1", "--force")
    second = json.loads(target.read_text(encoding="utf-8"))
    assert second == first
    assert target.read_text(encoding="utf-8").endswith("\n")


@pytest.mark.integration
def test_prepare_unknown_profile_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(CommandError, match="Unknown WebMCP profile"):
        call_command("webmcp_prepare", "--profile", "does-not-exist")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.integration
def test_webmcp_status_reports_static_and_profiles(capsys) -> None:
    call_command("webmcp_status")
    out = capsys.readouterr().out
    assert "Insight UI WebMCP status" in out
    assert "Package static resource: OK (insight_ui_webmcp/js/register.js)" in out
    assert "webpage" in out
    assert "MISSING" not in out


REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_MANIFEST = REPO_ROOT / "tests" / "fixtures" / "manifests" / "valid" / "webpage.json"
DUPLICATE_MANIFEST = (
    REPO_ROOT / "tests" / "fixtures" / "manifests" / "invalid" / "duplicate-id.json"
)


@pytest.mark.integration
def test_prepare_output_passes_shared_validator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    call_command("webmcp_prepare", "--profile", "webpage", "--manifest-version", "1")
    payload = json.loads((tmp_path / "webmcp.manifest.json").read_text(encoding="utf-8"))
    result = validate_data(payload)
    assert result.ok, result.issues
    subscribe = next(tool for tool in payload["tools"] if tool["id"] == "subscribe_newsletter")
    assert subscribe["consequential"] is True
    assert subscribe["enabled"] is False


@pytest.mark.integration
def test_webmcp_validate_accepts_fixture(capsys) -> None:
    call_command("webmcp_validate", str(VALID_MANIFEST))
    out = capsys.readouterr().out
    assert "ok:" in out
    assert "unregister is AbortController" in out


@pytest.mark.integration
def test_webmcp_validate_rejects_duplicate_id(capsys) -> None:
    with pytest.raises(CommandError, match="validation failed"):
        call_command("webmcp_validate", str(DUPLICATE_MANIFEST))
    out = capsys.readouterr().out
    assert "duplicate tool id" in out
    assert "without explicit enable" not in out


@pytest.mark.integration
def test_webmcp_validate_json_format(capsys) -> None:
    call_command("webmcp_validate", str(VALID_MANIFEST), "--format", "json")
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["notes"]


@pytest.mark.integration
def test_webmcp_validate_allow_profile(tmp_path: Path, capsys) -> None:
    payload = json.loads(VALID_MANIFEST.read_text(encoding="utf-8"))
    payload["profile"] = "docs"
    target = tmp_path / "docs.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CommandError, match="validation failed"):
        call_command("webmcp_validate", str(target))
    capsys.readouterr()
    call_command("webmcp_validate", str(target), "--allow-profile", "docs")
    assert "ok:" in capsys.readouterr().out


@pytest.mark.integration
def test_prepare_debug_annotations_not_from_django_debug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, settings
) -> None:
    """Django DEBUG=True alone must not emit annotations.debugging (#9)."""
    settings.DEBUG = True
    monkeypatch.chdir(tmp_path)
    call_command("webmcp_prepare", "--profile", "webpage", "--manifest-version", "1")
    payload = json.loads((tmp_path / "webmcp.manifest.json").read_text(encoding="utf-8"))
    assert all(not (tool.get("annotations") or {}).get("debugging") for tool in payload["tools"])


@pytest.mark.integration
def test_prepare_debug_annotations_flag_is_noop_without_debug_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, settings
) -> None:
    """Webpage profile has no debugging tools; --debug-annotations stays silent (#9)."""
    settings.DEBUG = False
    monkeypatch.chdir(tmp_path)
    call_command(
        "webmcp_prepare",
        "--profile",
        "webpage",
        "--manifest-version",
        "1",
        "--debug-annotations",
    )
    payload = json.loads((tmp_path / "webmcp.manifest.json").read_text(encoding="utf-8"))
    assert all(not (tool.get("annotations") or {}).get("debugging") for tool in payload["tools"])
