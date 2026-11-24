# Documentation

Use the [public documentation](https://insight-ui-webmcp.alpininsight.ai/),
including the [newcomer guide](https://insight-ui-webmcp.alpininsight.ai/docs/guide/)
and [reference](https://insight-ui-webmcp.alpininsight.ai/docs/reference/).

This repository contains the Django adapter, its [README](../README.md),
[CHANGELOG](../CHANGELOG.md), [LICENSE](../LICENSE), [NOTICE](../NOTICE), and
[contributor checks](ci-and-release.md). The experimental declarative form helper
is described in [declarative-api.md](declarative-api.md).

WebMCP tools use the page's session. Hosts decide which tools to expose and must
apply their normal authentication, authorization and CSRF protections. Keep
consequential tools disabled until the host explicitly enables them.
