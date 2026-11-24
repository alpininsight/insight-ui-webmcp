"""Minimal URLconf so Django can resolve requests in package tests.

An empty list is not a valid ``ROOT_URLCONF`` (Django expects a module path).
"""

from __future__ import annotations

urlpatterns: list = []
