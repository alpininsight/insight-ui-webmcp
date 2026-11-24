"""Expose the installed Core runtime at the established Django static path."""

from fnmatch import fnmatch
from importlib.resources import files

from django.contrib.staticfiles.finders import BaseFinder
from django.core.files.storage import FileSystemStorage

STATIC_PATH = "insight_ui_webmcp/js/register.js"


class CoreRuntimeFinder(BaseFinder):
    """One canonical runtime; no package copy or settings mutation."""

    def __init__(self, *args, **kwargs):
        self.storage = FileSystemStorage(location=str(files("ais_webmcp").joinpath("assets")))
        self.storage.prefix = "insight_ui_webmcp/js"

    def find(self, path, find_all=False, **kwargs):
        path = path.replace("\\", "/")
        matches = []
        if path == STATIC_PATH and self.storage.exists("register.js"):
            matches.append(self.storage.path("register.js"))
        return matches if find_all else (matches[0] if matches else [])

    def list(self, ignore_patterns):
        if self.storage.exists("register.js") and not any(
            fnmatch("register.js", pattern) or fnmatch(STATIC_PATH, pattern)
            for pattern in (ignore_patterns or ())
        ):
            yield "register.js", self.storage
