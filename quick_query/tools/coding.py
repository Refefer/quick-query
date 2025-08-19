# coding.py
"""
coding.py
~~~~~~~~~
Utility class for performing simple code‑related operations using only the
Python standard library.  The implementation mirrors the style of `fs.py`,
including type hints, docstrings, and basic error handling.
"""

from __future__ import annotations

import pathlib
import difflib
from typing import Dict, Any


class Coding:
    """
    A small helper class that can generate a line‑by‑line diff between two
    files and apply such a diff back to a file.  The diff format used is the
    ``difflib.ndiff`` output, which can be directly consumed by
    ``difflib.restore`` – keeping the whole process pure‑Python and portable.
    """

    def __init__(self, root: str = ".") -> None:
        """
        Parameters
        ----------
        root: str
            Base directory for all operations.  Paths supplied to the public
            methods are interpreted relative to this directory.
        """
        self.root = pathlib.Path(root).resolve()

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #
    def _resolve_path(self, path: str) -> pathlib.Path:
        """
        Resolve *path* relative to ``self.root`` and ensure it stays inside the
        root directory.
        """
        resolved = (self.root / path.lstrip("/")).resolve()
        if not str(resolved).startswith(str(self.root)):
            raise FileNotFoundError(f"Path {path!r} is outside the allowed root")
        return resolved

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def diff_files(self, file1: str, file2: str) -> str:
        """
        Produce an ``ndiff`` representation of the differences between
        *file1* and *file2*.

        Parameters:
            file1: str - Path to the file on disk to diff against.
            file2: str - Path to the file on disk to diff.

        Returns:
            str - The diff as a single string.  This string can be passed directly
                to :meth:`apply_patch`.
        """
        try:
            txt1 = self._resolve_path(file1).read_text().splitlines(keepends=True)
            txt2 = self._resolve_path(file2).read_text().splitlines(keepends=True)
            diff = difflib.ndiff(txt1, txt2)
            return "".join(diff)
        except Exception as exc:
            raise RuntimeError(f"Failed to diff files: {exc}") from exc

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def diff_file_with_content(self, filename: str, content: str) -> str:
        """
        Produce an ``ndiff`` representation of the differences between
        *file1* and the provided new file content.

        Parameters:
            filename: str - Path to the file on disk to diff against.
            content: str - New file contents to create a diff against.

        Returns:
            str - The diff as a single string.  This string can be passed directly
                to :meth:`apply_patch`.
        """
        try:
            txt1 = self._resolve_path(filename).read_text().splitlines(keepends=True)
            txt2 = content.splitlines(keepends=True)
            diff = difflib.ndiff(txt1, txt2)
            return "".join(diff)

        except Exception as exc:
            raise RuntimeError(f"Failed to diff files: {exc}") from exc

    def apply_patch(self, filename: str, patch: str) -> Dict[str, Any]:
        """
        Apply an ``ndiff`` *patch* to *filename*.

        Parameters:
            filename: str - Path to the file that should be patched (relative to ``root``).
            patch: str - The diff string produced by :meth:`diff_files`.

        Returns:
            dict - {"success": True}`` on success or ``{"success": False, "error": <error message>} on failure.
        """
        try:
            target = self._resolve_path(filename)
            # ``difflib.restore`` expects an iterable of lines and a ``which``
            # argument.  ``2`` tells it to reconstruct the *second* (i.e. new)
            # version of the file from an ndiff.
            patched_lines = difflib.restore(
                patch.splitlines(keepends=True), 2
            )
            target.write_text("".join(patched_lines))
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

