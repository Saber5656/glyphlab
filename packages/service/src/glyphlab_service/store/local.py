import os
import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from .base import StoreKey


class LocalDiskStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        path = (self.root / str(key)).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Object escaped store root")
        return path

    def put(self, key, data, content_type):
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp, path)
        finally:
            Path(temp).unlink(missing_ok=True)

    def get(self, key):
        try:
            return self.path(key).read_bytes()
        except FileNotFoundError:
            from glyphlab.errors import GlyphlabError

            raise GlyphlabError("E_NOT_FOUND", "Request failed") from None

    def stream(self, key):
        try:
            with self.path(key).open("rb") as source:
                while chunk := source.read(65536):
                    yield chunk
        except FileNotFoundError:
            from glyphlab.errors import GlyphlabError

            raise GlyphlabError("E_NOT_FOUND", "Request failed") from None

    def exists(self, key):
        return self.path(key).is_file()

    def delete(self, key):
        self.path(key).unlink(missing_ok=True)

    def delete_prefix(self, project_id):
        if not isinstance(project_id, UUID):
            raise TypeError("Invalid project ID")
        path = self.path(StoreKey(project_id, "uploads", "0" * 32)).parent.parent
        if path.name != str(project_id):
            raise ValueError("Invalid purge prefix")
        if not path.exists():
            return 0
        count = sum(p.is_file() for p in path.rglob("*"))
        shutil.rmtree(path)
        return count
