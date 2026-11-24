"""Fail-closed publication/provenance and workflow policy checks."""

import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publication", ROOT / "scripts/check_publication.py")
publication = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publication)


PUBLIC_REVISION = "7152544c2f591ed277e17894db9ad11f551b3069"


def _validate_contributor_workflow(workflow):
    assert workflow["permissions"] == {"contents": "read"}
    for job in workflow["jobs"].values():
        assert all(value == "read" for value in job.get("permissions", {}).values())
        assert "environment" not in job
        assert "secrets" not in job
        if "uses" in job:
            assert re.fullmatch(
                r"alpininsight/\.github/\.github/workflows/(python-quality|repository-policy)\.yml@"
                + PUBLIC_REVISION,
                job["uses"],
            )
            assert "runs-on" not in job and "steps" not in job
        else:
            assert job["runs-on"] == "ubuntu-latest"
        for step in job.get("steps", []):
            assert "secrets." not in str(step)
            assert "gh-action-pypi-publish" not in str(step)


def _workflow_files(directory):
    return sorted([*directory.glob("*.yml"), *directory.glob("*.yaml")])


def _validate_source_release_workflow(workflow):
    assert workflow["permissions"] == {"contents": "read"}
    events = workflow.get("on", workflow.get(True))
    assert set(events) == {"workflow_dispatch"}
    inputs = events["workflow_dispatch"]["inputs"]
    assert inputs["release"]["default"] is False
    assert inputs["release_kind"]["options"] == ["stable", "rc"]
    assert inputs["release_kind"]["default"] == "stable"
    assert inputs["rc_number"]["default"] == "1"
    jobs = workflow["jobs"]
    source = jobs["source"]
    assert source["runs-on"] == "ubuntu-latest"
    assert all(value == "read" for value in source["permissions"].values())
    assert source["steps"][0]["run"] == 'test "$SOURCE_REF" = refs/heads/main'
    proof = source["steps"][-1]
    assert proof["env"]["ENABLED"] == "${{ vars.WEBMCP_PYPI_PUBLISH_ENABLED }}"
    assert 'test "$ENABLED" = true' in proof["run"]
    assert "--require-merged-pr" in proof["run"]
    assert "scripts/check_publication.py source" in proof["run"]
    assert jobs["version"]["needs"] == "source"
    release = jobs["release"]
    assert set(release["needs"]) == {"source", "version"}
    assert release["permissions"] == {"contents": "write"}
    assert (
        release["uses"]
        == "alpininsight/.github/.github/workflows/create-release.yml@" + PUBLIC_REVISION
    )
    args = release["with"]
    assert args["create"] == "${{ inputs.release }}"
    assert args["release_kind"] == "${{ inputs.release_kind }}"
    assert args["rc_number"] == "${{ inputs.rc_number }}"
    assert args["require_main"] is True
    assert args["target_version"] == "${{ needs.version.outputs.major_minor_patch }}"
    assert args["checkout_ref"] == "${{ github.sha }}"
    assert args["contract_revision"] == PUBLIC_REVISION
    assert re.fullmatch(r"[0-9a-f]{64}", args["contract_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", args["release_sha256"])
    assert "secrets." not in str(workflow)
    assert ".github-private" not in str(workflow)
    assert "gh-action-pypi-publish" not in str(workflow)


def _scan_contributor_directory(directory):
    for path in _workflow_files(directory):
        workflow = yaml.safe_load(path.read_text())
        if path.name == "release.yml":
            _validate_source_release_workflow(workflow)
        else:
            _validate_contributor_workflow(workflow)


def test_contributor_ci_delegates_only_to_the_pinned_public_catalog():
    workflows = _workflow_files(ROOT / ".github/workflows")
    assert [p.name for p in workflows] == ["ci.yml", "release.yml"]
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    _scan_contributor_directory(ROOT / ".github/workflows")
    policy = workflow["jobs"]["repository-policy"]
    assert policy["uses"].endswith("repository-policy.yml@" + PUBLIC_REVISION)
    assert policy["with"]["policy_revision"] == PUBLIC_REVISION
    assert (
        policy["with"]["policy_sha256"]
        == "e172ee9657581c2e47b3940f291d7aa00769bcb59cca8db8d75b168f49835d09"
    )
    assert policy["if"] == "github.event_name == 'pull_request'"
    assert "repository-policy" in workflow["jobs"]["gate"]["needs"]
    assert "pytest" in str(workflow["jobs"]["quality"])
    assert "django==6.0.4" in str(workflow["jobs"]["compatibility"])
    metadata_checkout = workflow["jobs"]["gate"]["steps"][0]["with"]
    assert metadata_checkout["ref"] == "${{ github.event.pull_request.base.sha }}"
    assert metadata_checkout["persist-credentials"] is False


@pytest.mark.parametrize(
    "drift",
    ["floating", "foreign", "private", "source-write", "unconditional-create", "version", "main"],
)
def test_source_release_refuses_boundary_drift(drift):
    import copy

    workflow = copy.deepcopy(yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text()))
    release = workflow["jobs"]["release"]
    if drift == "floating":
        release["uses"] = release["uses"].replace(PUBLIC_REVISION, "main")
    elif drift == "foreign":
        release["uses"] = release["uses"].replace("alpininsight/", "example/")
    elif drift == "private":
        release["uses"] = release["uses"].replace(
            "alpininsight/.github/", "alpininsight/.github-private/"
        )
    elif drift == "source-write":
        workflow["jobs"]["source"]["permissions"]["contents"] = "write"
    elif drift == "unconditional-create":
        release["with"]["create"] = True
    elif drift == "version":
        release["with"]["target_version"] = "99.0.0"
    else:
        release["with"]["require_main"] = False
    with pytest.raises(AssertionError):
        _validate_source_release_workflow(workflow)


