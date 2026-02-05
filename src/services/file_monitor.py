"""
File monitoring service using Watchdog for automatic RAG document processing.
"""

import time
from pathlib import Path
from typing import Callable, Optional, List
from threading import Thread, Event

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from src.core.config import config
from src.utils.logging import get_logger, trace_function

logger = get_logger(__name__)


class DocumentFileHandler(FileSystemEventHandler):
    """
    File system event handler for document processing.
    """

    def __init__(
        self,
        supported_extensions: List[str],
        on_file_callback: Callable[[str], None],
    ):
        """
        Initialize handler.

        Args:
            supported_extensions: List of file extensions to monitor (e.g., ['.pdf', '.docx'])
            on_file_callback: Callback function to call when file is created/modified
        """
        super().__init__()
        self.supported_extensions = [ext.lower() for ext in supported_extensions]
        self.on_file_callback = on_file_callback
        self.processing = set()

    def _is_supported_file(self, file_path: str) -> bool:
        """Check if file is supported"""
        path = Path(file_path)
        return path.suffix.lower() in self.supported_extensions and path.exists()

    @trace_function("file_event_handler")
    def _handle_file(self, file_path: str):
        """Handle file creation/modification"""
        if not self._is_supported_file(file_path):
            return

        # Avoid processing same file multiple times concurrently
        if file_path in self.processing:
            logger.debug(f"File already being processed: {file_path}")
            return

        try:
            self.processing.add(file_path)

            logger.info(f"New file detected", file_path=file_path)

            # Wait a bit to ensure file is fully written
            time.sleep(1)

            # Call the callback
            self.on_file_callback(file_path)

        except Exception as e:
            logger.error(f"Error processing file: {e}", file_path=file_path)

        finally:
            self.processing.discard(file_path)

    def on_created(self, event):
        """Handle file creation"""
        if isinstance(event, FileCreatedEvent) and not event.is_directory:
            self._handle_file(event.src_path)

    def on_modified(self, event):
        """Handle file modification"""
        if isinstance(event, FileModifiedEvent) and not event.is_directory:
            self._handle_file(event.src_path)


class FileMonitorService:
    """
    File monitoring service using Watchdog.
    Monitors a directory for new/modified documents and triggers processing.
    """

    def __init__(
        self,
        watch_path: Optional[str] = None,
        on_file_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize file monitor.

        Args:
            watch_path: Path to monitor (defaults to config.rag.watch_path)
            on_file_callback: Callback when file is detected (defaults to self._default_callback)
        """
        self.watch_path = watch_path or config.rag.watch_path
        self.on_file_callback = on_file_callback or self._default_callback

        # Ensure watch path exists
        Path(self.watch_path).mkdir(parents=True, exist_ok=True)

        self.observer: Optional[Observer] = None
        self.handler: Optional[DocumentFileHandler] = None
        self.running = Event()

        logger.info(
            f"Initialized FileMonitorService",
            watch_path=self.watch_path,
            auto_process=config.rag.auto_process,
        )

    def _default_callback(self, file_path: str):
        """Default callback that just logs the file"""
        logger.info(f"File detected (no callback set): {file_path}")

    def start(self):
        """Start monitoring"""
        if self.observer is not None:
            logger.warning("File monitor already running")
            return

        try:
            # Create event handler
            self.handler = DocumentFileHandler(
                supported_extensions=config.rag.supported_extensions,
                on_file_callback=self.on_file_callback,
            )

            # Create and start observer
            self.observer = Observer()
            self.observer.schedule(
                self.handler,
                self.watch_path,
                recursive=True,  # Monitor subdirectories
            )
            self.observer.start()
            self.running.set()

            logger.info(
                f"File monitor started",
                watch_path=self.watch_path,
                supported_extensions=config.rag.supported_extensions,
            )

        except Exception as e:
            logger.error(f"Failed to start file monitor: {e}")
            raise

    def stop(self):
        """Stop monitoring"""
        if self.observer is None:
            return

        try:
            self.running.clear()
            self.observer.stop()
            self.observer.join(timeout=5)
            self.observer = None
            self.handler = None

            logger.info("File monitor stopped")

        except Exception as e:
            logger.error(f"Error stopping file monitor: {e}")

    def is_running(self) -> bool:
        """Check if monitor is running"""
        return self.running.is_set()

    def process_existing_files(self):
        """
        Process all existing files in the watch directory.
        Useful for initial setup or batch processing.
        """
        logger.info("Processing existing files in watch directory")

        count = 0
        watch_path_obj = Path(self.watch_path)

        for ext in config.rag.supported_extensions:
            for file_path in watch_path_obj.rglob(f"*{ext}"):
                if file_path.is_file():
                    try:
                        logger.info(f"Processing existing file: {file_path}")
                        self.on_file_callback(str(file_path))
                        count += 1
                    except Exception as e:
                        logger.error(f"Failed to process {file_path}: {e}")

        logger.info(f"Processed {count} existing files")
        return count


# Global file monitor instance
_file_monitor = None


def get_file_monitor(
    watch_path: Optional[str] = None,
    on_file_callback: Optional[Callable[[str], None]] = None,
) -> FileMonitorService:
    """
    Get global file monitor instance.

    Args:
        watch_path: Optional watch path (only used on first call)
        on_file_callback: Optional callback (only used on first call)

    Returns:
        FileMonitorService instance
    """
    global _file_monitor
    if _file_monitor is None:
        _file_monitor = FileMonitorService(
            watch_path=watch_path,
            on_file_callback=on_file_callback,
        )
    return _file_monitor
