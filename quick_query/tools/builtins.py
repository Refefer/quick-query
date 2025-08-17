import sqlite3
from typing import List
from pathlib import Path
import os

class FileSystem:
    def __init__(self, root):
        try:
            self.root = Path(root).resolve(strict=True)
            self.root_len = len(str(self.root).rstrip('/'))
        except FileNotFoundError as e:
            raise IOError(f"Invalid root path: {str(e)}") from e
        except Exception:
            raise

        if not self.root.is_dir():
            raise NotADirectoryError(f"'{root}' is not a valid directory")

    def resolve_path(self, path):
        """
        Safely read a file given a user path. All paths are treated as relative
        to the root. This method prevents path traversal and symbolic link
        attacks via normalization and containment checks.
        """
        stripped_path = path.lstrip('/')  # Ensure it's treated as a relative path
        resolved_path = (self.root / stripped_path).resolve(strict=False)

        # Ensure that after resolving the path, it's still within the root
        # Only check containment if resolved path exists. If not, it's still caught earlier.
        if not resolved_path.is_relative_to(self.root):
            raise FileNotFoundError(f"File Not Found: {path_str}")

        return resolved_path

    def read_file(self, path: str) -> str:

        """
        Reads the contents of the file.

        Parameters:
            path: str - Relative path of whose contents to read
        """
        try:
            with open(self.resolve_path(path)) as f:
                return {"success": True, "content": f.read()}
        except Exception as e:
            return {"success": False, "error": e.__class__.__name__}

    def write_file(self, path: str, contents: str) -> bool:
        """
        Writes the provided contents to a file.  Returns whether the operation
        was successful or an error message.

        Parameters:
            path: str - Relative path of file to write contents to
            contents: str - Contents of the file to write 
        """
        try:
            with open(self.resolve_path(path), 'w') as out:
                out.write(contents)
                return {"success": True, "content": True}
        except Exception as e:
            return {"success": False, "error": e.__class__.__name__}

    def list_files(self, path: str) -> List[str]:
        """
        Returns the contents of a directory.

        Parameters:
            path: str - Path to the directory.
        """
        try:
            files = []
            for fi in Path(self.resolve_path(path)).iterdir():
                rel_path = str(fi.resolve())[self.root_len:]
                files.append({"path": rel_path, "is_file:": fi.is_file(), "is_dir": fi.is_dir()})

            return {"success": True, "content": files}
        except Exception as e:
            return {"success": False, "error": e.__class__.__name__}

class Memory:

    _instances = {}

    def __new__(cls, *args, **kwargs):
        key = (cls, args, tuple(sorted(list(kwargs))))
        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls)

        return cls._instances[key]

    def __init__(self, db) -> None:
        """Initialize the database connection and create the memories table if it doesn't exist.

        Parameters:
            db: str - The path to the database file. 
        """
        self.conn = sqlite3.connect(db)
        self._create_table()


    def _create_table(self) -> None:
        """
        Create the memories table if it does not exist.

        Parameters:
            None
        """
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    name TEXT PRIMARY KEY,
                    content TEXT
                )
            ''')


    def list_memories(self) -> List[str]:
        """
        Returns a list of all memory names stored.  

        Memories are used to store information about the user, interests, preferences, or 
        other information that is helpful for an AI agent to know.  

        Parameters:
            None
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT name FROM memories')
        return cursor.fetchall()


    def write_memory(
        self,
        name: str,
        content: str
    ) -> None:
        """
        Write a new memory or overwrite an existing one with the given name and content.  
        Memories are used to store information about the user, interests, preferences, or 
        other information that is helpful for an AI agent to know.  

        Memory names are well structured and detailed to make it easier to understand their purpose.

        Parameters:
            name: str - The name of the memory.
            content: str - The content to store in the memory.
        """
        with self.conn:
            self.conn.execute('''
                INSERT OR REPLACE INTO memories (name, content)
                VALUES (?, ?)
            ''', (name, content))


    def read_memory( self, name: str) -> str:
        """
        Read the content of a memory with the given name.

        Parameters:
            name: str - The name of the memory to read.
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT content FROM memories WHERE name = ?', (name,))
        result = cursor.fetchone()
        return result[0] if result else ''


    def delete_memory( self, name: str) -> None:
        """Delete the memory with the given name.

        Parameters:
            name: str - The name of the memory to delete.
        """
        with self.conn:
            self.conn.execute('DELETE FROM memories WHERE name = ?', (name,))