def test_renovate_has_an_explicit_public_precommit_updater():
    config = json.loads((ROOT / "renovate.json").read_text())
    assert "github>alpininsight/.github:pre-commit" in config["extends"]


@pytest.mark.parametrize("drift", ["runner", "write", "secret", "publisher", "reusable"])
def test_contributor_boundary_rejects_executable_drift(drift):
    workflow = {
        "permissions": {"contents": "read"},
        "jobs": {"test": {"runs-on": "ubuntu-latest", "steps": [{"run": "true"}]}},
    }
    job = workflow["jobs"]["test"]
    if drift == "runner":
        job["runs-on"] = "self-hosted"
    elif drift == "write":
        job["permissions"] = {"contents": "write"}
    elif drift == "secret":
        job["steps"][0]["env"] = {"TOKEN": "${{ secrets.EXAMPLE_TOKEN }}"}
    elif drift == "publisher":
        job["steps"][0] = {"uses": "pypa/gh-action-pypi-publish@v1"}
    else:
        job["uses"] = "example/private/.github/workflows/quality.yml@main"
    with pytest.raises(AssertionError):
        _validate_contributor_workflow(workflow)


@pytest.mark.parametrize(
    "remote",
    [
        {},
        {"ais_webmcp-1.2.3-py3-none-any.whl": "0" * 64},
        "extra",
    ],
)
def test_registry_readback_is_exact(monkeypatch, tmp_path, remote):
    dist = tmp_path / "dist"
    dist.mkdir()
    digests = {}
    for name in (
        "insight_ui_webmcp-1.2.3-py3-none-any.whl",
        "insight_ui_webmcp-1.2.3.tar.gz",
    ):
        (dist / name).write_bytes(name.encode())
        digests[name] = hashlib.sha256(name.encode()).hexdigest()

    def urlopen(url, timeout):
        project = "insight_ui_webmcp"
        files = {k: v for k, v in digests.items() if k.startswith(project + "-")}
        if remote == "extra":
            files[f"{project}-1.2.3-py2-none-any.whl"] = "1" * 64
        elif project == "insight_ui_webmcp":
            files = remote
        payload = {"urls": [{"filename": k, "digests": {"sha256": v}} for k, v in files.items()]}
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(publication.urllib.request, "urlopen", urlopen)
    with pytest.raises(ValueError):
        publication.verify_index(tmp_path, "1.2.3")


def test_registry_readback_accepts_exact_match(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    for name in (
        "insight_ui_webmcp-1.2.3-py3-none-any.whl",
        "insight_ui_webmcp-1.2.3.tar.gz",
    ):
        (dist / name).write_bytes(name.encode())

    def urlopen(url, timeout):
        project = "insight_ui_webmcp"
        payload = {
            "urls": [
                {
                    "filename": p.name,
                    "digests": {"sha256": hashlib.sha256(p.read_bytes()).hexdigest()},
                }
                for p in dist.glob(project + "-*")
            ]
        }
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(publication.urllib.request, "urlopen", urlopen)
    publication.verify_index(tmp_path, "1.2.3")


@pytest.mark.parametrize("suffix", ["yml", "yaml"])
@pytest.mark.parametrize("drift", ["reusable", "runner", "write"])
def test_discovery_rejects_actual_unsafe_workflow_files(tmp_path, suffix, drift):
    workflow = {
        "permissions": {"contents": "read"},
        "jobs": {"check": {"runs-on": "ubuntu-latest", "steps": [{"run": "true"}]}},
    }
    job = workflow["jobs"]["check"]
    if drift == "reusable":
        job["uses"] = "example/private/.github/workflows/check.yml@main"
    elif drift == "runner":
        job["runs-on"] = "self-hosted"
    else:
        job["permissions"] = {"contents": "write"}
    (tmp_path / ("unsafe." + suffix)).write_text(yaml.safe_dump(workflow))
    with pytest.raises(AssertionError):
        _scan_contributor_directory(tmp_path)
