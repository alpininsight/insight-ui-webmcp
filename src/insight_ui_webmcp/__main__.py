"""``python -m insight_ui_webmcp`` entry. Does not import Django."""

from __future__ import annotations

from insight_ui_webmcp.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
