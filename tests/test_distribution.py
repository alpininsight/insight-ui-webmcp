"""Normal wheel/sdist installs of the adapter with the independently installed Core outside the checkout."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


def assert_public_package_links(message):
    entries = message.get_all("Project-URL", [])
    assert len(entries) == 2
    assert dict(entry.split(", ", 1) for entry in entries) == {
        "Homepage": "https://insight-ui-webmcp.alpininsight.ai/",
        "Documentation": "https://insight-ui-webmcp.alpininsight.ai/",
    }
    readme = message.get_payload()
    # PyPI renders this payload without the private repository's relative paths.
    for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", readme):
        if link.startswith("#"):
            continue
        target = urlsplit(link)
        assert target.scheme == "https" and target.netloc
    for link in re.findall(r"https?://[^\s)>\]]+", readme):
        target = urlsplit(link)
        assert not (
            target.hostname == "github.com"
            and target.path.split("/")[1:3] == ["alpininsight", "insight-ui-webmcp"]
        )


def assert_optional_ui_metadata(message):
    matches = [
        Requirement(raw)
        for raw in message.get_all("Requires-Dist", [])
        if Requirement(raw).name == "insight-ui"
    ]
    assert len(matches) == 1
    ui = matches[0]
    assert ui.url is None and ui.marker is not None
    assert ui.marker.evaluate({"extra": "ui"})
    assert not ui.marker.evaluate({"extra": ""})
    assert Version("1.15.1") in ui.specifier
    assert Version("2.0.0") in ui.specifier
    assert Version("3.0.0") not in ui.specifier


def core_requirement():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    matches = [
        Requirement(raw)
        for raw in project["project"]["dependencies"]
        if Requirement(raw).name == "ais-webmcp"
    ]
    assert len(matches) == 1
    requirement = matches[0]
    assert requirement.url is None and requirement.marker is None and not requirement.extras
    assert Version("0.1.0") in requirement.specifier
    assert Version("0.2.0") in requirement.specifier
    assert Version("0.3.0") not in requirement.specifier
    assert all(
        not (Version(bound.version).is_prerelease or Version(bound.version).is_postrelease)
        for bound in requirement.specifier
    )
    return requirement


def test_core_dependency_and_lock_use_stable_pypi():
    requirement = core_requirement()
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "ais-webmcp" not in project.get("tool", {}).get("uv", {}).get("sources", {})
    locked = tomllib.loads((ROOT / "uv.lock").read_text())
    core = [package for package in locked["package"] if package["name"] == "ais-webmcp"]
    assert len(core) == 1
    assert core[0]["source"] == {"registry": "https://pypi.org/simple"}
    assert Version(core[0]["version"]) in requirement.specifier
    assert not Version(core[0]["version"]).is_prerelease


def isolated_environment():
    """Keep interpreter/transport paths, without inheriting application credentials."""
    allowed = {
        "PATH",
        "HOME",
        "TMPDIR",
        "TMP",
        "TEMP",
        "LANG",
        "LC_ALL",
        "SSL_CERT_FILE",
        "UV_CACHE_DIR",
        # setup-python's Linux builds need this to resolve libpython. Do not
        # inherit Python import paths or settings from the source checkout.
        "LD_LIBRARY_PATH",
        "DYLD_LIBRARY_PATH",
    }
    return {key: value for key, value in os.environ.items() if key in allowed}


def test_isolated_environment_keeps_runtime_paths_without_host_configuration(monkeypatch):
    monkeypatch.setenv("LD_LIBRARY_PATH", "/runner/python/lib")
    monkeypatch.setenv("PYTHONPATH", "/host/source")
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "host.settings")
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "9.9.9")
    monkeypatch.setenv("HOST_TEST_CREDENTIAL", "dummy-test-value")
    env = isolated_environment()
    assert env["LD_LIBRARY_PATH"] == "/runner/python/lib"
    for key in (
        "PYTHONPATH",
        "DJANGO_SETTINGS_MODULE",
        "SETUPTOOLS_SCM_PRETEND_VERSION",
        "HOST_TEST_CREDENTIAL",
    ):
        assert key not in env


def run(*args, cwd=None, env=None):
    result = subprocess.run(args, cwd=cwd, env=env, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.mark.integration
@pytest.mark.parametrize("version", ["0.1.2", "0.1.3rc1"])
def test_normal_installs_and_delivery_inventory(tmp_path, version):
    uv = shutil.which("uv")
    assert uv, "uv is required"
    delivery = tmp_path / "delivery"
    run(
        uv,
        "run",
        "--locked",
        "python",
        "scripts/build_delivery.py",
        "--version",
        version,
        "--output",
        str(delivery),
        cwd=ROOT,
    )
    inventory = json.loads((delivery / "inventory.json").read_text())
    assert len(inventory["files"]) == 2
    assert inventory["version"] == version
    for entry in inventory["files"]:
        data = (delivery / entry["path"]).read_bytes()
        assert len(data) == entry["size"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
    dist = delivery / "dist"
    for wheel in dist.glob("*.whl"):
        with zipfile.ZipFile(wheel) as archive:
            metadata = archive.read(
                next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
            ).decode()
            for license_file in ("LICENSE", "NOTICE"):
                member = next(
                    n
                    for n in archive.namelist()
                    if n.endswith(f".dist-info/licenses/{license_file}")
                )
                assert archive.read(member) == (ROOT / license_file).read_bytes()
        headers = metadata.partition("\n\n")[0].splitlines()
        # PyPI shows a short PEP 639 expression, never the full license text.
        assert "License-Expression: Apache-2.0" in headers
        assert "License-File: LICENSE" in headers
        assert "License-File: NOTICE" in headers
        assert not any(line.startswith("License:") for line in headers)
        message = Parser().parsestr(metadata)
        assert_optional_ui_metadata(message)
        assert_public_package_links(message)
        classifiers = set(message.get_all("Classifier", []))
        assert "License :: OSI Approved :: Apache Software License" in classifiers
        assert "Framework :: Django :: 6.0" in classifiers
        assert "Framework :: Django :: 5.2" not in classifiers
        assert "Typing :: Typed" not in classifiers
        assert not any("MPL" in item or "Mozilla" in item for item in classifiers)
        assert f"Version: {version}" in headers
        dependencies = [
            Requirement(raw)
            for raw in Parser().parsestr(metadata).get_all("Requires-Dist", [])
            if Requirement(raw).name == "ais-webmcp"
        ]
        assert len(dependencies) == 1
        assert dependencies[0].url is None and dependencies[0].marker is None
        assert dependencies[0].specifier == core_requirement().specifier
    for artifact in [*dist.glob("*.whl"), *dist.glob("*.tar.gz")]:
        if artifact.suffix == ".whl":
            with zipfile.ZipFile(artifact) as archive:
                names = archive.namelist()
        else:
            with tarfile.open(artifact) as archive:
                names = archive.getnames()
                package_info = next(n for n in names if n.endswith("/PKG-INFO"))
                metadata_stream = archive.extractfile(package_info)
                assert metadata_stream is not None
                with metadata_stream:
                    message = Parser().parsestr(metadata_stream.read().decode())
                    assert_optional_ui_metadata(message)
                    assert_public_package_links(message)
                for license_file in ("LICENSE", "NOTICE"):
                    member = next(n for n in names if n.endswith(f"/{license_file}"))
                    stream = archive.extractfile(member)
                    assert stream is not None
                    with stream:
                        assert stream.read() == (ROOT / license_file).read_bytes()
        assert not any(
            name.startswith("docs/")
            or "/docs/" in name
            or "epp-api-changelog" in name
            or "mailbox" in name
            or name.endswith(".mbox")
            or name.endswith(".pth")
            or name.endswith("py.typed")
            or "output/" in name
            for name in names
        )
    for extension in ("whl", "tar.gz"):
        work = tmp_path / extension
        work.mkdir()
        env = isolated_environment()
        venv = work / "venv"
        run(uv, "venv", "--python", sys.executable, str(venv), env=env)
        python = str(venv / "bin/python")
        provenance = json.loads((ROOT / "tests/fixtures/core-provenance.json").read_text())
        # By default probe the published minimum. A compatibility lane can
        # instead install an explicit locally built Core artifact, while the
        # project lock retains its real published registry records.
        core_artifact = os.environ.get("WEBMCP_TEST_CORE_ARTIFACT")
        expected_core = (
            os.environ["WEBMCP_EXPECT_CORE_VERSION"] if core_artifact else provenance["version"]
        )
        client = core_artifact or f"ais-webmcp=={expected_core}"
        assert Version(expected_core) in core_requirement().specifier
        adapter = next(dist.glob(f"insight_ui_webmcp-*.{extension}"))
        run(
            uv,
            "pip",
            "install",
            "--python",
            python,
            "--default-index",
            "https://pypi.org/simple",
            str(client),
            env=env,
        )
        run(
            python,
            "-c",
            "import importlib.util; from importlib.metadata import version; "
            f"assert version('ais-webmcp') == {expected_core!r}; "
            "assert importlib.util.find_spec('django') is None",
            cwd=work,
            env=env,
        )
        cli = str(venv / "bin/ais-webmcp")
        manifest = work / "manifest.json"
        run(cli, "init", "--output", str(manifest), cwd=work, env=env)
        run(cli, "validate", str(manifest), cwd=work, env=env)
        run(cli, "doctor", str(manifest), "--format", "json", cwd=work, env=env)
        run(cli, "export", str(manifest), "--output", str(work / "export.yaml"), cwd=work, env=env)
        run(cli, "diff", str(manifest), str(work / "export.yaml"), cwd=work, env=env)
        # Core alone must accept the adapter's output schemas before Django or
        # the adapter is installed. A process-local adapter patch cannot help.
        webpage = work / "webpage.json"
        webpage.write_bytes((ROOT / "tests/fixtures/manifests/valid/webpage.json").read_bytes())
        for command in ("validate", "doctor"):
            run(cli, command, str(webpage), "--format", "json", cwd=work, env=env)
        run(
            uv,
            "pip",
            "install",
            "--python",
            python,
            "--default-index",
            "https://pypi.org/simple",
            "--find-links",
            str(dist),
            str(adapter),
            env=env,
        )
        run(uv, "pip", "check", "--python", python, env=env)
        smoke = work / "smoke.py"
        smoke.write_text(f"""from pathlib import Path
