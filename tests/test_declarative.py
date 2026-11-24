"""Experimental declarative WebMCP form markup."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path

import pytest
from django import forms
from django.template import Context, Template

from insight_ui_webmcp.declarative import (
    CONTROL_PARAM_DESCRIPTION_ATTR,
    FORM_TOOL_AUTOSUBMIT_ATTR,
    FORM_TOOL_DESCRIPTION_ATTR,
    FORM_TOOL_NAME_ATTR,
    REGISTER_TOOL_API,
    DeclarativeFormError,
    DeclarativeMarkupError,
    DeclarativeUnsupportedField,
    experimental_register_tool_descriptor,
    render_experimental_declarative_form,
    validate_declarative_markup,
)

pytestmark = pytest.mark.django_db(databases=[])


class SearchForm(forms.Form):
    make = forms.CharField(
        label="Make",
        help_text="The vehicle's make (e.g., BMW, Ford)",
        max_length=40,
    )
    model = forms.CharField(label="Model", required=False)
    year = forms.IntegerField(label="Year", required=False, min_value=1900, max_value=2100)
    remember = forms.BooleanField(label="Remember", required=False)
    shift = forms.ChoiceField(
        label="Shift",
        choices=[("", "---------"), ("day", "Day"), ("night", "Night")],
        widget=forms.RadioSelect,
        help_text="Which shift they work.",
    )
    team = forms.ChoiceField(
        label="Team",
        required=False,
        choices=[("", "---------"), ("support", "Website support")],
    )
    token = forms.CharField(widget=forms.HiddenInput, required=False)


def _elements(html: str) -> list[tuple[str, dict[str, str | None]]]:
    class Collector(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.found: list[tuple[str, dict[str, str | None]]] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            self.found.append((tag.lower(), {key.lower(): value for key, value in attrs}))

    parser = Collector()
    parser.feed(html)
    parser.close()
    return parser.found


def _render(**kwargs: object) -> str:
    defaults: dict[str, object] = {
        "tool_name": "search-cars",
        "tool_description": "Perform a car make/model search",
    }
    defaults.update(kwargs)
    return str(render_experimental_declarative_form(SearchForm(), **defaults))  # type: ignore[arg-type]


def test_proposal_attribute_names_match_the_explainer() -> None:
    assert FORM_TOOL_NAME_ATTR == "toolname"
    assert FORM_TOOL_DESCRIPTION_ATTR == "tooldescription"
    assert FORM_TOOL_AUTOSUBMIT_ATTR == "toolautosubmit"
    assert CONTROL_PARAM_DESCRIPTION_ATTR == "toolparamdescription"
    assert REGISTER_TOOL_API == "document.modelContext.registerTool"


def test_rendered_form_matches_declarative_attributes() -> None:
    html = _render()
    validate_declarative_markup(html)
    elements = _elements(html)
    forms_seen = [attrs for tag, attrs in elements if tag == "form"]
    assert len(forms_seen) == 1
    form = forms_seen[0]
    assert form["toolname"] == "search-cars"
    assert form["tooldescription"] == "Perform a car make/model search"
    assert "toolautosubmit" not in form
    assert form["data-insight-ui-webmcp"] == "declarative-form"
    assert "tooloutputschema" not in form
    assert "providecontext" not in form

    by_name = {
        attrs.get("name"): attrs
        for tag, attrs in elements
        if tag == "input" and attrs.get("type") != "hidden"
    }
    assert by_name["make"]["toolparamdescription"] == "The vehicle's make (e.g., BMW, Ford)"
    assert "toolparamdescription" not in by_name["model"]
    assert "maxlength" in by_name["make"] or by_name["make"].get("maxlength") == "40"
    radios = [
        attrs
        for tag, attrs in elements
        if tag == "input" and attrs.get("type") == "radio" and attrs.get("name") == "shift"
    ]
    assert [attrs.get("value") for attrs in radios] == ["", "day", "night"]
    assert {attrs.get("toolparamdescription") for attrs in radios} == {"Which shift they work."}
    assert any(tag == "fieldset" for tag, _attrs in elements)
    assert "<legend>" in html and "Shift" in html
    selects = [attrs for tag, attrs in elements if tag == "select"]
    assert len(selects) == 1
    assert selects[0]["name"] == "team"
    assert "toolparamdescription" not in selects[0]
    assert any(tag == "button" and attrs.get("type") == "submit" for tag, attrs in elements)
    assert "outputSchema" not in html
    assert "provideContext" not in html
    assert "<script" not in html


def test_autosubmit_is_a_boolean_attribute() -> None:
    html = _render(autosubmit=True, method="GET", action="/search")
    form = next(attrs for tag, attrs in _elements(html) if tag == "form")
    assert form["method"] == "get"
    assert form["action"] == "/search"
    assert "toolautosubmit" in form
    assert form["toolautosubmit"] in (None, "", "toolautosubmit")


def test_help_text_html_is_plain_text_in_the_attribute() -> None:
    class Form(forms.Form):
        make = forms.CharField(label="Make", help_text="<b>BMW & Ford</b>")

    html = str(
        render_experimental_declarative_form(
            Form(),
            tool_name="search-cars",
            tool_description='Tom & "Jerry"',
        )
    )
    assert "<b>" not in html
    assert "BMW &amp; Ford" in html
    assert "Tom &amp; &quot;Jerry&quot;" in html
    form = next(attrs for tag, attrs in _elements(html) if tag == "form")
    assert form["tooldescription"] == 'Tom & "Jerry"'
    make = next(
        attrs for tag, attrs in _elements(html) if tag == "input" and attrs.get("name") == "make"
    )
    assert make["toolparamdescription"] == "BMW & Ford"


def test_prefixed_field_names_are_the_tool_properties() -> None:
    form = SearchForm(prefix="search")
    html = str(
        render_experimental_declarative_form(
            form,
            tool_name="search-cars",
            tool_description="Perform a car make/model search",
        )
    )
    names = {attrs.get("name") for _tag, attrs in _elements(html) if attrs.get("name")}
    assert "search-make" in names
    descriptor = experimental_register_tool_descriptor(
        form,
        tool_name="search-cars",
        tool_description="Perform a car make/model search",
    )
    properties = descriptor["tool"]["inputSchema"]["properties"]
    assert "make" not in properties
    assert "search-make" in properties
    assert "search-token" not in properties


def test_register_tool_descriptor_omits_missing_output_schema() -> None:
    before = dict(SearchForm.base_fields["make"].widget.attrs)
    supplied = {"type": "string", "description": "Matching cars."}
    descriptor = experimental_register_tool_descriptor(
        SearchForm(),
        tool_name="search-cars",
        tool_description="Perform a car make/model search",
        output_schema=supplied,
    )
    supplied["type"] = "array"
    tool = descriptor["tool"]
    assert descriptor["api"] == "document.modelContext.registerTool"
    assert "provideContext" not in json.dumps(descriptor)
    assert "execute" not in tool
    assert tool["outputSchema"] == {"type": "string", "description": "Matching cars."}
    assert tool["outputSchema"] is not tool["inputSchema"]
    schema = tool["inputSchema"]
    assert schema["type"] == "object"
    assert schema["required"] == ["make", "shift"]
    make = schema["properties"]["make"]
    assert make["type"] == "string"
    assert make["description"] == "The vehicle's make (e.g., BMW, Ford)"
    assert "maxLength" not in make
    year = schema["properties"]["year"]
    assert year == {"type": "integer", "description": "Year"}
    assert "minimum" not in year and "maximum" not in year
    assert schema["properties"]["model"]["description"] == "Model"
    shift = schema["properties"]["shift"]
    assert shift["description"] == "Which shift they work."
    assert shift["enum"] == ["day", "night"]
    assert shift["anyOf"] == [
        {"type": "string", "const": "day", "title": "Day"},
        {"type": "string", "const": "night", "title": "Night"},
    ]
    assert schema["properties"]["team"]["enum"] == ["support"]
    assert "token" not in schema["properties"]
    assert "remember" in schema["properties"]
    assert schema["properties"]["remember"]["type"] == "boolean"
    assert "const" not in schema["properties"]["remember"]
    assert SearchForm.base_fields["make"].widget.attrs == before


def test_missing_output_schema_is_absent_and_empty_object_is_kept() -> None:
    omitted = experimental_register_tool_descriptor(
        SearchForm(),
        tool_name="search-cars",
        tool_description="Perform a car make/model search",
    )
    assert "outputSchema" not in omitted["tool"]
    empty = experimental_register_tool_descriptor(
        SearchForm(),
        tool_name="search-cars",
        tool_description="Perform a car make/model search",
        output_schema={},
    )
    assert empty["tool"]["outputSchema"] == {}


@pytest.mark.parametrize("output_schema", ["string", ["string"], 1, True])
def test_output_schema_must_be_an_object(output_schema: object) -> None:
    with pytest.raises(TypeError):
        experimental_register_tool_descriptor(
            SearchForm(),
            tool_name="search-cars",
            tool_description="Perform a car make/model search",
            output_schema=output_schema,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("tool_name", "tool_description"),
    [("Search flights", "ok"), ("", "ok"), ("a" * 129, "ok"), ("ok", "   "), ("café", "ok")],
)
def test_tool_identity_follows_register_tool(tool_name: str, tool_description: str) -> None:
    with pytest.raises(DeclarativeFormError):
        render_experimental_declarative_form(
            SearchForm(),
            tool_name=tool_name,
            tool_description=tool_description,
        )


def test_unsupported_fields_fail_closed() -> None:
    class Form(forms.Form):
        upload = forms.FileField()

    with pytest.raises(DeclarativeUnsupportedField):
        experimental_register_tool_descriptor(
            Form(),
            tool_name="upload-file",
            tool_description="Upload a file",
        )

    class Grouped(forms.Form):
        team = forms.ChoiceField(choices=[("People", [("a", "A")])])

    with pytest.raises(DeclarativeUnsupportedField):
        render_experimental_declarative_form(
            Grouped(),
            tool_name="choose-team",
            tool_description="Choose a team",
        )

    class Colliding(forms.Form):
        team = forms.ChoiceField(choices=[(1, "One"), ("1", "Also one")])

    with pytest.raises(DeclarativeUnsupportedField):
        experimental_register_tool_descriptor(
            Colliding(),
            tool_name="choose-team",
            tool_description="Choose a team",
        )

    class Multi(forms.Form):
        tags = forms.MultipleChoiceField(choices=[("a", "A"), ("b", "B")])

    with pytest.raises(DeclarativeUnsupportedField):
        render_experimental_declarative_form(
            Multi(),
            tool_name="choose-tags",
            tool_description="Choose tags",
        )


def test_param_description_override_and_radio_label_fallback() -> None:
    class Form(forms.Form):
        shift = forms.ChoiceField(
            label="Shift",
            choices=[("day", "Day"), ("night", "Night")],
            widget=forms.RadioSelect,
        )

    html = str(
        render_experimental_declarative_form(
            Form(),
            tool_name="createProfile",
            tool_description="Creates a profile.",
            param_descriptions={"shift": "Which shift they work."},
        )
    )
    radios = [
        attrs for tag, attrs in _elements(html) if tag == "input" and attrs.get("type") == "radio"
    ]
    assert len(radios) == 2
    assert {attrs.get("toolparamdescription") for attrs in radios} == {"Which shift they work."}
    bare = experimental_register_tool_descriptor(
        Form(),
        tool_name="createProfile",
        tool_description="Creates a profile.",
    )
    assert bare["tool"]["inputSchema"]["properties"]["shift"]["description"] == "Shift"


def test_csrf_token_is_markup_only() -> None:
    html = str(
        render_experimental_declarative_form(
            SearchForm(),
            tool_name="search-cars",
            tool_description="Perform a car make/model search",
            csrf_token="abc123",
        )
    )
    hidden = [
        attrs for tag, attrs in _elements(html) if tag == "input" and attrs.get("type") == "hidden"
    ]
    names = {attrs.get("name") for attrs in hidden}
    assert "csrfmiddlewaretoken" in names
    assert "token" in names
    assert all("toolparamdescription" not in attrs for attrs in hidden)
    skipped = str(
        render_experimental_declarative_form(
            SearchForm(),
            tool_name="search-cars",
            tool_description="Perform a car make/model search",
            csrf_token="NOTPROVIDED",
        )
    )
    assert "csrfmiddlewaretoken" not in skipped


def test_template_tag_renders_the_same_attributes() -> None:
    html = Template(
        "{% load webmcp_tags %}"
        '{% webmcp_experimental_declarative_form form "search-cars" '
        '"Perform a car make/model search" autosubmit=True %}'
    ).render(Context({"form": SearchForm(), "csrf_token": "from-context"}))
    validate_declarative_markup(html)
    form = next(attrs for tag, attrs in _elements(html) if tag == "form")
    assert form["toolname"] == "search-cars"
    assert "toolautosubmit" in form
    assert 'name="csrfmiddlewaretoken"' in html
    assert 'value="from-context"' in html


def test_validator_rejects_markup_outside_the_proposal() -> None:
    validate_declarative_markup(
        '<form toolname="search-cars" tooldescription="Perform a search">'
        '<input name="make" toolparamdescription="The make">'
        "</form>"
    )
    samples = [
        '<form toolname="search-cars">',
        '<form toolname="search cars" tooldescription="Perform a search">',
        '<form toolname="search-cars" tooldescription="Perform a search" tooloutputschema="{}">',
        '<form toolname="search-cars" tooldescription="Perform a search" provideContext="1">',
        '<form toolname="search-cars" tooldescription="Perform a search" toolautosubmit="false">',
        '<form toolname="search-cars" tooldescription="Perform a search">'
        '<input toolparamdescription="The make"></form>',
        "<div>no form</div>",
    ]
    for sample in samples:
        with pytest.raises(DeclarativeMarkupError):
            validate_declarative_markup(sample)


def test_required_checkbox_schema_is_const_true() -> None:
    class Form(forms.Form):
        accept = forms.BooleanField(label="Accept")
        optional = forms.BooleanField(label="Optional", required=False)

    schema = experimental_register_tool_descriptor(
        Form(),
        tool_name="accept-terms",
        tool_description="Record consent",
    )["tool"]["inputSchema"]
    assert schema["required"] == ["accept"]
    assert schema["properties"]["accept"]["type"] == "boolean"
    assert schema["properties"]["accept"]["const"] is True
    assert "const" not in schema["properties"]["optional"]


def test_disabled_fields_are_omitted_including_file_fields() -> None:
    class Form(forms.Form):
        name = forms.CharField(label="Name")
        nickname = forms.CharField(label="Nickname", disabled=True, required=True)
        upload = forms.FileField(disabled=True)

    descriptor = experimental_register_tool_descriptor(
        Form(),
        tool_name="update-profile",
        tool_description="Update the public profile",
    )
    schema = descriptor["tool"]["inputSchema"]
    assert list(schema["properties"]) == ["name"]
    assert schema["required"] == ["name"]
    html = str(
        render_experimental_declarative_form(
            Form(),
            tool_name="update-profile",
            tool_description="Update the public profile",
        )
    )
    names = {attrs.get("name") for _tag, attrs in _elements(html)}
    assert "name" in names
    assert "nickname" not in names
    assert "upload" not in names


def test_data_tooltip_is_not_a_tool_attribute() -> None:
    class Form(forms.Form):
        make = forms.CharField(widget=forms.TextInput(attrs={"data-tooltip": "Vehicle make"}))

    html = str(
        render_experimental_declarative_form(
            Form(),
            tool_name="search-cars",
            tool_description="Perform a car make/model search",
        )
    )
    validate_declarative_markup(html)
    make = next(attrs for tag, attrs in _elements(html) if attrs.get("name") == "make")
    assert make["data-tooltip"] == "Vehicle make"
    validate_declarative_markup(
        '<form toolname="search-cars" tooldescription="Perform a search" data-tooltip="hint">'
        '<input name="make" data-tooltip="hint">'
        "</form>"
    )


def test_get_form_omits_csrf_token() -> None:
    html = str(
        render_experimental_declarative_form(
            SearchForm(),
            tool_name="search-cars",
            tool_description="Perform a car make/model search",
            method="get",
            csrf_token="abc123",
        )
    )
    assert "csrfmiddlewaretoken" not in html
    posted = Template(
        "{% load webmcp_tags %}"
        '{% webmcp_experimental_declarative_form form "search-cars" '
        '"Perform a car make/model search" method="post" %}'
    ).render(Context({"form": SearchForm(), "csrf_token": "from-context"}))
    assert 'name="csrfmiddlewaretoken"' in posted
    gotten = Template(
        "{% load webmcp_tags %}"
        '{% webmcp_experimental_declarative_form form "search-cars" '
        '"Perform a car make/model search" method="get" %}'
    ).render(Context({"form": SearchForm(), "csrf_token": "from-context"}))
    assert "csrfmiddlewaretoken" not in gotten


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_output_schema_rejects_non_finite_numbers(value: float) -> None:
    with pytest.raises(TypeError):
        experimental_register_tool_descriptor(
            SearchForm(),
            tool_name="search-cars",
            tool_description="Perform a car make/model search",
            output_schema={"properties": {"n": {"const": value}}},
        )


def test_html_entities_are_decoded_once_in_descriptions() -> None:
    class Form(forms.Form):
        make = forms.CharField(label="A &amp; B", help_text="<b>BMW &amp; Ford</b>")

    html = str(
        render_experimental_declarative_form(
            Form(),
            tool_name="search-cars",
            tool_description="Perform a car make/model search",
        )
    )
    assert "&amp;amp;" not in html
    assert "<b>" not in html
    make = next(attrs for tag, attrs in _elements(html) if attrs.get("name") == "make")
    assert make["toolparamdescription"] == "BMW & Ford"
    schema = experimental_register_tool_descriptor(
        Form(),
        tool_name="search-cars",
        tool_description="Perform a car make/model search",
    )["tool"]["inputSchema"]
    assert schema["properties"]["make"]["description"] == "BMW & Ford"


def test_hidden_field_errors_are_visible() -> None:
    class Form(forms.Form):
        token = forms.CharField(widget=forms.HiddenInput)

    form = Form(data={"token": ""})
    assert not form.is_valid()
    html = str(
        render_experimental_declarative_form(
            form,
            tool_name="save-token",
            tool_description="Save the hidden token",
        )
    )
    assert "(Hidden field token)" in html
    assert "This field is required." in html
    hidden = next(
        attrs for tag, attrs in _elements(html) if tag == "input" and attrs.get("name") == "token"
    )
    assert hidden.get("type") == "hidden"


def test_docs_name_the_proposal_and_the_radio_gap() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    design = (root / "docs" / "declarative-api.md").read_text(encoding="utf-8")
    for text in (readme, design):
        assert "toolname" in text
        assert "tooldescription" in text
        assert "toolautosubmit" in text
        assert "toolparamdescription" in text
        assert "document.modelContext.registerTool" in text
        assert "outputSchema" in text
        assert "webmachinelearning/webmcp/issues/362" in text or "webmcp#362" in text
        assert "declarative-api-explainer.md" in text
