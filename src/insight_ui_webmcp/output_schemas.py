"""Host output schemas for the shipped webpage tools.

The installed ais-webmcp dependency owns manifest validation and browser
registration. This adapter declares result shapes without changing Core.
Schemas name only values the webpage tool contract already returns.
``subscribe_newsletter`` stays disabled and has no declared result schema.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

_INPUT_KEYS = ("inputSchema", "parameters", "input_schema")
_DEFAULT_MAX_PRODUCTS = 12

# Read-only webpage tools. Navigation and consequential tools are omitted:
# their handlers do not publish a stable result shape in this package.
_READ_ONLY_WEBPAGE_TOOLS = (
    "list_sections",
    "get_section",
    "get_company_pitch",
    "list_products",
    "get_contact",
)


def max_products() -> int:
    """Upper bound published by the webpage ``list_products`` contract."""
    try:
        from ais_webmcp.profiles.webpage import MAX_PRODUCTS
    except ImportError:
        return _DEFAULT_MAX_PRODUCTS
    if isinstance(MAX_PRODUCTS, int) and MAX_PRODUCTS > 0:
        return MAX_PRODUCTS
    return _DEFAULT_MAX_PRODUCTS


def webpage_output_schemas() -> dict[str, dict[str, Any]]:
    """JSON Schemas for read-only webpage tools, keyed by tool id."""
    limit = max_products()
    return {
        "list_sections": {
            "type": "array",
            "description": "Page section anchor ids on this host.",
            "items": {"type": "string", "minLength": 1},
        },
        "get_section": {
            "type": "string",
            "description": "Text content of the named section.",
        },
        "get_company_pitch": {
            "type": "string",
            "description": "Short company or product pitch summary.",
        },
        "list_products": {
            "type": "array",
            "maxItems": limit,
            "description": f"Published product cards. At most {limit} entries.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "title": {"type": "string"},
                    "status": {
                        "type": "string",
                        "description": "Publication status, for example Private Beta.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Short description.",
                    },
                },
            },
        },
        "get_contact": {
            "description": "Public contact details for this host.",
        },
    }


def set_output_schema(tool: Mapping[str, Any], schema: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of a manifest tool with ``outputSchema`` set.

    Hosts such as insight-ui-docs call this (or write the same key in the
    committed manifest) for their own tools. The schema must describe the
    handler return and must not add fields the handler does not return.
    """
    if not isinstance(schema, Mapping):
        raise TypeError("outputSchema must be a JSON Schema object")
    updated = dict(tool)
    updated["outputSchema"] = dict(schema)
    return updated


def apply_builtin_output_schemas(payload: dict[str, Any]) -> dict[str, Any]:
    """Add webpage output schemas when a tool does not already declare one.

    Custom profiles, including a host's own tools, are returned unchanged.
    An ``outputSchema`` already stored on a tool is kept.
    """
    if payload.get("profile") != "webpage":
        return payload
    tools = payload.get("tools")
    if not isinstance(tools, list):
        return payload
    schemas = webpage_output_schemas()
    updated = dict(payload)
    rewritten: list[Any] = []
    for tool in tools:
        if not isinstance(tool, dict):
            rewritten.append(tool)
            continue
        schema = schemas.get(tool.get("id"))
        if schema is None or "outputSchema" in tool:
            rewritten.append(tool)
            continue
        rewritten.append(_insert_output_schema(tool, schema))
    updated["tools"] = rewritten
    return updated


def _insert_output_schema(tool: Mapping[str, Any], schema: Mapping[str, Any]) -> dict[str, Any]:
    rebuilt: dict[str, Any] = {}
    inserted = False
    for key, value in tool.items():
        rebuilt[key] = value
        if key in _INPUT_KEYS and not inserted:
            rebuilt["outputSchema"] = copy.deepcopy(dict(schema))
            inserted = True
    if not inserted:
        rebuilt["outputSchema"] = copy.deepcopy(dict(schema))
    return rebuilt


def readonly_webpage_tool_ids() -> tuple[str, ...]:
    """Tool ids that ship with an output schema."""
    return _READ_ONLY_WEBPAGE_TOOLS
