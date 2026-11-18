"""
Django storage backend that keeps files in the `stored_files` table.   Owner: Aitore
Enabled by MEDIA_STORAGE=db (see settings). Files are small (tour photos, max 5 MB each), so a BYTEA column is fine.
"""
import io
import posixpath

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.crypto import get_random_string
from django.utils.deconstruct import deconstructible


@deconstructible
class DatabaseStorage(Storage):
    def _model(self):
        from core.models import StoredFile      # lazy: storage is created before the apps are ready
        return StoredFile

    def _open(self, name, mode="rb"):
        row = self._model().objects.filter(name=name).only("content").first()
        if row is None:
            raise FileNotFoundError(name)
        return ContentFile(bytes(row.content), name=name)

    def _save(self, name, content):
        if hasattr(content, "seek"):
            content.seek(0)
        data = content.read()
        if isinstance(data, str):
            data = data.encode()
        self._model().objects.create(name=name, content=data, size=len(data))
        return name

    def get_available_name(self, name, max_length=None):
        name = name.replace("\\", "/")
        root, ext = posixpath.splitext(name)
        while self.exists(name):
            name = f"{root}_{get_random_string(7)}{ext}"
        return name

    def delete(self, name):
        self._model().objects.filter(name=name).delete()

    def exists(self, name):
        return self._model().objects.filter(name=name).exists()

    def size(self, name):
        row = self._model().objects.filter(name=name).only("size").first()
        if row is None:
            raise FileNotFoundError(name)
        return row.size

    def url(self, name):
        raise NotImplementedError("Files are served by their own API views (e.g. /api/photos/<id>).")

    def path(self, name):
        raise NotImplementedError("Files in the database have no filesystem path.")
