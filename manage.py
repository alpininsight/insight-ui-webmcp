#!/usr/bin/env python
"""Thin Django management entry for package tests and local prepare commands."""

from __future__ import annotations

import os
import sys


def main() -> None:
    """Execute Django administrative commands against the test settings."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
