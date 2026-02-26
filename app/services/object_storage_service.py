from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class ObjectStorageError(Exception):
    pass


class ObjectStorageNotFoundError(ObjectStorageError):
    pass


@dataclass(frozen=True)
class ObjectStorageObjectMeta:
    bucket: str
    object_key: str
    size_bytes: int
    etag: str
    content_type: str
    storage_class: str
    object_version: str | None
    absolute_path: Path


class LocalObjectStorageAdapter:
    def __init__(self, root_dir: Path) -> None:
        self._root_dir = root_dir
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def _safe_object_path(self, bucket: str, object_key: str) -> Path:
        normalized_bucket = bucket.strip()
        if not normalized_bucket:
            raise ObjectStorageError("bucket is empty")
        key_path = PurePosixPath(object_key)
        if key_path.is_absolute() or ".." in key_path.parts:
            raise ObjectStorageError("invalid object key")
        if not key_path.parts:
            raise ObjectStorageError("object key is empty")
        return self._root_dir / normalized_bucket / Path(*key_path.parts)

    def put_bytes(
        self,
        *,
        bucket: str,
        object_key: str,
        content: bytes,
        content_type: str,
        storage_class: str,
    ) -> ObjectStorageObjectMeta:
        path = self._safe_object_path(bucket, object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        etag = hashlib.sha256(content).hexdigest()
        return ObjectStorageObjectMeta(
            bucket=bucket,
            object_key=object_key,
            size_bytes=len(content),
            etag=etag,
            content_type=content_type,
            storage_class=storage_class,
            object_version=None,
            absolute_path=path,
        )

    def stat_object(
        self,
        *,
        bucket: str,
        object_key: str,
        content_type: str,
        storage_class: str,
    ) -> ObjectStorageObjectMeta | None:
        path = self._safe_object_path(bucket, object_key)
        if not path.exists() or not path.is_file():
            return None
        content = path.read_bytes()
        return ObjectStorageObjectMeta(
            bucket=bucket,
            object_key=object_key,
            size_bytes=len(content),
            etag=hashlib.sha256(content).hexdigest(),
            content_type=content_type,
            storage_class=storage_class,
            object_version=None,
            absolute_path=path,
        )

    def get_download_path(self, *, bucket: str, object_key: str) -> Path:
        path = self._safe_object_path(bucket, object_key)
        if not path.exists() or not path.is_file():
            raise ObjectStorageNotFoundError("object not found")
        return path


class ObjectStorageService:
    def __init__(self) -> None:
        backend = os.getenv("OBJECT_STORAGE_BACKEND", "local").strip().lower()
        if backend != "local":
            raise ObjectStorageError(f"unsupported storage backend: {backend}")
        root_dir = Path(os.getenv("OBJECT_STORAGE_ROOT", "data/object_storage"))
        self._adapter = LocalObjectStorageAdapter(root_dir)
        self.default_bucket = os.getenv("OBJECT_STORAGE_BUCKET", "uav-outcomes")
        ttl = os.getenv("OBJECT_STORAGE_SIGNED_URL_TTL_SECONDS", "3600").strip()
        self.upload_url_ttl_seconds = int(ttl) if ttl.isdigit() else 3600

    def build_raw_object_key(self, *, tenant_id: str, session_id: str, file_name: str) -> str:
        safe_file_name = Path(file_name).name.replace("\\", "_").replace("/", "_").strip()
        if not safe_file_name:
            safe_file_name = "raw.bin"
        return f"tenants/{tenant_id}/raw/{session_id}/{safe_file_name}"

    def build_upload_url(self, *, session_id: str) -> str:
        return f"/api/outcomes/raw/uploads/{session_id}/content"

    def put_upload_content(
        self,
        *,
        bucket: str,
        object_key: str,
        content: bytes,
        content_type: str,
        storage_class: str,
    ) -> ObjectStorageObjectMeta:
        return self._adapter.put_bytes(
            bucket=bucket,
            object_key=object_key,
            content=content,
            content_type=content_type,
            storage_class=storage_class,
        )

    def stat_upload_content(
        self,
        *,
        bucket: str,
        object_key: str,
        content_type: str,
        storage_class: str,
    ) -> ObjectStorageObjectMeta | None:
        return self._adapter.stat_object(
            bucket=bucket,
            object_key=object_key,
            content_type=content_type,
            storage_class=storage_class,
        )

    def get_download_path(self, *, bucket: str, object_key: str) -> Path:
        return self._adapter.get_download_path(bucket=bucket, object_key=object_key)
