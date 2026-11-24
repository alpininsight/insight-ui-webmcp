"""Installed Core resources are exposed once via Django staticfiles."""

from importlib.resources import files
from pathlib import Path

import pytest
from django.contrib.staticfiles.finders import find
from django.core.management import call_command
from django.template import Context, Template
from django.test import override_settings

from insight_ui_webmcp.finders import STATIC_PATH, CoreRuntimeFinder


def test_finder_reads_installed_core_without_adapter_copy():
    core = files("ais_webmcp").joinpath("assets/register.js")
    assert Path(find(STATIC_PATH)).read_bytes() == core.read_bytes()
    assert not files("insight_ui_webmcp").joinpath("static", STATIC_PATH).is_file()
    assert CoreRuntimeFinder().find(STATIC_PATH, find_all=True) == [str(core)]


@pytest.mark.parametrize(
    "path",
    [
        "../register.js",
        "/register.js",
        "assets/register.js",
        "insight_ui_webmcp/js/../build_hook.py",
        "insight_ui_webmcp/js/other.js",
    ],
)
def test_finder_exposes_only_the_runtime(path):
    finder = CoreRuntimeFinder()
    assert finder.find(path) == []
    assert finder.find(path, find_all=True) == []


def test_finder_honors_ignore_patterns():
    assert list(CoreRuntimeFinder().list(["*.js"])) == []
    assert list(CoreRuntimeFinder().list([STATIC_PATH])) == []
    assert [path for path, _ in CoreRuntimeFinder().list([])] == ["register.js"]


def test_collectstatic_keeps_established_path_and_identical_bytes(settings, tmp_path):
    settings.STATIC_ROOT = tmp_path
    call_command("collectstatic", interactive=False, verbosity=0)
    assert (tmp_path / STATIC_PATH).read_bytes() == files("ais_webmcp").joinpath(
        "assets/register.js"
    ).read_bytes()


def test_collected_runtime_manifest_and_rendered_url_use_installed_core(settings, tmp_path):
    settings.STATIC_ROOT = tmp_path
    settings.DEBUG = False
    # A fresh storage instance is required after changing the manifest backend.
    with override_settings(
        STORAGES={
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
            }
        }
    ):
        call_command("collectstatic", interactive=False, verbosity=0)
        from django.contrib.staticfiles.storage import staticfiles_storage

        hashed = staticfiles_storage.stored_name(STATIC_PATH)
        assert hashed != STATIC_PATH
        core_bytes = files("ais_webmcp").joinpath("assets/register.js").read_bytes()
        assert (tmp_path / hashed).read_bytes() == core_bytes
        html = Template("{% load webmcp_tags %}{% webmcp_assets %}").render(Context())
        assert staticfiles_storage.url(STATIC_PATH) in html


def test_webmcp_assets_tag_emits_established_path():
    html = Template("{% load webmcp_tags %}{% webmcp_assets %}").render(Context())
    assert STATIC_PATH in html
    assert html.count("<script ") == 1
    assert "data-insight-ui-webmcp" in html


@pytest.mark.parametrize("ignore_patterns", [None, [], ()])
def test_finder_accepts_optional_ignore_patterns(ignore_patterns):
    # Debug asset discovery passes None, whereas collectstatic passes a list.
    # Both must enumerate the one installed resource without restoring a copy.
    entries = list(CoreRuntimeFinder().list(ignore_patterns))
    assert len(entries) == 1
    path, storage = entries[0]
    assert path == "register.js"
    with storage.open(path, "rb") as source:
        assert source.read() == files("ais_webmcp").joinpath("assets/register.js").read_bytes()
