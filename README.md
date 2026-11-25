# Insight UI WebMCP

**Let AI assistants use the features you choose on your Django website.**

Expose tools that let an assistant list products, find the right page section,
or call actions you enable. Your Django app stays in control of permissions and
execution. Insight UI WebMCP is part of **Alpin Insight Solutions WebMCP**.

**Deutsch** · Stellen Sie ausgewählte Inhalte und Funktionen Ihrer Django-Website
für KI-Assistenten bereit. Ihre Anwendung legt fest, welche Aktionen erlaubt sind.

[Django guide](https://insight-ui-webmcp.alpininsight.ai/docs/insight-ui-webmcp/)
· [PyPI](https://pypi.org/project/insight-ui-webmcp/)
· [Product website](https://insight-ui-webmcp.alpininsight.ai/)

WebMCP is in preview. Browser use requires support for
`document.modelContext` and may require browser activation.
[WebMCP draft specification](https://webmachinelearning.github.io/webmcp/)

## Quickstart

1. Install the package in your Django project.

   ```bash
   uv add insight-ui-webmcp
   ```

2. Add `insight_ui_webmcp` to your existing `INSTALLED_APPS`. The adapter works
   with Django and offers an optional Insight UI integration.

3. Preview, create and validate a starter manifest from your Django project
   directory.

   ```bash
   uv run python manage.py webmcp_prepare --profile webpage --dry-run
   uv run python manage.py webmcp_prepare --profile webpage
   uv run python manage.py webmcp_validate webmcp.manifest.json
   ```

The manifest describes the tools your site can expose. For browser use, configure
Django staticfiles, load the runtime in your base template, and connect the
tools to your application handlers. Start with a read-only tool and keep actions
that change data disabled until you have tested permissions and execution.
[Templates, static files and handlers](https://insight-ui-webmcp.alpininsight.ai/docs/insight-ui-webmcp/templates/)

## Choose your package

| Package | Use it for |
| --- | --- |
| [`insight-ui-webmcp` on PyPI](https://pypi.org/project/insight-ui-webmcp/) | Django integration with management commands, host profiles and template tags. |
| [`ais-webmcp` on PyPI](https://pypi.org/project/ais-webmcp/) | Creating, validating and managing manifests with a framework-independent Python CLI. Contains the shared schema and browser runtime. |
| [`@alpininsightsolutions/webmcp` on npm](https://www.npmjs.com/package/@alpininsightsolutions/webmcp) | Integrating the shared browser runtime and TypeScript types into a JavaScript build. |

The Django adapter serves the runtime from the installed Core package.
The Core runtime is also available as a versioned CDN asset.

## Requirements and documentation

- Python 3.12 or later and Django 6.0.4 or later in the Django 6 series.
- The optional `insight-ui-webmcp[ui]` extra includes
  [Insight UI](https://github.com/alpininsight/insight-ui) under its own AGPL-3.0
  license. CI checks the adapter with Insight UI 1.15.1 and 2.0.0rc1.

| Guide | What it covers |
| --- | --- |
| [WebMCP guide](https://insight-ui-webmcp.alpininsight.ai/docs/guide/) | First steps and how the three packages fit together. |
| [Django documentation](https://insight-ui-webmcp.alpininsight.ai/docs/insight-ui-webmcp/) | Installation, settings, commands, static assets, host profiles and troubleshooting. |
| [Core profiles and tool schemas](https://insight-ui-webmcp.alpininsight.ai/docs/ais-webmcp/profiles/) | How manifests describe tools, inputs and outputs. |
| [Experimental declarative forms](https://github.com/alpininsight/insight-ui-webmcp/blob/develop/docs/declarative-api.md) | Django helpers for the experimental WebMCP form attributes. |
| [Agents and edge integration](https://insight-ui-webmcp.alpininsight.ai/docs/guide/agents-and-edge/) | Optional Cloudflare edge discovery. Browser tool registration stays at the origin. |

## Contributing and license

Contributions are welcome through
[GitHub issues](https://github.com/alpininsight/insight-ui-webmcp/issues) and
[pull requests](https://github.com/alpininsight/insight-ui-webmcp/pulls).
See the [contributor checks](https://github.com/alpininsight/insight-ui-webmcp/blob/develop/docs/ci-and-release.md)
for the test workflow and the
[security policy](https://github.com/alpininsight/.github/blob/main/SECURITY.md)
for vulnerability reports.

The adapter is distributed under
[Apache-2.0](https://github.com/alpininsight/insight-ui-webmcp/blob/develop/LICENSE)
with a [NOTICE](https://github.com/alpininsight/insight-ui-webmcp/blob/develop/NOTICE).
Hosts can display the optional on-page notice **Insight UI WebMCP · Apache-2.0 ·
© Alpin Insight Solutions GmbH & Co. KG**. See
[Templates and static files](https://insight-ui-webmcp.alpininsight.ai/docs/insight-ui-webmcp/templates/).
