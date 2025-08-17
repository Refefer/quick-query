"""
Quick‑Query package.
"""

# Load the package version from the VERSION file at the repository root.
import pathlib

_VERSION_FILE = pathlib.Path(__file__).resolve().parent.parent / "VERSION"
try:
    __version__ = _VERSION_FILE.read_text().strip()
except FileNotFoundError:  # Fallback – should never happen after we add VERSION
    __version__ = "0.0.0"

__all__ = ["__version__"]
