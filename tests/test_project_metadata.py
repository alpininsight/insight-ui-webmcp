"""PyPI metadata for the Django adapter.

Django 5.2 is not declared: ``requires`` is ``django>=6.0.4,<7``, so 5.2 cannot
be installed. ``py.typed`` and ``Typing :: Typed`` are omitted because the
public surface re-exports ``ais-webmcp`` with star imports.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]

_DOCS = "https://insight-ui-webmcp.alpininsight.ai/"


def _project() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def test_project_urls_only_advertise_the_current_public_site() -> None:
    urls = _project()["urls"]
    assert urls == {"Homepage": _DOCS, "Documentation": _DOCS}


def test_license_and_django_classifiers() -> None:
    project = _project()
    assert project["license"] == "Apache-2.0"
    classifiers = set(project["classifiers"])
    assert "License :: OSI Approved :: Apache Software License" in classifiers
    assert "Framework :: Django" in classifiers
    assert "Framework :: Django :: 6.0" in classifiers
    assert "Framework :: Django :: 5.2" not in classifiers
    assert "Typing :: Typed" not in classifiers
    assert not any("MPL" in item or "Mozilla" in item for item in classifiers)
    django = next(
        Requirement(raw) for raw in project["dependencies"] if Requirement(raw).name == "django"
    )
    assert Version("5.2") not in django.specifier
    assert Version("5.2.8") not in django.specifier
    assert Version("6.0.4") in django.specifier
    assert Version("6.1.1") in django.specifier
    assert Version("7.0") not in django.specifier


def test_package_is_not_marked_typed() -> None:
    package = ROOT / "src" / "insight_ui_webmcp"
    assert not (package / "py.typed").exists()
    assert list(package.rglob("py.typed")) == []


def test_optional_ui_range_supports_verified_api_families_without_becoming_required() -> None:
    project = _project()
    requirements = [Requirement(raw) for raw in project["optional-dependencies"]["ui"]]
    assert len(requirements) == 1
    ui = requirements[0]
    assert ui.name == "insight-ui" and ui.url is None and ui.marker is None
    assert not any(Requirement(raw).name == "insight-ui" for raw in project["dependencies"])
    for version in ("1.15.0", "1.15.1", "2.0.0", "2.9.0"):
        assert Version(version) in ui.specifier
    for version in ("1.14.9", "3.0.0", "4.0.0"):
        assert Version(version) not in ui.specifier
    # Synthetic boundary only: this does not assign or publish an RC version.
    assert ui.specifier.contains(Version("2.0.0rc1"), prereleases=True)
