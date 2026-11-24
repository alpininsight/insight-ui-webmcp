"""Output schemas for shipped webpage tools and host-declared tools."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from insight_ui_webmcp.output_schemas import (
    apply_builtin_output_schemas,
    max_products,
    readonly_webpage_tool_ids,
    set_output_schema,
    webpage_output_schemas,
)

REPO = Path(__file__).resolve().parents[1]
WEBPAGE_JSON = REPO / "tests" / "fixtures" / "manifests" / "valid" / "webpage.json"
WEBPAGE_YAML = REPO / "tests" / "fixtures" / "manifests" / "valid" / "webpage.yaml"

_PRODUCT_FIELDS = {"name", "title", "status", "description"}


def _load(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def _schemas_are_draft_2020_12(schema: dict) -> None:
    Draft202012Validator.check_schema(schema)


def test_readonly_webpage_tools_match_the_shipped_contract() -> None:
    schemas = webpage_output_schemas()
    assert tuple(schemas) == readonly_webpage_tool_ids()
    for schema in schemas.values():
        _schemas_are_draft_2020_12(schema)

    sections = schemas["list_sections"]
    assert sections["type"] == "array"
    assert sections["items"] == {"type": "string", "minLength": 1}
    assert "properties" not in sections

    assert schemas["get_section"]["type"] == "string"
    assert "properties" not in schemas["get_section"]
    assert schemas["get_company_pitch"]["type"] == "string"
    assert "properties" not in schemas["get_company_pitch"]

    products = schemas["list_products"]
    assert products["type"] == "array"
    assert products["maxItems"] == max_products() == 12
    item = products["items"]
    assert set(item["properties"]) == _PRODUCT_FIELDS
    assert "required" not in item
    assert "additionalProperties" not in item

    contact = schemas["get_contact"]
    assert "properties" not in contact
    assert "type" not in contact
    assert "contact" in contact["description"].lower()


def test_builtin_schemas_do_not_invent_product_or_contact_fields() -> None:
    products = webpage_output_schemas()["list_products"]["items"]["properties"]
    assert set(products) == _PRODUCT_FIELDS
    contact = webpage_output_schemas()["get_contact"]
    assert "email" not in contact
    assert "phone" not in contact
    assert "properties" not in contact


@pytest.mark.parametrize("path", [WEBPAGE_JSON, WEBPAGE_YAML])
def test_committed_webpage_fixture_declares_readonly_output_schemas(path: Path) -> None:
    payload = _load(path)
    stripped = copy.deepcopy(payload)
    for tool in stripped["tools"]:
        tool.pop("outputSchema", None)
    assert apply_builtin_output_schemas(stripped) == payload

    by_id = {tool["id"]: tool for tool in payload["tools"]}
    for tool_id, schema in webpage_output_schemas().items():
        assert by_id[tool_id]["outputSchema"] == schema
        assert by_id[tool_id]["annotations"]["readOnlyHint"] is True

    subscribe = by_id["subscribe_newsletter"]
    assert subscribe["consequential"] is True
    assert subscribe["enabled"] is False
    assert "outputSchema" not in subscribe
    for tool_id in ("go_to_section", "open_legal", "start_conversation"):
        assert "outputSchema" not in by_id[tool_id]


def test_json_and_yaml_webpage_fixtures_match() -> None:
    assert _load(WEBPAGE_JSON) == _load(WEBPAGE_YAML)


def test_custom_profile_and_existing_schema_stay_put() -> None:
    host = {
        "profile": "docs",
        "version": "1",
        "tools": [
            {
                "id": "search_components",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ],
    }
    assert apply_builtin_output_schemas(host) == host

    webpage = {
        "profile": "webpage",
        "version": "1",
        "tools": [
            {
                "id": "list_sections",
                "inputSchema": {"type": "object", "properties": {}},
                "outputSchema": {"type": "string"},
            }
        ],
    }
    assert apply_builtin_output_schemas(webpage)["tools"][0]["outputSchema"] == {"type": "string"}


def test_set_output_schema_copies_the_tool() -> None:
    tool = {
        "id": "search_components",
        "name": "Search components",
        "description": "Search public components.",
        "inputSchema": {"type": "object", "properties": {}},
    }
    schema = {"type": "array", "items": {"type": "string"}}
    updated = set_output_schema(tool, schema)
    assert "outputSchema" not in tool
    assert updated["outputSchema"] == schema
    assert updated["id"] == "search_components"
    with pytest.raises(TypeError):
        set_output_schema(tool, ["not", "an", "object"])


def test_output_schema_must_be_json_schema_object() -> None:
    from webmcp_manifest.validate import validate_data

    def manifest(output_schema: object) -> dict:
        return {
            "profile": "webpage",
            "version": "1",
            "tools": [
                {
                    "id": "list_sections",
                    "name": "List sections",
                    "description": "List available page section anchors on this host.",
                    "inputSchema": {"type": "object", "properties": {}},
                    "outputSchema": output_schema,
                    "annotations": {"readOnlyHint": True},
                }
            ],
        }

    missing = manifest({"type": "array", "items": {"type": "string"}})
    missing["tools"][0].pop("outputSchema")
    assert validate_data(missing).ok

    assert validate_data(manifest(webpage_output_schemas()["list_sections"])).ok

    rejected = validate_data(manifest([]))
    assert not rejected.ok
    assert any("outputSchema" in issue.path for issue in rejected.issues)

    invalid = validate_data(manifest({"type": "object", "properties": []}))
    assert not invalid.ok
    assert any("outputSchema" in issue.path for issue in invalid.issues)


def test_doctor_does_not_mark_readonly_output_schemas_not_declared() -> None:
    """The WebMCP check reports a missing output schema as ``not declared``.

    Read-only webpage tools now declare one, so that status must not name them.
    """
    from ais_webmcp.operations import doctor

    report, _code = doctor(str(WEBPAGE_JSON))
    readonly = set(readonly_webpage_tool_ids())
    hits = [
        tool_id
        for row in _status_rows(report)
        if _row_says_not_declared(row)
        for tool_id in readonly
        if tool_id == row.get("id") or tool_id == row.get("tool") or tool_id in _row_text(row)
    ]
    assert hits == []


def _status_rows(node: object):
    if isinstance(node, dict):
        if "status" in node:
            yield node
        for value in node.values():
            yield from _status_rows(value)
    elif isinstance(node, list):
        for item in node:
            yield from _status_rows(item)


def _row_text(row: dict) -> str:
    return " ".join(
        str(row.get(key, "")) for key in ("detail", "message", "check", "name", "tool", "id")
    )


def _row_says_not_declared(row: dict) -> bool:
    status = str(row.get("status", "")).lower()
    return status == "not declared" or "not declared" in _row_text(row).lower()


def test_schema_checker_rejects_a_broken_schema() -> None:
    with pytest.raises(SchemaError):
        Draft202012Validator.check_schema({"type": "object", "properties": []})
