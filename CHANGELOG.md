# 0.2.0 (2026-11-13)

- README: the Core browser runtime is published on npm as
  `@alpininsightsolutions/webmcp`; the "not yet published" wording is
  removed. The adapter keeps using the Core installed from PyPI and supports
  the Core 0.1.x and 0.2.x series (`ais-webmcp>=0.1.0,<0.3`). The
  `validateOutput` additions are in PyPI Core `ais-webmcp` 0.2.1 and in the
  npm runtime from 0.2.0 on.
- Declarative form review: a required checkbox schema is `const: true`;
  disabled fields, including a disabled file field, are omitted; unknown
  `tool*` attributes are matched by prefix; the CSRF input is POST-only;
  non-finite `outputSchema` numbers raise `TypeError`; label and help text
  decode HTML entities once; hidden-field errors are shown with the form
  errors.
- Package metadata links the public documentation site. The package declares
  Django 6 and Apache-2.0 with LICENSE and NOTICE. The adapter re-exports Core
  APIs and does not declare a typed Python API.
- Experimental declarative forms:
  `{% webmcp_experimental_declarative_form %}` and
  `render_experimental_declarative_form` emit the current WebMCP form
  attributes (`toolname`, `tooldescription`, `toolautosubmit`,
  `toolparamdescription`). `experimental_register_tool_descriptor` builds a
  `document.modelContext.registerTool` tool object. `outputSchema` is
  included only when the caller supplies one. See `docs/declarative-api.md`.
  Radio groups follow the markup described in webmachinelearning/webmcp#362;
  that browser bug is not polyfilled.

- Install the verified public `ais-webmcp` release with the stable compatibility
  range `>=0.1.0,<0.3`; replace the temporary Git source and lock with PyPI
  Core `0.1.0`. Update corpus provenance to its release source and test real
  index installs before wheel/sdist adapter installs. Contributor checks resolve
  the public Core package from PyPI.
