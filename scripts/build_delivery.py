"""Build only the Django adapter with an exact distribution inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import zipfile
from email.parser import Parser
from pathlib import Path


def build(version: str, output: Path):
    # Accept a final or canonical PEP 440 RC version of a nonzero GitVersion base.
    # Exclude other prereleases, dev/post/local versions, leading zeros and the "v" prefix.
    if (
        not re.fullmatch(
            r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:rc[1-9][0-9]{0,5})?",
            version,
        )
        or version.split("rc", 1)[0] == "0.0.0"
    ):
        raise ValueError("delivery requires an explicit nonzero GitVersion version")
    if output.exists() and any(output.iterdir()):
        raise ValueError("delivery output must be empty")
    epoch = subprocess.check_output(
        ["git", "show", "-s", "--format=%ct", "HEAD"], text=True
    ).strip()
    env = os.environ | {"SETUPTOOLS_SCM_PRETEND_VERSION": version, "SOURCE_DATE_EPOCH": epoch}
    dist = output / "dist"
    subprocess.run(["uv", "build", "--out-dir", str(dist.resolve())], env=env, check=True)
    wheels = sorted(dist.glob("*.whl"))
    if len(wheels) != 1 or len(list(dist.glob("*.tar.gz"))) != 1:
        raise ValueError("expected one adapter wheel and one sdist")
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            metadata = Parser().parsestr(
                archive.read(
                    next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
                ).decode()
            )
            if metadata["Name"] != "insight-ui-webmcp" or metadata["Version"] != version:
                raise ValueError("adapter metadata drift")
            if any(
                n.endswith(("/register.js", "/webmcp-manifest.schema.json"))
                for n in archive.namelist()
            ):
                raise ValueError("adapter must use installed Core resources")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    entries = [
        {
            "path": p.relative_to(output).as_posix(),
            "size": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
        for p in sorted([*dist.glob("*.whl"), *dist.glob("*.tar.gz")])
    ]
    inventory = {
        "version": version,
        "source_sha": revision,
        "source_dirty": dirty,
        "project": "insight-ui-webmcp",
        "files": entries,
    }
    (output / "inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    return inventory


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, default=Path("dist/delivery"))
    args = parser.parse_args()
    build(args.version, args.output)
