"""
Azure Blob Storage service for persisting data.
"""

import json
import pickle
from typing import Any, Optional
from datetime import datetime, timedelta

from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceNotFoundError

from src.core.config import config
from src.utils.logging import get_logger, trace_function

logger = get_logger(__name__)


class AzureBlobStorage:
    """
    Azure Blob Storage service for caching, EDA results, and RAG documents.
    """

    def __init__(self):
        self.blob_service_client = BlobServiceClient.from_connection_string(
            config.azure_storage.connection_string
        )
        self._ensure_containers()

    def _ensure_containers(self):
        """Ensure all required containers exist"""
        containers = [
            config.azure_storage.container_cache,
            config.azure_storage.container_rag,
            config.azure_storage.container_eda,
        ]

        for container_name in containers:
            try:
                container_client = self.blob_service_client.get_container_client(
                    container_name
                )
                if not container_client.exists():
                    self.blob_service_client.create_container(container_name)
                    logger.info(f"Created container: {container_name}")
            except Exception as e:
                logger.warning(f"Error checking/creating container {container_name}: {e}")

    @trace_function("upload_blob")
    def upload_blob(
        self,
        container_name: str,
        blob_name: str,
        data: Any,
        serialize: str = "json",
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Upload data to blob storage.

        Args:
            container_name: Container name
            blob_name: Blob name (path)
            data: Data to upload
            serialize: Serialization format ('json', 'pickle', 'text')
            metadata: Optional metadata dict

        Returns:
            Blob URL
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )

            # Serialize data
            if serialize == "json":
                serialized_data = json.dumps(data, default=str).encode("utf-8")
            elif serialize == "pickle":
                serialized_data = pickle.dumps(data)
            elif serialize == "text":
                serialized_data = str(data).encode("utf-8")
            else:
                raise ValueError(f"Unsupported serialization format: {serialize}")

            # Upload
            blob_client.upload_blob(serialized_data, overwrite=True, metadata=metadata)

            logger.info(
                f"Uploaded blob to {container_name}/{blob_name}",
                blob_size=len(serialized_data),
            )

            return blob_client.url

        except Exception as e:
            logger.error(f"Failed to upload blob: {e}")
            raise

    @trace_function("download_blob")
    def download_blob(
        self, container_name: str, blob_name: str, deserialize: str = "json"
    ) -> Any:
        """
        Download data from blob storage.

        Args:
            container_name: Container name
            blob_name: Blob name (path)
            deserialize: Deserialization format ('json', 'pickle', 'text')

        Returns:
            Deserialized data
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )

            # Download
            blob_data = blob_client.download_blob().readall()

            # Deserialize
            if deserialize == "json":
                return json.loads(blob_data.decode("utf-8"))
            elif deserialize == "pickle":
                return pickle.loads(blob_data)
            elif deserialize == "text":
                return blob_data.decode("utf-8")
            else:
                raise ValueError(f"Unsupported deserialization format: {deserialize}")

        except ResourceNotFoundError:
            logger.warning(f"Blob not found: {container_name}/{blob_name}")
            return None
        except Exception as e:
            logger.error(f"Failed to download blob: {e}")
            raise

    @trace_function("blob_exists")
    def blob_exists(self, container_name: str, blob_name: str) -> bool:
        """Check if blob exists"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            return blob_client.exists()
        except Exception as e:
            logger.error(f"Error checking blob existence: {e}")
            return False

    @trace_function("list_blobs")
    def list_blobs(self, container_name: str, prefix: Optional[str] = None) -> list:
        """
        List blobs in container with metadata.

        Args:
            container_name: Container name
            prefix: Optional prefix filter

        Returns:
            List of dicts with blob info: [{"name": "...", "last_modified": datetime, "size": int}, ...]
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blobs = container_client.list_blobs(name_starts_with=prefix)
            return [
                {
                    "name": blob.name,
                    "last_modified": blob.last_modified,
                    "size": blob.size,
                }
                for blob in blobs
            ]
        except Exception as e:
            logger.error(f"Failed to list blobs: {e}")
            return []

    @trace_function("delete_blob")
    def delete_blob(self, container_name: str, blob_name: str) -> bool:
        """Delete blob"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            blob_client.delete_blob()
            logger.info(f"Deleted blob: {container_name}/{blob_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete blob: {e}")
            return False

    # Convenience methods for specific containers

    def save_cache(self, key: str, data: Any, ttl_seconds: Optional[int] = None):
        """Save to cache container"""
        metadata = {}
        if ttl_seconds:
            expiry = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            metadata["expiry"] = expiry.isoformat()

        self.upload_blob(
            config.azure_storage.container_cache,
            f"cache/{key}.json",
            data,
            serialize="json",
            metadata=metadata,
        )

    def load_cache(self, key: str) -> Optional[Any]:
        """Load from cache container"""
        blob_name = f"cache/{key}.json"

        # Check if expired
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=config.azure_storage.container_cache, blob=blob_name
            )
            props = blob_client.get_blob_properties()
            metadata = props.metadata

            if metadata and "expiry" in metadata:
                expiry = datetime.fromisoformat(metadata["expiry"])
                if datetime.utcnow() > expiry:
                    self.delete_blob(config.azure_storage.container_cache, blob_name)
                    return None

        except ResourceNotFoundError:
            return None

        return self.download_blob(config.azure_storage.container_cache, blob_name)

    def save_eda_results(self, table_name: str, results: dict):
        """Save EDA results for a table"""
        self.upload_blob(
            config.azure_storage.container_eda,
            f"eda/{table_name}.json",
            results,
            serialize="json",
        )

    def load_eda_results(self, table_name: str) -> Optional[dict]:
        """Load EDA results for a table"""
        return self.download_blob(
            config.azure_storage.container_eda, f"eda/{table_name}.json"
        )

    def save_rag_metadata(self, file_name: str, metadata: dict):
        """Save RAG file metadata"""
        self.upload_blob(
            config.azure_storage.container_rag,
            f"metadata/{file_name}.json",
            metadata,
            serialize="json",
        )

    def load_rag_metadata(self, file_name: str) -> Optional[dict]:
        """Load RAG file metadata"""
        return self.download_blob(
            config.azure_storage.container_rag, f"metadata/{file_name}.json"
        )


# Global storage instance
_storage_service = None


def get_storage_service() -> AzureBlobStorage:
    """Get global storage service instance"""
    global _storage_service
    if _storage_service is None:
        _storage_service = AzureBlobStorage()
    return _storage_service


# Alias for consistency
def get_blob_storage() -> AzureBlobStorage:
    """Alias for get_storage_service()"""
    return get_storage_service()
