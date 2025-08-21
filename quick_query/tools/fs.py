import atexit
import pathlib
import tempfile
from typing import List, Dict, Any, Optional

class FileSystem:
    """Utility class for safe file operations within a designated root directory."""

    def __init__(self, root: str) -> None:
        """
        Initialize the FileSystem with a root directory.

        Parameters:
            root: str - Path to the root directory.
        """
        try:
            self.root = pathlib.Path(root).resolve(strict=True)
            self.root_len = len(str(self.root).rstrip("/"))
        except FileNotFoundError as e:
            raise IOError(f"Invalid root path: {str(e)}") from e
        except Exception:
            raise

        if not self.root.is_dir():
            raise NotADirectoryError(f"'{root}' is not a valid directory")

        # Keep track of temporary files created via ``create_temp_file`` so we can
        # clean them up automatically when the interpreter exits.
        self._temp_files: List[pathlib.Path] = []
        atexit.register(self._cleanup_temp_files)

    def resolve_path(self, path: str) -> pathlib.Path:
        """
        Safely resolve a user-provided path relative to the root directory.

        Parameters:
            path: str - Relative path to resolve.

        Returns:
            pathlib.Path - Resolved absolute path.

        Raises:
            FileNotFoundError: If the resolved path is outside the root.
        """
        stripped_path = path.lstrip("/")
        resolved_path = (self.root / stripped_path).resolve(strict=False)

        if not resolved_path.is_relative_to(self.root):
            raise FileNotFoundError(f"File Not Found: {path}")

        return resolved_path

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

    def create_temp_file(self, dirname: str, content: str | None) -> str:
        """Create an empty temporary file with a random name inside *dir*.  This
        method is useful for creating a file to write a code change to and then diffing
        it with the original.

        The file is created on disk and its path is recorded so that it will be
        automatically removed when the interpreter exits.

        Parameters:
            dirname: str - Relative directory (under the managed root) where the temporary file should be placed.
            dirname: optional str - If provided, writes the content to the new file.

        Returns
        -------
        str - {"success": true, "path": "path/to/temp/file"} or {"success": false, "error": str}
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
            with open(tmp_path, 'w') as out:
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

    def list_files(self, path: Optional[str]) -> Dict[str, Any]:
        """
        List all entries in a directory.  If path is not provided, lists all
        files at '/'.  Relative paths are converted to absolute paths - for example,
        if list_files("path/to/file") is called, it is converted to "/path/to/file".

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


