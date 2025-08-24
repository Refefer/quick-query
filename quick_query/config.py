# -*- coding: utf-8 -*-
"""
Configuration helpers for quick_query.

This module provides utility functions for loading and interpreting the TOML
configuration file used by the CLI.  The original implementation exposed a
``read_model`` function that returned a raw ``dict``.  We are now introducing a
structured ``Profile`` dataclass (see ``quick_query/profile.py``) and helper
functions that return ``Profile`` objects.
"""

import sys
import os
from typing import Optional, Dict, List, Any, Generator, Mapping
import tomllib

from .tools import load_tools
from .profile import Profile

def expand_str(val: str) -> str:
    """Expand $VAR, ${VAR} and %VAR% in a single string."""
    return os.path.expandvars(val)

def expand_env(obj: Any) -> Any:
    """Recursively walk a TOML‑decoded object and expand strings."""
    if isinstance(obj, Mapping):
        return {k: expand_env(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [expand_env(v) for v in obj]

    if isinstance(obj, str):
        return expand_str(obj)

    return obj  # numbers, bools, None

def load_toml_file(
    file_path: str
) -> Dict[str, Any]:
    """
    Load and parse a TOML file into a dictionary.

    Args:
        file_path: Path to the TOML file

    Returns:
        Dictionary of parsed TOML data or empty dict if error
    """
    path = os.path.expanduser(file_path)
    if not os.path.exists(path):
        print(f"Error: File not found: {path}")
        return {}

    try:
        with open(path, "rb") as f:
            return expand_env(tomllib.load(f))

    except tomllib.TOMLDecodeError:
        print(f"Error: Invalid TOML format in {path}", file=sys.stderr)
        return {}

def read_profiles(config_path: str) -> List[Profile]:
    """Load *all* profiles from a TOML configuration file and return them as
    :class:`~quick_query.profile.Profile` instances.

    The TOML layout is expected to contain a top‑level ``profile`` mapping
    (e.g. ``[profile.my‑profile]``) and a top‑level ``credentials`` mapping.
    Each profile entry may contain a ``credentials`` key that references an
    entry in the ``credentials`` table.  The reference is resolved so that the
    resulting ``Profile.credentials`` attribute holds the actual credential dict.

    Parameters
    ----------
    config_path: str
        Path to the TOML configuration file.

    Returns
    -------
    List[Profile]
        One :class:`Profile` object per profile defined in the file.
    """
    data = load_toml_file(config_path)
    profiles_section = data.get("profile", {})
    if not isinstance(profiles_section, Mapping):
        raise ValueError("'profile' section must be a mapping in the TOML file")

    credentials_section = data.get("credentials", {})
    result: List[Profile] = []

    for name, raw in profiles_section.items():
        # Resolve credentials reference (if any)
        cred_key = raw.get("credentials") if isinstance(raw, Mapping) else None
        cred_dict: Dict[str, Any] = {}
        if cred_key:
            if not isinstance(credentials_section, Mapping):
                raise ValueError("'credentials' section must be a mapping in the TOML file")
            cred_dict = credentials_section.get(cred_key, {})

        # Pull known fields; anything else goes into ``extra``
        known_keys = {"model", "tools", "prompt", "structured_streaming", "credentials", "parameters"}
        extra: Dict[str, Any] = {k: v for k, v in (raw or {}).items() if k not in known_keys}

        profile_obj = Profile(
            name=name,
            model=raw.get("model") if isinstance(raw, Mapping) else None,
            credentials=cred_dict,
            tools=raw.get("tools") if isinstance(raw, Mapping) else None,
            prompt_name=raw.get("prompt") if isinstance(raw, Mapping) else None,
            structured_streaming=raw.get("structured_streaming") if isinstance(raw, Mapping) else None,
            parameters=raw.get("parameters") if isinstance(raw, Mapping) else None,
            extra=extra,
        )
        result.append(profile_obj)

    return result

def get_profile(config_path: str, name: str = "default") -> Profile:
    """Return a single :class:`Profile` by name.

    This is a convenience wrapper used by the CLI.  It raises ``KeyError`` if the
    requested profile does not exist.
    """
    for p in read_profiles(config_path):
        if p.name == name:
            return p

    raise KeyError(f"Profile '{name}' not found in {config_path}")

def read_model(
    config_path: str,
    model: Optional[str]
) -> Dict[str, Any]:
    """Legacy wrapper kept for backward compatibility.

    Historically callers expected a plain ``dict``.  This function now delegates
    to :func:`get_profile` and returns ``profile.as_dict()`` so existing code
    continues to work.
    """
    profile = get_profile(config_path, model or "default")
    return profile.as_dict()

def get_profile_prompt_name(
    config_path: str,
    profile: str
) -> Optional[str]:
    """Return the optional ``prompt`` field for *profile*.

    If the field is absent, ``None`` is returned.
    """
    # NOTE: This helper is retained for backward compatibility; new code should
    # use ``Profile.prompt_name`` directly.
    conf = load_toml_file(config_path)
    profiles = conf.get('profile', {})
    selected = profiles.get(profile or 'default', {})
    return selected.get('prompt')

def load_toml_prompt(
    file_path: str,
    section_name: Optional[str]
) -> Optional[str]:
    """
    Load a prompt string from a TOML file section.

    Args:
        file_path: Path to the TOML file
        section_name: Name of the section to retrieve

    Returns:
        Prompt string if found, else None
    """
    if not section_name:
        return None

    data = load_toml_file(file_path)
    section = data.get(section_name, {})
    return section.get("prompt")

def load_tools_from_toml(tool_mapping, file_path):
    data = load_toml_file(file_path)
    return load_tools(tool_mapping, data)
