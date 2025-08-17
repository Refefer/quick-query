import pathlib
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
