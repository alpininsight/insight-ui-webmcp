"""Django output/exit adapter for the shared local client."""

from contextlib import redirect_stdout
from io import StringIO

from ais_webmcp.cli import main
from django.core.management.base import CommandError


def run_client(arguments, stdout):
    buffer = StringIO()
    with redirect_stdout(buffer):
        code = main(arguments)
    stdout.write(buffer.getvalue(), ending="")
    if code:
        raise CommandError("WebMCP client returned a nonzero result", returncode=code)
