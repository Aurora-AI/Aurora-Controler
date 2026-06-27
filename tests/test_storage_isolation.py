import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "src" / "orchestrator") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src" / "orchestrator"))

import pytest
from pydantic import BaseModel
from storage_manager import StorageManager

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
