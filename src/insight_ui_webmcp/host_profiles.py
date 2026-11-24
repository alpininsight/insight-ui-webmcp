"""Explicit Django host adapters; no host imports in the shared client."""

from ais_webmcp.profiles import get_profile as builtin_profile
from ais_webmcp.profiles import list_profiles as builtin_names
from django.conf import settings
from django.utils.module_loading import import_string


def profiles():
    result = {name: builtin_profile(name) for name in builtin_names()}
    for path in getattr(settings, "WEBMCP_PROFILES", ()):
        profile = import_string(path)()
        if profile.name in result:
            raise ValueError(f"Duplicate WebMCP profile: {profile.name}")
        result[profile.name] = profile
    return result


def get_profile(name):
    known = profiles()
    if name not in known:
        raise KeyError(f"Unknown WebMCP profile {name!r}. Known: {', '.join(known)}")
    return known[name]


def list_profiles():
    return tuple(sorted(profiles()))
