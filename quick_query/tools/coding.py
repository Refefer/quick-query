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
import subprocess
import shlex
from typing import Dict, Any, List


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


class Coding:
    """
    A small helper class that can generate a line‑by‑line diff between two
    files and apply such a diff back to a file.  The diff format used is the
    ``difflib.ndiff`` output, which can be directly consumed by
    ``difflib.restore`` — keeping the whole process pure‑Python and portable.
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

    def _run_subprocess(self, cmd: List[str], input_text: str | None = None) -> str:
        """Run *cmd* with ``cwd=self.root``.

        Parameters
        ----------
        cmd: List[str]
            Command and arguments to execute.
        input_text: str | None, optional
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
    def diff_files(self, file1: str, file2: str) -> str:
        """
        Produce an ``normal diff`` representation of the differences between
        *file1* and *file2*.  This is _not_ a unified diff format: for exammple, 
        if the only difference between two files was the first line,
        a patch might look like: 

        ```
        1c1
        < x = 1 + 2
        ---
        > x = 1 * 2
        ```

        Make sure to not use a unified-diff format. 

        Using create_temp_file, followed by a write_file, and then diff_files will provide a correct
        patch in all cases.

        Parameters:
            file1: str - Path to the file on disk to diff against.
            file2: str - Path to the file on disk to diff.

        Returns:
            str - {"success": bool, "diff": (if true) The diff as a single string, "error": str(err)}  
                  This string can be passed directly to :meth:`apply_patch`.
        """
        try:
            # Resolve to absolute paths for the external diff command.
            path1 = str(self._resolve_path(file1))
            path2 = str(self._resolve_path(file2))
            # ``diff -u`` produces a unified diff.
            diff_output = self._run_subprocess(["diff", path1, path2])
            return {"success": True, "diff": diff_output}

        except PatchError as exc:
            return {"success": False, "error": exc.stderr or exc.stdout}

        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def apply_patch(self, filename: str, patch: str) -> Dict[str, Any]:
        """
        Apply a ``normal diff`` patch to the given file.  Patch should _only_ including the patch file,
        no additional instructions or commentary.  For example, if we have a file "foo.py" with the following

        For example, the patch: ```
        1c1
        < x = 1 + 2
        ---
        > x = 1 * 2
        ```
        would patch the first line of code from an addition to a multiply.

        Patches do _not_ include filenames.  Make sure to include a trailing newline.  Even if a 'apply_patch'
        completes successfully, confirm the contents of the file match expectations.

        Parameters:
            filename: str - Path to the file getting patched.
            patch: str - The diff string produced by :meth: `create_diff` or `diff_files`.

        Returns:
            dict - {"success": True}`` on success or ``{"success": False, "error": <error message>} on failure.
        """
        try:
            filename = self._resolve_path(filename)
            # ``patch`` reads the patch from stdin; ``-p1`` means strip leading slash.
            # ``-d <root>`` reinforces the directory restriction.
            self._run_subprocess(["patch", filename], input_text=patch)
            return {"success": True}

        except PatchError as exc:
            print(exc)
            return {"success": False, "error": exc.stderr or exc.stdout}

        except Exception as exc:
            print(exc)
            return {"success": False, "error": str(exc)}

