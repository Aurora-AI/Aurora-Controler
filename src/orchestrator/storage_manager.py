import json
import os
import re
from pathlib import Path
from pydantic import BaseModel

_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class StorageManager:
    """Gerencia a persistência de artefatos confinados por tenant_id e job_id (decoupled I/O)."""
    def __init__(
        self,
        job_id: str,
        output_base_dir: str | Path | None = None,
        tenant_id: str | None = None,
    ):
        if output_base_dir is None:
            output_base_dir = os.getenv("EXRS_DATA_DIR", "output")

        if not _ID_PATTERN.match(job_id):
            raise ValueError(f"Identificador de job_id inválido ou tentativa de traversal: {job_id}")
        if tenant_id is not None and tenant_id != "default":
            if not _ID_PATTERN.match(tenant_id):
                raise ValueError(f"Identificador de tenant_id inválido ou tentativa de traversal: {tenant_id}")

        self.job_id = job_id
        self.tenant_id = tenant_id

        resolved_base = Path(output_base_dir).resolve()
        if tenant_id and tenant_id != "default":
            target_dir = (resolved_base / tenant_id / job_id).resolve()
        else:
            target_dir = (resolved_base / job_id).resolve()

        # Validação estrita de confinamento (Anti-Path Traversal)
        if not target_dir.is_relative_to(resolved_base):
            raise ValueError(f"Caminho não confinado à base de saída autorizada: {target_dir}")

        self.output_dir = target_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)


    def write_artifact(self, stem: str, phase: str, model: BaseModel | dict) -> Path:
        """
        Salva um modelo Pydantic ou dicionário em output/{tenant_id}/{job_id}/{stem}_{phase}.json.
        """
        file_path = self.output_dir / f"{stem}_{phase}.json"

        if isinstance(model, BaseModel):
            content = model.model_dump_json(indent=2)
        else:
            content = json.dumps(model, indent=2, ensure_ascii=False)

        file_path.write_text(content, encoding="utf-8")
        return file_path
