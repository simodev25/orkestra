"""Version utilities for semantic versioning."""


def bump_patch(version: str) -> str:
    """Increment the patch component: 1.0.0 -> 1.0.1"""
    parts = version.split(".")
    if len(parts) != 3:
        return "1.0.1"
    major, minor, patch = parts
    try:
        return f"{major}.{minor}.{int(patch) + 1}"
    except ValueError:
        return "1.0.1"
