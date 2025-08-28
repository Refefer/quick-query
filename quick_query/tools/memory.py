import sqlite3
from typing import List, Any

class Memory:

    _instances = {}

    def __new__(cls, *args, **kwargs):
        key = (cls, args, tuple(sorted(list(kwargs))))
        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls)

        return cls._instances[key]

    def __init__(self, db) -> None:
        """Initialize the database connection and create the memories table if it doesn't exist.

        Parameters
        ----------
        db : str
            The path to the database file.
        """
        self.conn = sqlite3.connect(db)
        self._create_table()


    def _create_table(self) -> None:
        """Create the ``memories`` table if it does not already exist."""
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    name TEXT PRIMARY KEY,
                    content TEXT
                )
            ''')


    def list_memories(self):
        """Return a list of all memory names.

        Returns the list on success or an error string on failure.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT name FROM memories')
            return cursor.fetchall()
        except Exception as e:
            return f"Error using `{self.__class__.__name__}`: {e}"


    def add_memory(
        self,
        name: str,
        content: str
    ) -> Any:
        """Add a new memory or overwrite an existing one.

        Returns ``True`` on success or an error string on failure.
        """
        try:
            with self.conn:
                self.conn.execute('''
                    INSERT OR REPLACE INTO memories (name, content)
                    VALUES (?, ?)
                ''', (name, content))
            return True
        except Exception as e:
            return f"Error using `{self.__class__.__name__}`: {e}"


    def read_memory(self, name: str) -> Any:
        """Read the content of a memory.

        Returns the stored string on success (or an empty string if not found) or an error string on failure.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT content FROM memories WHERE name = ?', (name,))
            result = cursor.fetchone()
            return result[0] if result else ''
        except Exception as e:
            return f"Error using `{self.__class__.__name__}`: {e}"


    def delete_memory(self, name: str) -> Any:
        """Delete a memory.

        Returns ``True`` on success or an error string on failure.
        """
        try:
            with self.conn:
                self.conn.execute('DELETE FROM memories WHERE name = ?', (name,))
            return True
        except Exception as e:
            return f"Error using `{self.__class__.__name__}`: {e}"
