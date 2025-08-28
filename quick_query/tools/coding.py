"""
coding.py
~~~~~~~~~
Utility class for performing simple code‑related operations using only the Python standard library.
The implementation mirrors the style of `fs.py`, including type hints, docstrings, and basic error handling.
"""

from __future__ import annotations

import pathlib
import subprocess
import shlex
from typing import Dict, Any, List

# Import the shared base class providing root handling.
from .base import RootedBase


class PatchError(RuntimeError):
    """Exception raised when a subprocess call to ``diff`` or ``patch`` fails.

    Attributes
    ----------
    stdout : str
        Captured standard output from the subprocess.
    stderr : str
        Captured standard error from the subprocess.
    returncode : int
        Exit status of the subprocess (non‑zero indicates failure).
    """

    def __init__(self, stdout: str, stderr: str, returncode: int) -> None:
        super().__init__(stderr or stdout)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class Coding(RootedBase):
    """Utility class for generating diffs and applying patches within a sandbox root.
    Inherits path‑resolution logic from :class:`RootedBase`.
    """

    def __init__(self, root: str = ".") -> None:
        """Initialize the Coding helper with a sandbox root directory.

        Parameters
        ----------
        root : str
            Base directory for all operations.  Paths supplied to the public methods are interpreted relative to this directory.
        """
        super().__init__(root)

    # --------------------------------------------------------------------- #
    # Internal helpers (no need for a custom _resolve_path – inherited from RootedBase)
    # --------------------------------------------------------------------- #
    def _run_subprocess(self, cmd: List[str], input_text: str | None = None) -> str:
        """Run *cmd* with ``cwd=self.root``.

        Parameters
        ----------
        cmd : List[str]
            Command and arguments to execute.
        input_text : str | None, optional
            Text to send to the process's stdin (used for ``patch``).

        Returns
        -------
        str
            The captured stdout of the command.

        Raises
        ------
        PatchError
            If the command exits with a non‑zero status.
        """
        try:
            completed = subprocess.run(
                cmd,
                cwd=self.root,
                input=input_text,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:
            raise PatchError("", str(exc), -1) from exc

        if completed.returncode != 0:
            raise PatchError(completed.stdout, completed.stderr, completed.returncode)

        return completed.stdout

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def diff_files(self, file1: str, file2: str) -> Any:
        """Produce a ``normal diff`` representation of the differences between *file1* and *file2*.

        Returns the diff string on success or an error string on failure.
        """
        try:
            path1 = str(self.resolve_path(file1))
            path2 = str(self.resolve_path(file2))
            diff_output = self._run_subprocess(["diff", path1, path2])
            return diff_output
        except PatchError as exc:
            return f"Error using `{self.__class__.__name__}`: {exc.stderr or exc.stdout}"
        except Exception as exc:
            return f"Error using `{self.__class__.__name__}`: {exc}"

    def apply_patch(self, filename: str, patch: str) -> Any:
        """Apply a ``normal diff`` patch to the given file.

        Returns ``True`` on success or an error string on failure.
        """
        try:
            target = self.resolve_path(filename)
            # The external ``patch`` command reads the diff from stdin.
            self._run_subprocess(["patch", str(target)], input_text=patch)
            return True
        except PatchError as exc:
            return f"Error using `{self.__class__.__name__}`: {exc.stderr or exc.stdout}"
        except Exception as exc:
            return f"Error using `{self.__class__.__name__}`: {exc}"
