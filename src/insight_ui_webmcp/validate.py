"""Compatibility facade for the authoritative ais-webmcp validator."""

from ais_webmcp.validate import *  # noqa: F403

if __name__ == "__main__":
    import sys

    from ais_webmcp.cli import main

    raise SystemExit(main(["validate", *sys.argv[1:]]))
