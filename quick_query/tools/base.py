"""Common utilities for tools operating under a fixed filesystem root."""

from __future__ import annotations

import pathlib


class RootedBase:
    """Base class that stores a *root* directory and supplies a safe ``resolve_path`` method.

    Sub‑classes (e.g. :class:`FileSystem` or :class:`Coding`) can rely on this
    functionality instead of re‑implementing it.
    """

    def __init__(self, root: str) -> None:
        """Initialize the object with a directory that will serve as the sandbox root.

        Parameters
        ----------
        root : str
            Path to an existing directory.  All relative paths used by the tool are
            resolved against this directory and must stay inside it.
        """
        # Resolve the provided path and ensure it points at an actual directory.
        self.root = pathlib.Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise NotADirectoryError(f"'{root}' is not a valid directory")

        # Length of the root path without trailing slash – useful when we need to
        # present paths relative to the sandbox.
        self.root_len = len(str(self.root).rstrip("/"))

    def resolve_path(self, path: str) -> pathlib.Path:
        """Resolve *path* relative to ``self.root`` and verify it does not escape.

        Parameters
        ----------
        path : str
            User‑supplied path (may start with a leading slash).

        Returns
        -------
        pathlib.Path
            The absolute, sanitized path inside the sandbox.

        Raises
        ------
        FileNotFoundError
            If the resolved location would be outside ``self.root``.
        """
        # Strip any leading '/' so that it is always treated as relative to root.
        stripped_path = path.lstrip("/")
        resolved_path = (self.root / stripped_path).resolve(strict=False)

        # pathlib.Path.is_relative_to() is available from Python 3.9.
        if not resolved_path.is_relative_to(self.root):
            raise FileNotFoundError(f"File Not Found: {path}")

        return resolved_path
