import sys
import os
from typing import Optional, Dict, List, Any, Generator, Mapping
import tomllib

from .tools import load_tools

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

def read_model(
    config_path: str,
    model: Optional[str]
) -> Dict[str, Any]:
    """
    Read API configuration from a TOML file for a given profile.

    Args:
        config_path: Path to the configuration file
        model: Name of the profile (section) to retrieve; defaults to "default".

    Returns:
        Dict of configuration values
    """
    conf = load_toml_file(config_path)
    # The top‑level key is now "profile" instead of "models"
    profiles = conf.get('profile', {})
    if not profiles:
        raise KeyError("No 'profile' section found in configuration file")
    selected = profiles[model or "default"]
    credentials = conf['credentials'][selected['credentials']]
    selected['credentials'] = credentials
    return selected

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

