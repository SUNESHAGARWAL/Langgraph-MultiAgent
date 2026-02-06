"""
Azure Blob Storage monitoring service for RAG document processing.
Replaces local filesystem monitoring for production scalability.
"""

import time
import io
from pathlib import Path
from typing import Callable, Optional, List, Set, Dict
from threading import Thread, Event
from datetime import datetime, timedelta

from src.core.config import config
from src.utils.logging import get_logger, trace_function

logger = get_logger(__name__)


class BlobMonitorService:
    """
    Azure Blob Storage monitoring service for RAG documents.

    IMPORTANT: Monitors Azure Blob Storage container instead of local filesystem.
    This is production-ready and works in distributed/containerized environments.

    Process:
    1. Polls Azure Blob Storage container every N seconds
    2. Detects new/modified blobs
    3. Downloads blob to temp directory
    4. Triggers callback for processing
    5. Tracks processed blobs to avoid duplicates
    """

    def __init__(
        self,
        container_name: Optional[str] = None,
        blob_prefix: Optional[str] = "",
        on_file_callback: Optional[Callable[[str], None]] = None,
        poll_interval: Optional[int] = None,  # defaults to config.rag.poll_interval
    ):
        """
        Initialize blob monitor.

        Args:
            container_name: Azure Blob container to monitor (defaults to config)
            blob_prefix: Optional prefix filter (e.g., "documents/")
            on_file_callback: Callback function when new file detected
            poll_interval: How often to check for new blobs (seconds)
        """
        # Get RAG container and prefix from config
        rag_container, rag_prefix_default = config.azure_storage.get_rag_config()

        self.container_name = container_name or rag_container
        # Use provided prefix, or default from config, or empty string
        self.blob_prefix = blob_prefix if blob_prefix else (rag_prefix_default or "")
        self.on_file_callback = on_file_callback
        self.poll_interval = poll_interval if poll_interval is not None else config.rag.poll_interval

        # Supported file extensions
        self.supported_extensions = [
            ext.lower() for ext in config.rag.supported_extensions
        ]

        # Track processed blobs (blob_name -> last_modified_time)
        self.processed_blobs: Dict[str, datetime] = {}

        # Thread control
        self.observer_thread: Optional[Thread] = None
        self.stop_event = Event()

        # Get blob storage service
        self._storage = None

        logger.info(
            f"Initialized BlobMonitorService",
            container=self.container_name,
            prefix=self.blob_prefix,
            poll_interval=poll_interval,
        )

    @property
    def storage(self):
        """Lazy load blob storage to avoid circular imports"""
        if self._storage is None:
            from src.services.storage import get_blob_storage
            self._storage = get_blob_storage()
        return self._storage

    def _is_supported_file(self, blob_name: str) -> bool:
        """Check if blob is a supported file type"""
        return any(blob_name.lower().endswith(ext) for ext in self.supported_extensions)

    @trace_function("poll_blob_storage")
    def _poll_blobs(self):
        """Poll Azure Blob Storage for new/modified files"""
        try:
            # List blobs in container with optional prefix
            blobs = self.storage.list_blobs(self.container_name, self.blob_prefix)

            for blob in blobs:
                blob_name = blob.get("name")
                last_modified = blob.get("last_modified")

                # Skip if not supported file type
                if not self._is_supported_file(blob_name):
                    continue

                # Check if blob is new or modified
                if blob_name not in self.processed_blobs:
                    # New blob
                    logger.info(f"New blob detected", blob=blob_name, container=self.container_name)
                    self._process_blob(blob_name)
                    self.processed_blobs[blob_name] = last_modified

                elif self.processed_blobs[blob_name] < last_modified:
                    # Modified blob
                    logger.info(f"Modified blob detected", blob=blob_name, container=self.container_name)
                    self._process_blob(blob_name)
                    self.processed_blobs[blob_name] = last_modified

        except Exception as e:
            logger.error(f"Error polling blob storage: {e}")

    def _process_blob(self, blob_name: str):
        """
        Download blob to temp directory and trigger processing.

        Args:
            blob_name: Name of the blob to process
        """
        try:
            # Download blob data
            blob_data = self.storage.download_blob(self.container_name, blob_name)

            if not blob_data:
                logger.warning(f"Could not download blob", blob=blob_name)
                return

            # Create temp file
            temp_dir = Path("/tmp/rag_blobs")
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Use just the filename from blob path
            filename = Path(blob_name).name
            temp_file = temp_dir / filename

            # Write blob data to temp file
            with open(temp_file, "wb") as f:
                f.write(blob_data)

            logger.info(
                f"Downloaded blob to temp file",
                blob=blob_name,
                temp_file=str(temp_file),
            )

            # Trigger callback with temp file path
            if self.on_file_callback:
                self.on_file_callback(str(temp_file))

        except Exception as e:
            logger.error(f"Error processing blob: {e}", blob=blob_name)

    def _monitor_loop(self):
        """Main monitoring loop (runs in background thread)"""
        logger.info(f"Starting blob monitoring loop", container=self.container_name)

        while not self.stop_event.is_set():
            try:
                self._poll_blobs()
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            # Wait before next poll
            self.stop_event.wait(self.poll_interval)

        logger.info(f"Blob monitoring loop stopped")

    def start(self):
        """Start monitoring Azure Blob Storage"""
        if self.observer_thread and self.observer_thread.is_alive():
            logger.warning("Blob monitor already running")
            return

        logger.info(f"Starting blob monitor", container=self.container_name)

        self.stop_event.clear()
        self.observer_thread = Thread(target=self._monitor_loop, daemon=True)
        self.observer_thread.start()

        logger.info("✅ Blob monitor started successfully")

    def stop(self):
        """Stop monitoring"""
        if not self.observer_thread or not self.observer_thread.is_alive():
            logger.warning("Blob monitor not running")
            return

        logger.info("Stopping blob monitor")

        self.stop_event.set()

        if self.observer_thread:
            self.observer_thread.join(timeout=5)

        logger.info("✅ Blob monitor stopped")

    def get_stats(self) -> dict:
        """Get monitoring statistics"""
        return {
            "container": self.container_name,
            "blob_prefix": self.blob_prefix,
            "poll_interval": self.poll_interval,
            "processed_blobs": len(self.processed_blobs),
            "is_running": self.observer_thread and self.observer_thread.is_alive(),
        }


# Global blob monitor
_blob_monitor = None


def get_blob_monitor(
    container_name: Optional[str] = None,
    on_file_callback: Optional[Callable[[str], None]] = None,
) -> BlobMonitorService:
    """Get global blob monitor service"""
    global _blob_monitor
    if _blob_monitor is None:
        _blob_monitor = BlobMonitorService(
            container_name=container_name,
            on_file_callback=on_file_callback,
        )
    return _blob_monitor
