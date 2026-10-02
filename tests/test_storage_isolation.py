import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# sys.path if statements removed

import pytest
from pydantic import BaseModel
from orchestrator.storage_manager import StorageManager

class DummyModel(BaseModel):
    val: str

def test_storage_isolation(tmp_path):
    """Garante que jobs paralelos não colidem arquivos."""
    s1 = StorageManager("job_A", output_base_dir=tmp_path)
    s2 = StorageManager("job_B", output_base_dir=tmp_path)
    
    s1.write_artifact("stem", "phase1", DummyModel(val="A"))
    s2.write_artifact("stem", "phase1", DummyModel(val="B"))
    
    a_path = tmp_path / "job_A" / "stem_phase1.json"
    b_path = tmp_path / "job_B" / "stem_phase1.json"
    
    assert a_path.exists()
    assert b_path.exists()
    assert "A" in a_path.read_text(encoding="utf-8")
    assert "B" in b_path.read_text(encoding="utf-8")
