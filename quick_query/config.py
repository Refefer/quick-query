import os
from typing import Optional, Dict, List, Any, Generator
import tomllib

from .tools import load_tools

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
            return tomllib.load(f)

    except tomllib.TOMLDecodeError:
        print(f"Error: Invalid TOML format in {path}")
        return {}


def read_api_conf(
    config_path: str,
    namespace: Optional[str]
) -> Dict[str, Any]:
    """
    Read API configuration from a TOML file for a given namespace.

    Args:
        config_path: Path to the configuration file
        namespace: Section name in the TOML file

    Returns:
        Dict of configuration values
    """
    conf = load_toml_file(config_path)
    ns = namespace or "default"
    return conf.get(ns, {})


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

def load_tools_from_toml(file_path):
    data = load_toml_file(file_path)
    return load_tools(data)

