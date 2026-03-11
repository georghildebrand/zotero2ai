"""
This script should be copied and pasted into a new "Tool" inside Open WebUI.
It gives the mobile LLM the ability to write JSON job files into the mapped Docker volume.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

# Important: This path must match the volume mapping in docker-compose.yml
QUEUE_DIR = Path("/app/backend/data/zotero_queue_sync/pending")

class Tools:
    def __init__(self):
        pass

    def create_memory_item(self, project: str, mem_class: str, role: str, title_label: str, content: str) -> str:
        """
        Save a structured observation, hypothesis, or result directly to the user's Zotero memory system.
        This writes a job asynchronously which the user's laptop will automatically pick up later.
        
        :param project: Project slug, e.g., 'zotero2ai' or 'centric-software'.
        :param mem_class: 'unit' or 'concept'. Use 'unit' for raw observations.
        :param role: 'observation', 'result', 'hypothesis', or 'question'.
        :param title_label: Short, descriptive label for the title.
        :param content: The full markdown content to be saved.
        """
        # Ensure the pending queue directory exists inside the container
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Generate a unique Job ID
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        
        job_payload = {
            "id": job_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "create_memory",
            "payload": {
                "project": project,
                "mem_class": mem_class,
                "role": role,
                "title_label": title_label,
                "content": content
            },
            "status": "pending"
        }
        
        # Write the JSON payload to the queue
        file_path = QUEUE_DIR / f"{job_id}.json"
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(job_payload, f, indent=2)
            
            return f"Successfully queued memory creation job ({job_id}) for project '{project}'. It will be processed when the user's main endpoint comes online."
            
        except Exception as e:
            return f"Error queuing job: {str(e)}"
