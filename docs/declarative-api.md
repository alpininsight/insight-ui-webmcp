# Declarative WebMCP forms (experimental)

The normative WebMCP draft ([specification](https://webmachinelearning.github.io/webmcp/))
registers tools with `document.modelContext.registerTool`. A second, declarative
path is still an explainer:
[declarative-api-explainer.md](https://github.com/webmachinelearning/webmcp/blob/main/declarative-api-explainer.md).
Chrome documents the same attributes for its origin trial
([Declarative API](https://developer.chrome.com/docs/ai/webmcp/declarative-api)).
Input-schema synthesis in the explainer is explicitly unfinished, and how a
declarative tool appears in `getTools()` / `executeTool()` is still open.

This package therefore does not ship a full declarative client. It emits the
attributes the explainer names today, checks that markup, and can build the
`registerTool` object a host script would pass alongside its own `execute`.

## Attributes we emit

| Markup | Proposal role |
|---|---|
| `<form toolname="…">` | `registerTool` `name` |
| `<form tooldescription="…">` | `registerTool` `description` |
| `<form toolautosubmit>` | Boolean. Present only when the host asks for agent submit. |
| `toolparamdescription` on a named control | JSON Schema `description` of that property |

`toolname` uses the `registerTool` name grammar: 1–128 characters from ASCII
letters, digits, `_`, `-` and `.`. The explainer's informal example
`toolname="Search flights"` contains a space; `registerTool` rejects that
name, and this helper rejects it too.

There is no `outputSchema` attribute in the explainer. Imperative
`outputSchema` is part of the draft specification
([webmcp#254](https://github.com/webmachinelearning/webmcp/pull/254)). The
declarative explainer still treats an output schema as an open question, so
this helper never invents `tooloutputschema` or writes `outputSchema` into
the form.

## Django entry points

```django
{% load webmcp_tags %}
{% webmcp_experimental_declarative_form form "search-cars" "Perform a car make/model search" %}
{% webmcp_experimental_declarative_form form "search-cars" "Perform a car make/model search" autosubmit=True %}
```

`render_experimental_declarative_form` is the same renderer. Field
`help_text` becomes `toolparamdescription` on text, checkbox and select
controls. A radio group is a `<fieldset>` with a `<legend>` and the same
`toolparamdescription` on every radio. When the radio field has no
`help_text`, the attribute is the field label. Pass `param_descriptions` to
override `help_text` by field name. HTML in a label or `help_text` is reduced
to plain text, and entities such as `&amp;` are decoded once before that text
is escaped again for the attribute. Hidden inputs are rendered for the
browser and are not given a parameter description. `csrfmiddlewaretoken` is
included only when the form method is `post`, so a GET form does not put the
token in the query string. Errors on hidden fields are listed with the form
errors, in Django's `(Hidden field …)` form. Fields with `disabled=True` are
left out of the markup and the schema, including a disabled file field.

`experimental_register_tool_descriptor` returns:

```python
{"api": "document.modelContext.registerTool", "tool": {...}}
```

`tool` has `name`, `description` and `inputSchema`. Pass `output_schema` as
a JSON object when the handler's result shape is known; that object is
copied onto `tool["outputSchema"]`. Omit the argument and the key is absent.
An empty object is kept, because the caller supplied it. A string, list or
other non-object raises `TypeError`. The helper does not add `execute` and
does not call into a browser.

`inputSchema` is a preview of the Django fields, not the browser's
synthesis algorithm:

- Visible `CharField` (including email and URL), date and time fields are
  strings. `IntegerField` is `integer`. Float and decimal fields are
  `number`. An optional `BooleanField` is `boolean`. A required checkbox is
  `{"type": "boolean", "const": true}` because Django rejects `false`.
- Fields with `disabled=True` are omitted. A disabled `FileField` does not
  raise.
- A single-value `ChoiceField` is a string with `enum` and `anyOf`
  (`const` plus `title`), matching the shape in Chrome's select example.
  Blank placeholder options are left out of `enum`.
- Property names are the HTML field names, including a form prefix.
- `description` is `help_text` or `param_descriptions` when set, otherwise
  the field label. That follows Chrome's label fallback for controls that
  have no `toolparamdescription`.
- `min`, `max`, `step` and `max_length` are not copied to `minimum`,
  `maximum` or `maxLength`. The explainer has not finished that reduction.
- File fields, multi-value choices, grouped choices and multi-widgets raise
  `DeclarativeUnsupportedField` instead of a guessed schema.

## Radio groups and webmcp#362

[webmachinelearning/webmcp#362](https://github.com/webmachinelearning/webmcp/issues/362)
reports that Chromium builds a radio group's choices (`enum` / `anyOf`) and
then drops the property `description`. `toolparamdescription` on the radios,
the `<legend>`, and `aria-description` do not currently show up in
`getTools()`. The explainer still says `toolparamdescription` is the
property description, and the issue asks browsers to use the first
`toolparamdescription` in the group or the legend.

The helper emits both, so the markup matches that expected shape. It does
not polyfill `getTools()`. Until #362 is fixed, an agent reading Chromium's
synthesized schema may still see the choices without the description. The
Python descriptor includes the description; that object is the
`registerTool` preview, not a claim about current Chromium output.

## What this slice does not do

- It does not load a script, call `registerTool`, or call `provideContext`.
  `provideContext` is the older entry point that replaces the whole tool
  list. Hosts that need an imperative tool add their own `execute` and call
  `document.modelContext.registerTool`.
- It does not implement `SubmitEvent.respondWith`, `agentInvoked`, or the
  `:tool-form-active` / `:tool-submit-active` pseudo-classes. Those stay in
  the host page.
- It does not try to compile `step`, `min` and `max` into JSON Schema.
