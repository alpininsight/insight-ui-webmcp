"""Cross-layer output-schema contracts using the unmodified installed Core.

The Core console script does not import this package. A validator reference
taken before the package is imported must still reject a broken output schema.
``registerFromManifest`` must pass ``outputSchema`` through to
``document.modelContext.registerTool``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from importlib.resources import files
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WEBPAGE = REPO / "tests" / "fixtures" / "manifests" / "valid" / "webpage.json"


def _python_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONSAFEPATH"):
        env.pop(key, None)
    return env


def _run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, env=env, check=False, capture_output=True, text=True)


def test_package_does_not_import_itself_at_interpreter_startup() -> None:
    assert not list((REPO / "src").rglob("*.pth"))
    project = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "force-include" not in project
    assert ".pth" not in project


def test_previously_imported_validators_keep_the_draft_check(tmp_path: Path) -> None:
    script = tmp_path / "stale_validator.py"
    script.write_text(
        textwrap.dedent(
            f"""
            import json
            from pathlib import Path

            from ais_webmcp.validate import validate_data as early
            from webmcp_manifest.validate import validate_data as facade
            import ais_webmcp.operations as operations
            import ais_webmcp.validate as core

            assert early is facade is operations.validate_data is core.validate_data
            assert core.validate_data.__module__ == "ais_webmcp.validate"

            loader = core._load_schema_cached
            semantic = core._semantic_issues
            import insight_ui_webmcp
            import insight_ui_webmcp.validate
            assert core._load_schema_cached is loader
            assert core._semantic_issues is semantic

            assert core.validate_data is early
            assert core.validate_data.__module__ == "ais_webmcp.validate"
            assert facade is early

            def manifest(output_schema):
                tool = {{
                    "id": "list_sections",
                    "name": "List sections",
                    "description": "List available page section anchors on this host.",
                    "inputSchema": {{"type": "object", "properties": {{}}}},
                }}
                if output_schema is not None:
                    tool["outputSchema"] = output_schema
                return {{"profile": "webpage", "version": "1", "tools": [tool]}}

            missing = early(manifest(None))
            assert missing.ok, missing.issues

            valid = early(manifest({{"type": "array", "items": {{"type": "string"}}}}))
            assert valid.ok, valid.issues
            assert facade(manifest({{"type": "array", "items": {{"type": "string"}}}})).ok

            broken = early(manifest({{"type": "object", "properties": []}}))
            assert not broken.ok
            assert any(
                "outputSchema" in issue.path and "Draft 2020-12" in issue.message
                for issue in broken.issues
            )
            facade_broken = facade(manifest({{"type": "object", "properties": []}}))
            assert not facade_broken.ok
            assert any("Draft 2020-12" in issue.message for issue in facade_broken.issues)

            webpage = json.loads(Path({str(WEBPAGE)!r}).read_text(encoding="utf-8"))
            checked = early(webpage)
            assert checked.ok, checked.issues
            """
        ),
        encoding="utf-8",
    )
    result = _run([sys.executable, str(script)], _python_env())
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("command", ["validate", "doctor"])
@pytest.mark.parametrize("broken", [False, True])
def test_standalone_core_commands_validate_output_schemas(tmp_path, command, broken) -> None:
    payload = json.loads(WEBPAGE.read_text(encoding="utf-8"))
    if broken:
        payload["tools"][0]["outputSchema"] = {"type": "object", "properties": []}
    manifest = tmp_path / "webpage.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    cli = Path(sys.executable).parent / "ais-webmcp"
    result = subprocess.run(
        [str(cli), command, str(manifest), "--format", "json"],
        cwd=tmp_path,
        env=_python_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    if broken:
        assert result.returncode != 0, result.stdout + result.stderr
        if command == "validate":
            assert "outputSchema" in result.stdout + result.stderr
        else:
            checks = json.loads(result.stdout)["checks"]
            assert {"check": "manifest", "status": "error"} in checks
    else:
        assert result.returncode == 0, result.stdout + result.stderr


def _node() -> str:
    found = shutil.which("node") or shutil.which("nodejs")
    if found:
        return found
    candidate = Path("/exec-daemon/node")
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    pytest.fail("node is required for the browser registration contract")


def test_register_from_manifest_forwards_output_schema() -> None:
    register_js = files("ais_webmcp").joinpath("assets/register.js")
    program = textwrap.dedent(
        r"""
        const fs = require("fs");
        const registerPath = process.env.REGISTER_JS;
        const manifest = JSON.parse(fs.readFileSync(process.env.MANIFEST, "utf8"));

        function handlersFor(body) {
          const handlers = {};
          for (const tool of body.tools) handlers[tool.id] = function () { return null; };
          return handlers;
        }

        function boot() {
          const registered = [];
          global.document = {
            querySelector() { return null; },
            querySelectorAll() { return []; },
            modelContext: {
              registerTool(tool) {
                const snapshot = {};
                for (const key of Object.keys(tool)) {
                  snapshot[key] = typeof tool[key] === "function" ? { callable: true } : tool[key];
                }
                registered.push(snapshot);
                return Promise.resolve();
              },
            },
          };
          global.window = global;
          delete global.InsightUiWebmcp;
          delete require.cache[require.resolve(registerPath)];
          require(registerPath);
          return { registered, api: global.InsightUiWebmcp };
        }

        (async () => {
          const bridged = boot();
          const originalManifest = JSON.stringify(manifest);
          const result = await bridged.api.registerFromManifest(manifest, handlersFor(manifest));
          if (JSON.stringify(manifest) !== originalManifest) {
            throw new Error("runtime mutated the host manifest");
          }
          const byName = new Map(bridged.registered.map((tool) => [tool.name, tool]));
          for (const tool of manifest.tools) {
            const payload = byName.get(tool.id);
            if (tool.enabled === false) {
              if (payload) throw new Error("disabled tool was registered: " + tool.id);
              continue;
            }
            if (!payload) throw new Error("missing registration for " + tool.id);
            if (tool.outputSchema) {
              if (JSON.stringify(payload.outputSchema) !== JSON.stringify(tool.outputSchema)) {
                throw new Error("outputSchema was not forwarded for " + tool.id);
              }
            } else if (Object.prototype.hasOwnProperty.call(payload, "outputSchema")) {
              throw new Error("invented outputSchema for " + tool.id);
            }
            if (!payload.inputSchema) throw new Error("inputSchema missing for " + tool.id);
          }
          const enabled = manifest.tools.filter((tool) => tool.enabled !== false).length;
          if (result.registered !== enabled) {
            throw new Error("registered " + result.registered + " of " + enabled);
          }

          const leaked = { name: "list_sections", description: "after" };
          global.document.modelContext.registerTool(leaked);
          if (Object.prototype.hasOwnProperty.call(leaked, "outputSchema")) {
            throw new Error("registerTool stayed wrapped and wrote outputSchema onto the call");
          }
          const tail = bridged.registered[bridged.registered.length - 1];
          if (tail.outputSchema) throw new Error("schema map leaked after registerFromManifest");

          const direct = await global.InsightUiWebmcp.registerTool({
            id: "get_section",
            name: "Get section",
            description: "Text of the named section.",
            inputSchema: { type: "object", properties: {} },
            outputSchema: { type: "string", description: "Text content of the named section." },
            execute() { return "text"; },
          });
          if (!direct.ok) throw new Error(JSON.stringify(direct));
          const forwarded = bridged.registered[bridged.registered.length - 1];
          if (!forwarded.outputSchema || forwarded.outputSchema.type !== "string") {
            throw new Error("registerTool dropped outputSchema");
          }
          console.log("ok");
        })().catch((err) => {
          console.error(err && err.stack ? err.stack : err);
          process.exit(1);
        });
        """
    )
    env = _python_env()
    env["REGISTER_JS"] = str(register_js)
    env["MANIFEST"] = str(WEBPAGE)
    result = _run([_node(), "-e", program], env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok" in result.stdout
