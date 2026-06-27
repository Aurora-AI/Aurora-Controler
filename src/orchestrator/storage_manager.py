import json
import os
from pathlib import Path
from pydantic import BaseModel

class StorageManager:
    """Gerencia a persistência de artefatos por job_id (decoupled I/O)."""
    def __init__(self, job_id: str, output_base_dir: str | Path | None = None):
        if output_base_dir is None:
            output_base_dir = os.getenv("EXRS_DATA_DIR", "output")
        self.job_id = job_id
        # Cria a pasta do job: output/{job_id}
        self.output_dir = Path(output_base_dir) / job_id
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_artifact(self, stem: str, phase: str, model: BaseModel | dict) -> Path:
        """
        Salva um modelo Pydantic ou dicionário em output/{job_id}/{stem}_{phase}.json.
        """
        file_path = self.output_dir / f"{stem}_{phase}.json"
        
        if isinstance(model, BaseModel):
            content = model.model_dump_json(indent=2)
        else:
            content = json.dumps(model, indent=2, ensure_ascii=False)
            
        file_path.write_text(content, encoding="utf-8")
        return file_path
