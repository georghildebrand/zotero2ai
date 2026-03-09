import os
import json
import time
import logging
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from zotero2ai.queue.schema import QueueJob, JobStatus
from zotero2ai.config import resolve_zotero_mcp_token

# Only importing for type checking if needed, otherwise we will pass the server object
# but for now we'll just parse the json and invoke the MCP functions or PluginClient directly.
from zotero2ai.zotero.plugin_client import PluginClient

logger = logging.getLogger(__name__)

class QueueJobHandler(FileSystemEventHandler):
    def __init__(self, watch_dir: Path):
        self.watch_dir = watch_dir
        self.pending_dir = watch_dir / "pending"
        self.completed_dir = watch_dir / "completed"
        self.failed_dir = watch_dir / "failed"
        
        # Ensure directories exist
        for d in [self.pending_dir, self.completed_dir, self.failed_dir]:
            d.mkdir(parents=True, exist_ok=True)
            
    def process_existing_files(self):
        """Process files that are already in the pending directory before monitoring started."""
        for file_path in self.pending_dir.glob("*.json"):
            self._handle_file(file_path)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            # Small delay to ensure the file is fully written by Syncthing/Synology Drive
            time.sleep(1.0)
            self._handle_file(Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            self._handle_file(Path(event.src_path))

    def _handle_file(self, file_path: Path):
        if file_path.parent != self.pending_dir or not file_path.name.endswith('.json'):
            return

        processing_path = file_path.with_suffix('.processing')
        
        # ATOMIC LOCK: Try to rename the file. If another MCP worker did this first,
        # this will raise FileNotFoundError, preventing duplicate execution.
        try:
            file_path.rename(processing_path)
        except (FileNotFoundError, FileExistsError, OSError):
            # Another process already grabbed this job or it's gone
            return

        try:
            with open(processing_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            job = QueueJob(**data)
            
            # Skip if not pending (safety check)
            if job.status != JobStatus.PENDING:
                return

            logger.info(f"Processing zotero queue job {job.id}: {job.action}")
            job.status = JobStatus.PROCESSING
            self._write_job(processing_path, job)
            
            # Execute the job
            self._execute_job(job)
            
            # Mark Success
            job.status = JobStatus.COMPLETED
            completed_path = self.completed_dir / file_path.name
            self._write_job(processing_path, job)
            processing_path.rename(completed_path)
            logger.info(f"Successfully processed job {job.id}")

        except Exception as e:
            logger.error(f"Failed to process job file {file_path.name}: {e}", exc_info=True)
            try:
                # Attempt to mark as failed
                with open(processing_path, "r+", encoding="utf-8") as f:
                    data = json.load(f)
                    job = QueueJob(**data)
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    
                failed_path = self.failed_dir / file_path.name
                self._write_job(processing_path, job)
                processing_path.rename(failed_path)
            except Exception as nested_e:
                logger.error(f"Could not construct/move failure payload: {nested_e}")

    def _write_job(self, path: Path, job: QueueJob):
        with open(path, "w", encoding="utf-8") as f:
            f.write(job.model_dump_json(indent=2))

    def _execute_job(self, job: QueueJob):
        # We need the MCP token to send instructions to the local Zotero
        token = resolve_zotero_mcp_token()
        if not token:
            raise ValueError("ZOTERO_MCP_TOKEN not found in environment")
            
        with PluginClient(auth_token=token) as client:
            if job.action == "create_memory":
                # Ensure the tool is available
                from zotero2ai.zotero.memory import MemoryManager
                from zotero2ai.zotero.models import MemoryItem
                
                mm = MemoryManager(client)
                payload = job.payload
                project = payload.get("project", "")
                mem_class = payload.get("mem_class", "unit")
                role = payload.get("role", "observation")
                title_label = payload.get("title_label", "")
                content = payload.get("content", "")
                
                cols = mm.ensure_collections(project_slug=project)
                
                mem_id = MemoryItem.generate_mem_id(project)
                full_title = f"[MEM][{mem_class}][{project}] {title_label}"

                m_item = MemoryItem(
                    mem_id=mem_id, 
                    mem_class=mem_class, 
                    role=role, 
                    project=project, 
                    title=full_title, 
                    content=content, 
                    source="mobile_agent", 
                    confidence="medium", 
                    tags=[]
                )

                mm.create_memory_item(m_item, cols["project"])
            else:
                raise ValueError(f"Unknown action: {job.action}")


def start_queue_worker_in_background(watch_dir_path: str):
    """Starts the Watchdog observer in a daemon background thread."""
    watch_dir = Path(watch_dir_path)
    if not watch_dir.exists():
        logger.warning(f"ZOTERO_QUEUE_WATCH_DIR {watch_dir} does not exist. Queue worker will not start.")
        return

    logger.info(f"Starting async queue worker thread on {watch_dir}...")
    handler = QueueJobHandler(watch_dir)
    
    # Process already pending files before starting the watch
    handler.process_existing_files()

    observer = Observer()
    observer.schedule(handler, str(handler.pending_dir), recursive=False)
    observer.start()

    # The observer runs in its own thread, but as long as the parent is alive.
    # We should return it or keep a reference so it doesn't get garbage collected, 
    # but Observer() internally manages a daemon thread.
    return observer
