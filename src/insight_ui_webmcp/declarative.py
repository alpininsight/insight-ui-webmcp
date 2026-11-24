"""Experimental WebMCP declarative form markup.

The declarative form API lives in the W3C explainer
(``webmachinelearning/webmcp`` ``declarative-api-explainer.md``) and in
Chrome's origin trial. It is not part of the normative WebMCP specification,
and the explainer still marks input-schema synthesis as unfinished.
``outputSchema`` on a declarative form has no HTML attribute there.

This module emits the attributes that explainer currently names and checks
the markup before returning it. The companion descriptor is the argument
object for ``document.modelContext.registerTool``. A missing ``outputSchema``
is left off that object. See ``docs/declarative-api.md``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from html import unescape
from html.parser import HTMLParser
from typing import Any

from django import forms
from django.forms import BaseForm
from django.forms.utils import ErrorList
from django.utils.html import format_html, strip_tags
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import gettext as _

# Attribute names from declarative-api-explainer.md and Chrome's declarative
# API documentation. Tests lock these literals to that proposal.
FORM_TOOL_NAME_ATTR = "toolname"
FORM_TOOL_DESCRIPTION_ATTR = "tooldescription"
FORM_TOOL_AUTOSUBMIT_ATTR = "toolautosubmit"
CONTROL_PARAM_DESCRIPTION_ATTR = "toolparamdescription"

REGISTER_TOOL_API = "document.modelContext.registerTool"

_FORM_TOOL_ATTRS = frozenset(
    {
        FORM_TOOL_NAME_ATTR,
        FORM_TOOL_DESCRIPTION_ATTR,
        FORM_TOOL_AUTOSUBMIT_ATTR,
    }
)
_ALLOWED_TOOL_ATTRS = _FORM_TOOL_ATTRS | frozenset({CONTROL_PARAM_DESCRIPTION_ATTR})

# registerTool rejects an empty name, a name longer than 128, and any code
# point other than ASCII alphanumeric, "_", "-", or ".".
_TOOL_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_METHOD = re.compile(r"^(?:get|post)$", re.IGNORECASE)

_UNSUPPORTED_WIDGETS = (
    forms.FileInput,
    forms.SelectMultiple,
    forms.CheckboxSelectMultiple,
    forms.MultiWidget,
)


class DeclarativeFormError(ValueError):
    """The form cannot be exposed with the current declarative proposal."""


class DeclarativeUnsupportedField(DeclarativeFormError):
    """A field has no honest mapping onto the current proposal."""

    def __init__(self, field_name: str, reason: str) -> None:
        self.field_name = field_name
        super().__init__(f"Field {field_name!r} cannot be exposed declaratively: {reason}")


class DeclarativeMarkupError(DeclarativeFormError):
    """Emitted markup does not match the declarative attribute proposal."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__("; ".join(issues))


def _plain_text(value: object) -> str:
    """Plain text for a label or help string.

    Tags are removed first, then entities are decoded, so ``BMW &amp; Ford``
    becomes ``BMW & Ford`` before a later escape for HTML or JSON.
    """
    return " ".join(unescape(strip_tags(str(value))).split())


def _require_tool_identity(tool_name: str, tool_description: str) -> tuple[str, str]:
    name = _plain_text(tool_name)
    description = _plain_text(tool_description)
    if not _TOOL_NAME.fullmatch(name):
        raise DeclarativeFormError(
            "toolname must be 1-128 characters of ASCII letters, digits, '_', '-' or '.'; "
            f"{tool_name!r} does not match document.modelContext.registerTool"
        )
    if not description:
        raise DeclarativeFormError("tooldescription must be a non-empty string")
    return name, description