from django.conf import settings
settings.configure(SECRET_KEY="smoke",DEBUG=False,ROOT_URLCONF="urls",INSTALLED_APPS=["django.contrib.contenttypes","django.contrib.staticfiles","insight_ui_webmcp"],STATICFILES_FINDERS=["django.contrib.staticfiles.finders.AppDirectoriesFinder","insight_ui_webmcp.finders.CoreRuntimeFinder"],STATIC_URL="/static/",STATIC_ROOT={str(work / "staticfiles")!r},STORAGES={{"staticfiles":{{"BACKEND":"django.contrib.staticfiles.storage.ManifestStaticFilesStorage"}}}},TEMPLATES=[{{"BACKEND":"django.template.backends.django.DjangoTemplates","APP_DIRS":True}}])
import django
django.setup()
import insight_ui_webmcp, ais_webmcp
from importlib.metadata import version as installed_version
import importlib.util
assert importlib.util.find_spec("insight_ui") is None
assert insight_ui_webmcp.__version__ == {version!r}
assert installed_version("ais-webmcp") == {expected_core!r}
assert ais_webmcp.__version__ != insight_ui_webmcp.__version__
from django.core.management import call_command
call_command("check")
call_command("collectstatic",interactive=False,verbosity=0)
from django.template import Template,Context
html=Template("{{% load webmcp_tags %}}{{% webmcp_assets %}}").render(Context())
assert "register." in html and "data-insight-ui-webmcp" in html
from importlib.resources import files
from django.contrib.staticfiles.finders import find
core_bytes = files("ais_webmcp").joinpath("assets/register.js").read_bytes()
assert Path(find("insight_ui_webmcp/js/register.js")).read_bytes() == core_bytes
assert Path({str(work / "staticfiles/insight_ui_webmcp/js/register.js")!r}).read_bytes() == core_bytes
assert not files("insight_ui_webmcp").joinpath("static/insight_ui_webmcp/js/register.js").is_file()
call_command("webmcp_validate",{str(manifest)!r})
call_command("webmcp_doctor",{str(manifest)!r},format="json")
""")
        (work / "urls.py").write_text("urlpatterns=[]\n")
        run(python, str(smoke), cwd=work, env=env)
