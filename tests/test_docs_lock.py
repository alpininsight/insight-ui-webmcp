"""Guard public documentation and tracked text against private metadata drift."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DOCS = _ROOT / "docs"
_DOCS_REPO = "https://github.com/alpininsight/" + "insight-ui-webmcp-docs"
_PUBLIC_CONTACTS = {"security@alpininsight.ai"}
_DOCS_SITE = "https://insight-ui-webmcp.alpininsight.ai"


def _repo_docs() -> list[Path]:
    return [
        _ROOT / "README.md",
        _ROOT / "CHANGELOG.md",
        *sorted(p for p in _DOCS.rglob("*") if p.is_file()),
    ]


# Match categories, rather than retaining the personal facts that triggered them.
_RETIRED: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"[\w.+-]+@(?!example\.(?:com|org|net|invalid)\b)[\w.-]+\.[A-Za-z]{2,}", re.IGNORECASE
    ),
    re.compile(r"/(?:workspace|Users|home)/[^\s`]+/\.env\b"),
    re.compile(r"\b[A-Z][A-Z0-9_]*_IMAP_[A-Z_*]*"),
    re.compile(r"\bUID\s+\d+", re.IGNORECASE),
    re.compile(r"\bMessage-ID:\s*<", re.IGNORECASE),
    re.compile(r"bodies/\d+\.txt"),
    re.compile(
        r"https://github\.com/alpininsight/(?:\.github-private|insight-ui-webmcp-(?:docs|enterprise))\b"
    ),
)


def _scan_retired(blob: str, *, label: str = "synthetic") -> list[str]:
    offenders: list[str] = []
    for line_no, line in enumerate(blob.splitlines(), start=1):
        for pattern in _RETIRED:
            for match in pattern.finditer(line):
                if match.group(0).lower() not in _PUBLIC_CONTACTS:
                    offenders.append(f"{label}:{line_no}: {match.group(0)}")
    return offenders


def test_docs_moved_to_docs_repository() -> None:
    stub = _DOCS / "README.md"
    assert stub.is_file(), "docs/README.md stub missing"
    assert _DOCS_SITE in stub.read_text(encoding="utf-8")
    assert _DOCS_REPO not in stub.read_text(encoding="utf-8")
    # The guide/reference live only in the docs repository; no second copy here.
    assert not (_DOCS / "guide").exists(), "docs/guide belongs in insight-ui-webmcp-docs"
    assert not (_DOCS / "reference").exists(), "docs/reference belongs in insight-ui-webmcp-docs"
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    # README is the PyPI long_description: link the public website, never the private repo.
    assert f"{_DOCS_SITE}/docs/guide/" in readme
    assert _DOCS_REPO not in readme
    for pyproject in (_ROOT / "pyproject.toml",):
        text = pyproject.read_text(encoding="utf-8")
        assert f'Documentation = "{_DOCS_SITE}/"' in text


_LOCAL_DOC_LINK = re.compile(r"\]\((?:\.\./)*docs/(?:guide|reference)/")


def test_no_relative_links_into_moved_docs() -> None:
    offenders = [
        f"{doc.relative_to(_ROOT)}:{line_no}"
        for doc in _repo_docs()
        if doc.suffix == ".md"
        for line_no, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), start=1)
        if _LOCAL_DOC_LINK.search(line)
    ]
    assert not offenders, "relative links into moved docs:\n" + "\n".join(offenders)
    assert _LOCAL_DOC_LINK.search("[guide](docs/guide/README.md)")
    assert _LOCAL_DOC_LINK.search("[ADR](../docs/reference/adr/0001.md)")
    assert not _LOCAL_DOC_LINK.search(f"[guide]({_DOCS_REPO}/blob/develop/docs/guide/README.md)")


def test_no_retired_facts_in_repository_docs() -> None:
    offenders: list[str] = []
    import subprocess

    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=_ROOT).decode().split("\0")
    for name in filter(None, paths):
        path = _ROOT / name
        if not path.is_file() or path.suffix in {".png", ".jpg", ".woff2"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        offenders.extend(_scan_retired(text, label=name))
    assert not offenders, "retired facts found (must not reappear):\n" + "\n".join(offenders)


def test_negative_proof_stale_content_fails() -> None:
    """Prove the DocLock catches intentional drift (Negativnachweis)."""
    stale = "\n".join(
        [
            "user@" + "personal.invalid",
            "/workspace/" + "synthetic-contacts/.env",
            "SYNTHETIC_" + "IMAP_PASSWORD",
            "UID " + "12345",
            "Message-ID:" + " <synthetic@example.invalid>",
            "bodies/" + "12345.txt",
            "https://github.com/alpininsight/" + ".github-private/blob/main/README.md",
        ]
    )
    current = """
    Implementation target: document.modelContext.
    Primary sources: webmachinelearning.github.io/webmcp and Chrome WebMCP docs.
    Origin Trial tokens are never committed; use WEBMCP_ORIGIN_TRIAL_TOKEN on the host.
    """
    stale_hits = _scan_retired(stale, label="stale-fixture")
    assert len(stale_hits) == 7, (
        "Negativnachweis failed: expected multiple retired matches on intentional "
        f"stale content, got {len(stale_hits)}: {stale_hits}"
    )
    assert not _scan_retired(current, label="current-fixture"), (
        "current-shape fixture must stay clean under retired scanners"
    )


# executeTool takes the RegisteredTool from getTools() and an input object
# (Chrome 155+). A tool name or a JSON string is the shape a broken smoke used;
# host-facing docs must not show it.
_EXECUTE_TOOL_STRING_FORMS: tuple[re.Pattern[str], ...] = (
    re.compile(r"executeTool\(\s*[\"'`]"),
    re.compile(r"executeTool\([^,()]+,\s*(?:[\"'`]|JSON\.stringify)"),
)


def _scan_execute_tool_string_forms(blob: str) -> list[str]:
    return [
        f"{line_no}: {line.strip()}"
        for line_no, line in enumerate(blob.splitlines(), start=1)
        if any(pattern.search(line) for pattern in _EXECUTE_TOOL_STRING_FORMS)
    ]


def test_host_docs_use_executetool_object_contract() -> None:
    offenders: list[str] = []
    for doc in (_ROOT / "README.md", *sorted((_ROOT / "packages").glob("*/README.md"))):
        hits = _scan_execute_tool_string_forms(doc.read_text(encoding="utf-8"))
        offenders.extend(f"{doc.relative_to(_ROOT)}:{hit}" for hit in hits)
    assert not offenders, "executeTool must take RegisteredTool + object:\n" + "\n".join(offenders)


def test_executetool_scanner_negative_proof() -> None:
    stale = """
    await document.modelContext.executeTool("list_sections", "{}");
    await mc.executeTool(tool, '{"section":"trust"}');
    await mc.executeTool(tool, JSON.stringify(input));
    """
    current = """
    const result = await mc.executeTool(tool, { section: "trust" });
    await mc.executeTool(tools.find((t) => t.name === "list_sections"), {});
    """
    assert len(_scan_execute_tool_string_forms(stale)) == 3
    assert not _scan_execute_tool_string_forms(current)


# The root README keeps Cloudflare Edge WebMCP as an optional complement with a
# link to the reference page in the docs repository.
_CF_EDGE_RETIRED: tuple[re.Pattern[str], ...] = (
    re.compile(r"basgr/cf-webmcp", re.IGNORECASE),
    re.compile(
        r"replaces? (?:the )?(?:origin[- ]trial|registerTool|insight-ui-webmcp)", re.IGNORECASE
    ),
    re.compile(r"official (?:Cloudflare )?WAF[- ]skip", re.IGNORECASE),
)


def test_readme_cloudflare_edge_is_complement_only() -> None:
    text = (_ROOT / "README.md").read_text(encoding="utf-8")
    assert f"{_DOCS_SITE}/docs/guide/agents-and-edge/" in text
    assert "Browser tool registration stays at the origin." in text
    offenders = [
        f"{line_no}: {match.group(0)}"
        for line_no, line in enumerate(text.splitlines(), start=1)
        for pattern in _CF_EDGE_RETIRED
        if (match := pattern.search(line))
    ]
    assert not offenders, "README.md Cloudflare edge wording drifted:\n" + "\n".join(offenders)


def test_cloudflare_edge_scanner_negative_proof() -> None:
    stale = """
    Cloudflare Edge replaces the origin trial token.
    Use the native basgr/cf-webmcp bridge.
    Follow the official Cloudflare WAF-skip guide for /.webmcp/*.
    """
    hits = [p.pattern for line in stale.splitlines() for p in _CF_EDGE_RETIRED if p.search(line)]
    assert len(hits) == 3, hits


def test_public_security_contact_is_allowed_but_personal_contacts_are_not():
    assert not _scan_retired("Report vulnerabilities to security@alpininsight.ai.")
    for contact in [
        "synthetic-person@" + "alpininsight.ai",
        "synthetic-person@" + "personal.invalid",
    ]:
        assert _scan_retired(contact)


def test_allowed_security_contact_does_not_mask_later_private_contact():
    mixed = "Report to security@alpininsight.ai; CC synthetic-person@" + "personal.invalid"
    hits = _scan_retired(mixed)
    assert hits == ["synthetic:1: synthetic-person@" + "personal.invalid"], hits
    both_private = "a-person@" + "personal.invalid, b-person@" + "personal.invalid"
    assert len(_scan_retired(both_private)) == 2
