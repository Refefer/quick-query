"""FileSystem implementation that inherits from RootedBase.
"""
from __future__ import annotations

import atexit
import pathlib
import tempfile
import shutil
import os
import subprocess
import re
from typing import List, Dict, Any, Optional

from .base import RootedBase


class FileSystem(RootedBase):
    """Utility class for safe file operations within a designated root directory."""

    def __init__(self, root: str) -> None:
        """
        Initialize the FileSystem with a root directory.

        Parameters:
            root: str - Path to the root directory.
        """
        super().__init__(root)
        # Keep track of temporary files created via ``create_temp_file`` so we can
        # clean them up automatically when the interpreter exits.
        self._temp_files: List[pathlib.Path] = []
        atexit.register(self._cleanup_temp_files)

    def _cleanup_temp_files(self) -> None:
        """Remove any temporary files that were created during this session.

        This method is registered with ``atexit`` and will be called when the
        Python process terminates.  Errors during cleanup are silenced to avoid
        interfering with normal shutdown procedures.
        """
        for temp_path in self._temp_files:
            if temp_path.exists():
                temp_path.unlink()

        self._temp_files.clear()
    
    def create_temp_file(self, dirname: str, content: str | None) -> Dict[str, Any]:
        """Create an empty temporary file with a random name inside *dir*.  This
        method is useful for creating a file to write a code change to and then diffing
        it with the original.

        The file is created on disk and its path is recorded so that it will be
        automatically removed when the interpreter exits.

        Parameters:
            dirname: str - Relative directory (under the managed root) where the temporary file should be placed.
            content: optional str - If provided, writes the content to the new file.

        Returns
        -------
        dict - {"success": true, "path": "relative/path/to/temp/file"} or {"success": false, "error": "..."}
        """
        target_dir = self.resolve_path(dirname)
        if not target_dir.is_dir():
            return {"success": False, "error": f"{target_dir} is not a directory."}

        # ``delete=False`` because we want to manage deletion ourselves.
        tmp = tempfile.NamedTemporaryFile(delete=False, dir=str(target_dir))
        tmp_path = pathlib.Path(tmp.name)
        tmp.close()

        self._temp_files.append(tmp_path)
        if content is not None:
            with open(tmp_path, "w") as out:
                out.write(content)

        rel_path = str(tmp_path.resolve())[self.root_len:]
        return {"success": True, "path": rel_path}

    def read_file(self, path: str) -> Dict[str, Any]:
        """
        Read the contents of a file.

        Parameters:
            path: str - Relative path of the file to read.

        Returns:
            dict - {"success": bool, "content": str} on success,
                    {"success": bool, "error": str} on failure.
        """
        try:
            with open(self.resolve_path(path)) as f:
                return {"success": True, "content": f.read()}

        except Exception as e:
            return {"success": False, "error": e.__class__.__name__}

    def write_file(self, path: str, contents: str) -> Dict[str, Any]: 
        """
        Write contents to a file.  Always confirm with user prior to calling it.

        Parameters:
            path: str - Relative path of the file to write.
            contents: str - Text to write to the file.

        Returns:
            dict - {"success": True, "content": True} on success,
                    {"success": False, "error": str} on failure.
        """
        try:
            with open(self.resolve_path(path), "w") as out:
                out.write(contents)
                return {"success": True, "content": True}

        except Exception as e:
            return {"success": False, "error": e.__class__.__name__}

    def list_files(self, path: Optional[str] = '/') -> Dict[str, Any]:
        """
        List all entries in a directory.  If path is not provided, lists all
        files at '/'.

        Parameters:
            path: str - Relative path to the directory.

        Returns:
            dict - {"success": True, "content": list} on success,
                    {"success": False, "error": str} on failure.
        """
        try:
            files: List[Dict[str, Any]] = []
            for fi in pathlib.Path(self.resolve_path(path)).iterdir():
                rel_path = str(fi.resolve())[self.root_len:]
                files.append(
                    {
                        "path": rel_path,
                        "is_file": fi.is_file(),
                        "is_dir": fi.is_dir(),
                    }
                )
            return {"success": True, "content": files}

        except Exception as e:
            return {"success": False, "error": e.__class__.__name__}

    def delete_file(self, path: str) -> Dict[str, Any]:
        """
        Deletes a file in a directory.  Always confirm with user prior to deletion.

        Parameters:
            path: str - Relative path to the file.

        Returns:
            dict - {"success": True} on success,
                    {"success": False, "error": str} on failure.
        """
        try:
            path = self.resolve_path(path)
            path.unlink()
            return {"success": True}

        except Exception as e:
            return {"success": False, "error": e.__class__.__name__}

    def create_directory(self, path: str) -> Dict[str, Any]:
        """Create a new directory within the managed root.

        Parameters:
        path: str - Relative path of the directory to create.

        Returns:
            dict - {"success": True, "content": True} on success.  If the directory
                already exists, this is treated as a successful no‑op.  On failure the
                dictionary contains {"success": False, "error": "<ExceptionName>"}.

        """
        try:
            dir_path = self.resolve_path(path)
            if dir_path.is_dir():
                return {"success": True, "content": True}

            os.makedirs(dir_path, exist_ok=True)
            return {"success": True, "content": True}

        except Exception as e:
            return {"success": False, "error": e.__class__.__name__}

    def move_file(self, src: str, dest: str) -> Dict[str, Any]:
        """
        Move a file from ``src`` to ``dest``.  If the file at ``dest`` already exists,
        it is overwritten.

        Parameters:
            src: str  - Relative path of the source file to be moved.
            dest: str - Relative path of the destination **file**.  The parent directory
                        must already exist; the method does **not** create missing
                        directories.

        Returns:
            dict - {"success": True, "content": True} on success or {"success": False, "error": <ExceptionName>} on failure.

        """
        try:
            src_path = self.resolve_path(src)
            dest_path = self.resolve_path(dest)

            # Ensure source exists
            if not src_path.is_file():
                raise FileNotFoundError(f"Source file not found: {src}")

            # Ensure destination directory exists
            dest_dir = dest_path.parent
            if not dest_dir.is_dir():
                raise FileNotFoundError(f"Destination directory not found: {dest_dir}")

            shutil.move(str(src_path), str(dest_path))
            return {"success": True, "content": True}

        except Exception as e:
            return {"success": False, "error": e.__class__.__name__}
    
    def search_by_regex(self, path: str, regex: str, context: int) -> Dict[str, Any]:
        """Search files under `path` for a regular expression using egrep.

        Parameters:
            path (str): Relative directory inside the managed root where the search starts.
            regex (str): The regular expression pattern to match.
            context (int): Number of surrounding lines to include as context.

        Returns:
            dict: On success {"success": True, "content": <string>} containing the formatted egrep output with file paths converted to relative form.  
                  On failure {"success": False, "error": <error_message>}
        """
        try:
            # Resolve the base directory; this also validates that it is within the root.
            base_path = self.resolve_path(path)

            # Build the egrep command.  -R for recursive, -C<cnt> for context lines.
            cmd = ["egrep", "-R", f"-C{context}", regex, "-n", str(base_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)

            # egrep returns 0 if matches found, 1 if none, >1 for errors.
            if result.returncode not in (0, 1):
                return {"success": False, "error": f"egrep failed: {result.stderr.strip()}"}

            output = result.stdout
            # Convert any absolute file paths in the output to relative paths.
            lines = []
            for line in output.splitlines():
                line = line.rstrip('\n')
                if line == '--':
                    lines.append(line)
                    continue

                parsed = parse_egrep_line(line)
                if parsed is None:
                    continue

                abs_path = pathlib.Path(parsed['filename']).resolve()
                rel_path = str(abs_path)[self.root_len:]
                parsed['filename'] = rel_path
                delim = '-' if parsed['context'] else ':'
                lines.append(f"{rel_path}{delim}{parsed['lineno']}{delim}{parsed['content']}")

            return {"success": True, "content": '\n'.join(lines)}

        except Exception as e:
            return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------- 
# Regex that recognises BOTH egrep formats: 
# 
#   1) Context lines (surrounding the match) 
#        <filename>-<lineno>- 
#   2) The matching line itself 
#        <filename>:<lineno>: 
# 
#   • <filename> may contain spaces, hyphens, dots, colons, etc. 
#   • The line‑content part (everything after the last delimiter) 
#     is captured unchanged. 
# ---------------------------------------------------------------------- 
EGREP_LINE_RE = re.compile(r'''
    ^                                   # start of line
    (?P<filename>.+?)                   # filename – lazy so it stops at the first delimiter
    (?:                                 # non‑capturing group for the two possible delimiters
        ([-:])(?P<lineno>\d+)\2         #   a) context line  → “-23-”
    )
    (?P<content>.*)                     # the rest of the line (the source code)
    $                                   # end of line
''', re.VERBOSE)

def parse_egrep_line(line: str) -> Dict:
    """Parse a single egrep output line.

    Returns 
    ------- 
    dict | None 
        ``{'filename': ..., 'lineno': int, 'is_match': bool, 'content': ...}`` 
        or ``None`` if the line does not match the expected format. 
    """
    m = EGREP_LINE_RE.match(line)
    if not m:
        return None

    lineno = int(m.group('lineno'))

    # ':' is a a match delimieter, '-' is a context delimiter.
    is_match = ':' in line.split(str(lineno))[0]
    return {
        'filename': m.group('filename'), 
        'lineno': lineno, 
        'context': not is_match,
        'content': m.group('content')
    }
