"""Vendored negative corpus is locked to the installed Core artifact."""

import hashlib
import json
import os
import tomllib
from importlib.metadata import version
from importlib.resources import files
from io import StringIO
from pathlib import Path

from django.core.management import call_command


def test_installed_core_corpus_matches_provenance_and_expected_version():
    root = Path(__file__).parent / "fixtures"
    provenance = json.loads((root / "core-provenance.json").read_text())
    installed = files("ais_webmcp").joinpath("fixtures/cross-layer.json").read_bytes()
    assert installed == (root / "cross-layer.json").read_bytes()
    assert hashlib.sha256(installed).hexdigest() == provenance["sha256"]
    # This provenance also owns the independent minimum-Core archive probe.
    # Normal tests must use the locked Core. An explicit compatibility lane may
    # install a different real artifact without rewriting the registry lock.
    lock = tomllib.loads((root.parent.parent / "uv.lock").read_text())
    core = [package for package in lock["package"] if package["name"] == "ais-webmcp"]
    assert len(core) == 1
    expected = os.environ.get("WEBMCP_EXPECT_CORE_VERSION", core[0]["version"])
    assert version("ais-webmcp") == expected


def test_status_reports_both_versions():
    out = StringIO()
    call_command("webmcp_status", stdout=out)
    assert f"Core/runtime version: {version('ais-webmcp')}" in out.getvalue()
    assert f"Adapter version: {version('insight-ui-webmcp')}" in out.getvalue()


def test_doctor_reports_asset_owner_version():
    out = StringIO()
    call_command(
        "webmcp_doctor",
        str(Path(__file__).parent / "fixtures/manifests/valid/webpage.json"),
        format="json",
        stdout=out,
    )
    report = json.loads(out.getvalue())
    assert report["core_version"] == version("ais-webmcp")
    assert report["adapter_version"] == version("insight-ui-webmcp")


def test_missing_finder_fails_explicitly(settings):
    from insight_ui_webmcp.checks import check_core_runtime_finder

    settings.STATICFILES_FINDERS = ["django.contrib.staticfiles.finders.AppDirectoriesFinder"]
    failures = check_core_runtime_finder(None)
    assert [failure.id for failure in failures] == ["insight_ui_webmcp.E001"]
    settings.WEBMCP_ASSET_MODE = "cdn"
    assert check_core_runtime_finder(None) == []