def _json_object(schema: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    if isinstance(schema, (str, bytes)) or not isinstance(schema, Mapping):
        raise TypeError(f"{label} must be a JSON Schema object")
    try:
        encoded = json.dumps(schema, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{label} must be a JSON-compatible object") from exc
    decoded = json.loads(encoded)
    if not isinstance(decoded, dict):
        raise TypeError(f"{label} must be a JSON Schema object")
    return decoded


def _explicit_description(
    bound: forms.BoundField,
    param_descriptions: Mapping[str, object] | None,
) -> str | None:
    if param_descriptions is not None and bound.name in param_descriptions:
        text = _plain_text(param_descriptions[bound.name])
        return text or None
    if bound.help_text:
        text = _plain_text(bound.help_text)
        return text or None
    return None


def _label_text(bound: forms.BoundField) -> str | None:
    text = _plain_text(bound.label)
    return text or None


def _reject_unsupported_widget(bound: forms.BoundField) -> None:
    widget = bound.field.widget
    if isinstance(widget, _UNSUPPORTED_WIDGETS):
        raise DeclarativeUnsupportedField(
            bound.name,
            f"widget {type(widget).__name__} has no stable mapping in this slice",
        )


def _choice_schema(bound: forms.BoundField) -> dict[str, Any]:
    field = bound.field
    if not isinstance(field, forms.ChoiceField):
        raise DeclarativeUnsupportedField(bound.name, "expected a ChoiceField")
    enum: list[str] = []
    any_of: list[dict[str, str]] = []
    seen: set[str] = set()
    for option_value, option_label in field.choices:
        if isinstance(option_label, (list, tuple)):
            raise DeclarativeUnsupportedField(
                bound.name,
                "grouped choices are not in this experimental slice",
            )
        if option_value is None or option_value == "":
            continue
        text = str(option_value)
        if text in seen:
            raise DeclarativeUnsupportedField(
                bound.name,
                f"distinct choice values both stringify to {text!r}",
            )
        seen.add(text)
        option: dict[str, str] = {"type": "string", "const": text}
        title = _plain_text(option_label)
        if title:
            option["title"] = title
        enum.append(text)
        any_of.append(option)
    schema: dict[str, Any] = {"type": "string"}
    if enum:
        schema["enum"] = enum
        schema["anyOf"] = any_of
    return schema


def _value_schema(bound: forms.BoundField) -> dict[str, Any]:
    """JSON Schema preview for one visible field.

    ``minimum``, ``maximum``, ``minLength`` and ``maxLength`` are omitted.
    The explainer still marks reduction of ``min``, ``max`` and ``step`` as
    unfinished, so this slice does not invent those keywords.
    """
    _reject_unsupported_widget(bound)
    field = bound.field
    if isinstance(field, forms.MultipleChoiceField):
        raise DeclarativeUnsupportedField(
            bound.name,
            "multiple-value choice fields are not in this experimental slice",
        )
    if isinstance(field, forms.ChoiceField):
        return _choice_schema(bound)
    if isinstance(field, forms.BooleanField):
        # A required BooleanField rejects False. ``const: true`` is the
        # checked state Django actually accepts.
        if field.required:
            return {"type": "boolean", "const": True}
        return {"type": "boolean"}
    if isinstance(field, forms.IntegerField):
        return {"type": "integer"}
    if isinstance(field, (forms.FloatField, forms.DecimalField)):
        return {"type": "number"}
    if isinstance(field, forms.CharField):
        return {"type": "string"}
    if isinstance(field, (forms.DateField, forms.TimeField, forms.DateTimeField)):
        return {"type": "string"}
    raise DeclarativeUnsupportedField(
        bound.name,
        f"field type {type(field).__name__} is not in this experimental slice",
    )


def _property_schema(
    bound: forms.BoundField,
    param_descriptions: Mapping[str, object] | None,
) -> dict[str, Any]:
    schema = _value_schema(bound)
    explicit = _explicit_description(bound, param_descriptions)
    description = explicit or _label_text(bound)
    if description:
        schema["description"] = description
    return schema


def _input_schema(
    form: BaseForm,
    param_descriptions: Mapping[str, object] | None,
) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for bound in form:
        # Hidden and disabled controls are not successful form fields.
        # A disabled FileField must not raise; it is display-only.
        if bound.is_hidden or bound.field.disabled:
            continue
        properties[bound.html_name] = _property_schema(bound, param_descriptions)
        if bound.field.required:
            required.append(bound.html_name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def experimental_register_tool_descriptor(
    form: BaseForm,
    *,
    tool_name: str,
    tool_description: str,
    output_schema: Mapping[str, Any] | None = None,
    param_descriptions: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Build a ``document.modelContext.registerTool`` tool object.

    The returned mapping has ``api`` and ``tool``. ``tool`` contains
    ``name``, ``description`` and ``inputSchema``. ``outputSchema`` is
    present only when ``output_schema`` is a JSON object supplied by the
    caller. The helper does not add ``execute`` and does not register
    anything in a browser.
    """
    name, description = _require_tool_identity(tool_name, tool_description)
    copied_output: dict[str, Any] | None = None
    if output_schema is not None:
        copied_output = _json_object(output_schema, label="outputSchema")
    tool: dict[str, Any] = {
        "name": name,
        "description": description,
        "inputSchema": _input_schema(form, param_descriptions),
    }
    if copied_output is not None:
        tool["outputSchema"] = copied_output
    return {"api": REGISTER_TOOL_API, "tool": tool}


def _control_attrs(description: str | None) -> dict[str, str]:
    if not description:
        return {}
    return {CONTROL_PARAM_DESCRIPTION_ATTR: description}


def _render_bound(
    bound: forms.BoundField,
    param_descriptions: Mapping[str, object] | None,
) -> SafeString:
    explicit = _explicit_description(bound, param_descriptions)
    errors = format_html("{}", bound.errors) if bound.errors else mark_safe("")
    help_html = mark_safe("")
    if bound.help_text:
        help_html = format_html('<div class="helptext">{}</div>', _plain_text(bound.help_text))
    label_text = _label_text(bound)
    if isinstance(bound.field.widget, forms.RadioSelect):
        description = explicit or label_text
        control = bound.as_widget(attrs=_control_attrs(description))
        legend = bound.legend_tag(contents=label_text) if label_text else mark_safe("")
        return format_html("<fieldset>{}{}{}{}</fieldset>", legend, help_html, errors, control)
    control = bound.as_widget(attrs=_control_attrs(explicit))
    label = bound.label_tag(contents=label_text) if label_text else mark_safe("")
    return format_html("<div>{}{}{}{}</div>", label, help_html, errors, control)


def _top_errors(form: BaseForm) -> ErrorList:
    """Non-field errors plus hidden-field errors, as Django's form renderer does."""
    top_errors = form.non_field_errors().copy()
    for bound in form.hidden_fields():
        if not bound.errors:
            continue
        top_errors.extend(
            [
                _("(Hidden field %(name)s) %(error)s") % {"name": bound.name, "error": str(error)}
                for error in bound.errors
            ]
        )
    return top_errors


def _csrf_markup(csrf_token: object) -> SafeString:
    if csrf_token is None or isinstance(csrf_token, bool):
        return mark_safe("")
    text = str(csrf_token).strip()
    if not text or text == "NOTPROVIDED":
        return mark_safe("")
    return format_html(
        '<input type="hidden" name="csrfmiddlewaretoken" value="{}">',
        text,
    )


def render_experimental_declarative_form(
    form: BaseForm,
    *,
    tool_name: str,
    tool_description: str,
    autosubmit: bool = False,
    method: str = "post",
    action: str = "",
    submit_label: str = "Submit",
    param_descriptions: Mapping[str, object] | None = None,
    csrf_token: object = None,
) -> SafeString:
    """Render ``form`` as a declarative WebMCP ``<form>``.

    ``help_text`` becomes ``toolparamdescription`` on text, select and
    checkbox controls. A radio group also receives that attribute on every
    radio (or the field label, when ``help_text`` is empty) and a
    ``<fieldset>`` with a ``<legend>``. ``autosubmit=True`` emits the boolean
    ``toolautosubmit`` attribute. Disabled fields are omitted. The CSRF input
    is rendered only when ``method`` is ``post``.
    """
    name, description = _require_tool_identity(tool_name, tool_description)
    if not isinstance(method, str) or not _METHOD.fullmatch(method):
        raise DeclarativeFormError("method must be 'get' or 'post'")
    # Build the schema first so an unsupported field fails before any HTML
    # is returned, and so the preview and the markup describe the same form.
    _input_schema(form, param_descriptions)
    autosubmit_attr = mark_safe(" toolautosubmit") if autosubmit else mark_safe("")
    parts: list[SafeString] = [
        format_html(
            '<form method="{}" action="{}" {}="{}" {}="{}" '
            'data-insight-ui-webmcp="declarative-form"{}>',
            method.lower(),
            action,
            FORM_TOOL_NAME_ATTR,
            name,
            FORM_TOOL_DESCRIPTION_ATTR,
            description,
            autosubmit_attr,
        )
    ]
    top_errors = _top_errors(form)
    if top_errors:
        parts.append(format_html("{}", top_errors))
    if method.lower() == "post":
        parts.append(_csrf_markup(csrf_token))
    for bound in form.hidden_fields():
        if bound.field.disabled:
            continue
        parts.append(format_html("{}", bound.as_widget()))
    for bound in form.visible_fields():
        if bound.field.disabled:
            continue
        parts.append(_render_bound(bound, param_descriptions))
    parts.append(format_html('<button type="submit">{}</button></form>', submit_label))
    html = mark_safe("".join(parts))
    validate_declarative_markup(html)
    return html


class _MarkupParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag.lower(), {key.lower(): value for key, value in attrs}))


def validate_declarative_markup(html: str) -> None:
    """Raise if ``html`` does not match the current declarative attributes.

    A declarative form needs ``toolname`` and ``tooldescription``.
    ``toolautosubmit`` is a boolean attribute. ``toolparamdescription`` belongs
    on a named control. Any other ``tool*`` attribute, including a made-up
    output-schema attribute, is rejected.
    """
    parser = _MarkupParser()
    parser.feed(html)
    parser.close()
    issues: list[str] = []
    forms_seen = 0
    for tag, attrs in parser.elements:
        tool_attrs = {key for key in attrs if key.startswith("tool")}
        unknown = sorted(tool_attrs - _ALLOWED_TOOL_ATTRS)
        if unknown:
            issues.append(f"<{tag}> uses undeclared tool attribute(s): {', '.join(unknown)}")
        if "providecontext" in attrs:
            issues.append(f"<{tag}> uses provideContext; registerTool is the registration API")
        if tag == "form":
            forms_seen += 1
            name = attrs.get(FORM_TOOL_NAME_ATTR)
            description = attrs.get(FORM_TOOL_DESCRIPTION_ATTR)
            if name is None or description is None:
                issues.append("declarative <form> needs toolname and tooldescription")
            elif not _TOOL_NAME.fullmatch(name) or not description.strip():
                issues.append("declarative <form> has an empty or illegal toolname/tooldescription")
            if CONTROL_PARAM_DESCRIPTION_ATTR in attrs:
                issues.append("toolparamdescription belongs on a control, not on <form>")
            if FORM_TOOL_AUTOSUBMIT_ATTR in attrs:
                value = attrs[FORM_TOOL_AUTOSUBMIT_ATTR]
                if value not in (None, "", FORM_TOOL_AUTOSUBMIT_ATTR):
                    issues.append("toolautosubmit must be a boolean attribute")
        else:
            for form_attr in _FORM_TOOL_ATTRS:
                if form_attr in attrs:
                    issues.append(f"{form_attr} belongs on <form>, found on <{tag}>")
        if CONTROL_PARAM_DESCRIPTION_ATTR in attrs and tag != "form":
            description = attrs[CONTROL_PARAM_DESCRIPTION_ATTR]
            if description is None or not str(description).strip():
                issues.append(f"<{tag}> has an empty toolparamdescription")
            if not attrs.get("name"):
                issues.append(f"<{tag}> has toolparamdescription without a name")
    if forms_seen == 0:
        issues.append("markup has no declarative <form>")
    if issues:
        raise DeclarativeMarkupError(issues)
