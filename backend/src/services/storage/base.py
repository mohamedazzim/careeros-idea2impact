from abc import ABC, abstractmethod

class StorageAdapter(ABC):
    @abstractmethod
    async def save_file(self, filename: str, file_obj: bytes) -> str:
        """Save a file and return its storage path or URI."""
        pass

    @abstractmethod
    async def read_file(self, file_path: str) -> bytes:
        """Read a file and return its content in bytes."""
        pass
