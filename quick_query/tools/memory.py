import sqlite3
from typing import List

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
        Returns a list of all memories stored.

        Memories are used to store information about the user, interests, preferences, or 
        other information that is helpful for an AI agent to know.  

        Parameters:
            None
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT name FROM memories')
        return cursor.fetchall()


    def add_memory(
        self,
        name: str,
        content: str
    ) -> None:
        """
        Adds a new memory or overwrite an existing one with the given name and content.  
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