- Pin integrated ais-webmcp `ae44b8b37a6f6997d856731bfc8b896bfe63c0de`
  (ais-webmcp #14). Core validates a declared `outputSchema` and forwards it
  from `registerFromManifest` and `registerTool` into
  `document.modelContext.registerTool`. `{% webmcp_assets %}` serves the
  installed Core `register.js` byte-for-byte. This adapter does not monkey-patch
  Core validators or load an `output-schema.js` bridge.
- Declare `outputSchema` on the read-only `webpage` tools (`list_sections`,
  `get_section`, `get_company_pitch`, `list_products`, `get_contact`) so an
  agent can see the return shape. Each schema names only values that tool
  already returns. `subscribe_newsletter` stays `enabled: false` and is
  unchanged. Hosts such as insight-ui-docs set `outputSchema` on their own
  tool objects; `webmcp_prepare` does not invent schemas for a custom profile.
- README: packages at a glance. One `register.js` from the
  [ais-webmcp core](https://github.com/alpininsight/ais-webmcp), delivered as
  `insight-ui-webmcp` (this Django adapter, using the installed core),
  `@alpininsightsolutions/webmcp` (npm) and the CDN. Core distribution channels
  have independent release evidence. The unscoped npm package `webmcp` is unrelated.
- Relicense both packages from MPL-2.0 to Apache-2.0 with an Alpin Insight
  Attribution NOTICE (decision 2026-10-09): root and per-package `LICENSE` and
  `NOTICE`, PEP 639 `License-Expression: Apache-2.0` with `License-File` LICENSE
  and NOTICE in wheel and sdist. NOTICE lists the bundled Ajv and
  fast-deep-equal (MIT). Nothing is published.
- Add `{% webmcp_attribution %}` (#57, decision 2026-10-09): a small, accessible
  notice "Insight UI WebMCP · Apache-2.0 · © Alpin Insight Solutions GmbH & Co. KG"
  linking to alpininsight.ai, which the host places (e.g. footer). It renders only
  when `WEBMCP_ENABLED` is true, is on by default, and is turned off with
  `WEBMCP_ATTRIBUTION = False` or `show=False` on the tag. It is plain `<small>`
  markup with no JS or inline style. `webmcp_assets`, manifests and tool output
  are unchanged.
- Add read-only `list_products` to the `webpage` profile (webpage#71): published
  product cards with name, title, status (e.g. Private Beta) and short
  description; no input, `readOnlyHint: true`, at most `MAX_PRODUCTS` (12)
  entries, no side effects. Hosts supply the handler from their own content;
  `subscribe_newsletter` stays `enabled: false`. Fixtures updated.
- Split the Django extension and framework-independent `ais-webmcp` client into
  two normally installable packages with one schema and browser helper.
- Enforce enable/annotation/schema parity, stable errors and clobber protection.
- Add local doctor/status, diff/export and explicit host-profile adapters.
- Clarify the two products with website-focused package and repository copy.
- Add `ToolSpec(untrusted_content=True)` so Python host profiles can emit
  `annotations.untrustedContentHint` (Chrome 149+). Only when set; the
  `webpage` profile ships first-party content and stays unmarked.
- Add read-only `InsightUiWebmcp.status()` to tell `ok`, `no-origin-trial-meta`
  and `no-model-context` apart in the page without exposing the token (#6).
- Add `InsightUiWebmcp.onToolActivated` / `onToolCancel` for `toolactivated` /
  `toolcancel` on `document.modelContext` only (Chrome 156+ / PR #245); no-op
  without the API; never on `window` (#7).
- Document `executeTool(registeredTool, inputObject)` (Chrome 155+) for host
  smokes: the `RegisteredTool` from `getTools()`, never a name or JSON string;
  `RegisteredTool.inputSchema` as an object; contract table and DocLock (#5, #8).
- Document Cloudflare Edge WebMCP (dashboard bridge `/.webmcp/bridge.js` with
  C2PA and Site MCP Server packs) as an optional complement on proxied zones:
  origin registration and `WEBMCP_ORIGIN_TRIAL_TOKEN` stay in the host; DocLock.
- Clarify the newcomer guide for beginners: reading order, short glossary,
  AIS-first package choice aligned with the root README, thinner first-steps
  with links into `docs/reference/` (hosts, Cloudflare edge, delivery).
- Restructure docs into `docs/guide/` (newcomers: overview, package choice,
  first steps, agents vs Cloudflare edge) and `docs/reference/` (hosts,
  delivery/CDN, Cloudflare edge, ADR, EPP changelog, archive, proof,
  lessons-learned). Update root README, DocLock paths and CF complement
  assertions.

# Changelog

All notable changes to this project will be documented in this file.

## [unreleased]

### 🚀 Features

- *(cli)* Optional `tool.group` molecule field and `doctor --tree` Atomic Design listing (#20)

- *(annotations)* Allow `annotations.debugging` only via explicit host opt-in or `webmcp_prepare --debug-annotations` for tools marked debugging; never from Django `DEBUG` / `JS_DEBUG` (#9)

- *(monorepo)* Two publishable distributions: Django `insight-ui-webmcp` (`packages/insight-ui-webmcp`, import `insight_ui_webmcp`, keeps `register.js`) and Dev/CI `ais-webmcp` (`packages/ais-webmcp`, console script `ais-webmcp`, shared module `webmcp_manifest`). The root project is a uv workspace and is not published. Newsletter stays default-off. Does not close #20
- *(names)* Dev/CI console script is `ais-webmcp` (not `webmcp` / `webmcp-cli`). Django PyPI name stays `insight-ui-webmcp`. A second `ais-webmcp` distribution is documented, not split yet. Committed client commands, phased not optional: `list` (not P0), `doctor`/`status` (P1), `init` (P2), `diff` and `export` (after init)
- *(validate)* Shared WebMCP manifest JSON Schema plus Django-free `ais-webmcp validate` and `manage.py webmcp_validate` (#20 P0). Consequential tools need an explicit `enabled` flag; `subscribe_newsletter` stays enabled false
- *(scaffold)* Phase 1 MVP: WebMCP Django package, webpage profile, prepare/status commands, and browser JS helper

### ✅ Tests

- Executable JS contract tests for `registerTool` / AbortSignal / annotations, including promise rejection, sync throw, abort before and during work, replacement race, and default-off newsletter registration (#5)
- Django command tests (`webmcp_prepare` dry-run, rewrite, `webmcp_status`) and a real `ROOT_URLCONF` module (#5)
- Wheel and sdist are installed outside the checkout; `register.js` and the `webmcp_assets` template tag must be present (#5)

### 🧰 CI

- `validate` job installs the package without Django and runs `ais-webmcp validate` on committed fixtures (#20 P0)
- Historical contributor checks covered lint, tests, manifest validation and distribution installation (#5, #20 P0)

### 🐛 Bug Fixes

- *(register.js)* `wrapExecute` settles failure vs success explicitly, so `Promise.reject()` / `reject(null)` / falsy throws reject instead of resolving as success (review P2 on #30)
- *(register.js)* In-flight `execute` rejects with `AbortError` when its signal aborts and drops a later handler success. A JSON string is parsed only as a fallback and warned once, without logging the value (#8)

- *(register.js)* Spec-compliant `document.modelContext.registerTool`: await Promise, `name`/`title` mapping, `annotations.*Hint` (no top-level `consequential`), require execute + non-empty description (#2)
- *(register.js)* Unregister via `registerTool(tool, { signal })` + AbortController; public `unregister`/`dispose`; document that abort does not cancel in-flight execute (#11)
- *(register.js)* Synchronous `document.modelContext.registerTool` throws are reported as `{ ok: false }` instead of escaping the helper (#5)
