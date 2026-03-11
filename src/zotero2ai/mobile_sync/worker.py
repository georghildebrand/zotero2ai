import os
import json
import time
import logging
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from zotero2ai.mobile_sync.schema import MobileSyncJob, JobStatus
from zotero2ai.config import resolve_zotero_mcp_token

# Only importing for type checking if needed, otherwise we will pass the server object
# but for now we'll just parse the json and invoke the MCP functions or PluginClient directly.
from zotero2ai.zotero.plugin_client import PluginClient

logger = logging.getLogger(__name__)

class MobileSyncJobHandler(FileSystemEventHandler):
    def __init__(self, watch_dir: Path):
        self.watch_dir = watch_dir
        self.pending_dir = watch_dir / "pending"
        self.completed_dir = watch_dir / "completed"
        self.failed_dir = watch_dir / "failed"
        
        # Ensure directories exist
        for d in [self.pending_dir, self.completed_dir, self.failed_dir, watch_dir / "ZoteroReadCache"]:
            d.mkdir(parents=True, exist_ok=True)
            
        self.last_export_time = 0
        self.export_interval = 300 # Export every 5 minutes if there are changes
            
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
            
            job = MobileSyncJob(**data)
            
            # Skip if not pending (safety check)
            if job.status != JobStatus.PENDING:
                return

            logger.info(f"Processing mobile sync job {job.id}: {job.action}")
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
                    job = MobileSyncJob(**data)
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    
                failed_path = self.failed_dir / file_path.name
                self._write_job(processing_path, job)
                processing_path.rename(failed_path)
            except Exception as nested_e:
                logger.error(f"Could not construct/move failure payload: {nested_e}")

    def _write_job(self, path: Path, job: MobileSyncJob):
        with open(path, "w", encoding="utf-8") as f:
            f.write(job.model_dump_json(indent=2))

    def _execute_job(self, job: MobileSyncJob):
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
                
                # Check for active project fallback if no specific project is given
                if not project or project.lower() == "default":
                    try:
                        cols = mm.ensure_collections()
                        settings = mm.get_settings(cols["system"])
                        active_slug = settings.get("active_project_slug")
                        if active_slug:
                            logger.info(f"Using active project fallback: {active_slug}")
                            project = active_slug
                    except Exception as e:
                        logger.warning(f"Could not resolve active project fallback: {e}")

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
                # Trigger an export after a new memory is created
                self.export_zotero_data()
            else:
                raise ValueError(f"Unknown action: {job.action}")

    def export_zotero_data(self):
        """Export recent Zotero items to a JSON file for the mobile search tool."""
        try:
            token = resolve_zotero_mcp_token()
            cache_file = self.watch_dir / "ZoteroReadCache" / "mobile_search_cache.json"
            
            logger.info("Updating mobile search cache...")
            with PluginClient(auth_token=token) as client:
                # Fetch recent items and notes
                items = client.get_recent_items(limit=100)
                
                # Format for the search tool
                export_data = []
                for item in items:
                    if "error" in item: continue
                    
                    export_data.append({
                        "id": item.get("key"),
                        "title": item.get("title", "Untitled"),
                        "type": item.get("itemType"),
                        "abstract": item.get("abstract", ""),
                        "note": item.get("note", ""), # For standalone notes
                        "tags": item.get("tags", []),
                        "date": item.get("dateAdded")
                    })
                
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, indent=2)
                
                self.last_export_time = time.time()
                logger.info(f"Exported {len(export_data)} items to {cache_file}")
                
        except Exception as e:
            logger.error(f"Failed to export search cache: {e}")


def start_mobile_sync_worker(watch_dir_path: str):
    """Starts the Watchdog observer in a daemon background thread."""
    watch_dir = Path(watch_dir_path)
    if not watch_dir.exists():
        logger.warning(f"ZOTERO2AI_MOBILE_SYNC_WATCH_DIR {watch_dir} does not exist. Worker will not start.")
        return

    logger.info(f"Starting async mobile sync worker thread on {watch_dir}...")
    handler = MobileSyncJobHandler(watch_dir)
    
    # Process already pending files before starting the watch
    handler.process_existing_files()

    observer = Observer()
    observer.schedule(handler, str(handler.pending_dir), recursive=False)
    observer.start()

    # The observer runs in its own thread, but as long as the parent is alive.
    # We should return it or keep a reference so it doesn't get garbage collected, 
    # but Observer() internally manages a daemon thread.
    return observer
