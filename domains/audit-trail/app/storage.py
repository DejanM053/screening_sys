"""MinIO document storage for the audit-trail service."""
from __future__ import annotations

import io
from typing import Optional

from minio import Minio

from app.config import settings


class DocumentStore:
    def __init__(
        self,
        endpoint: str = settings.minio_endpoint,
        access_key: str = settings.minio_access_key,
        secret_key: str = settings.minio_secret_key,
        secure: bool = settings.minio_secure,
        bucket: str = settings.minio_bucket,
    ):
        self._client: Optional[Minio] = None
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._secure = secure
        self.bucket = bucket

    def _get_client(self) -> Minio:
        if self._client is None:
            self._client = Minio(
                self._endpoint,
                access_key=self._access_key,
                secret_key=self._secret_key,
                secure=self._secure,
            )
            if not self._client.bucket_exists(self.bucket):
                self._client.make_bucket(self.bucket)
        return self._client

    def put(self, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        client = self._get_client()
        client.put_object(
            self.bucket,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return f"{self.bucket}/{object_name}"

    def get(self, object_name: str) -> bytes:
        client = self._get_client()
        response = client.get_object(self.bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
