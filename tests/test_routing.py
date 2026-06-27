import pytest
from pathlib import Path
import sys

# Ensure libs/trustware is in path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "libs" / "trustware"))

from pipeline_contracts import WorkbookClass, CompileDecision
from src.orchestrator.pipeline_orchestrator import route

def test_route_escalate():
    assert route(WorkbookClass.UNSUPPORTED, CompileDecision.ESCALATE, Path("foo.xlsx")) == "escalate"
    assert route(WorkbookClass.SUPPORTED, CompileDecision.ESCALATE, Path("foo.xlsx")) == "escalate"

def test_route_track_c():
    assert route(WorkbookClass.SUPPORTED, CompileDecision.PROCEED, Path("foo.csv")) == "track_c"
    assert route(WorkbookClass.SUPPORTED, CompileDecision.PROCEED, Path("FOO.CSV")) == "track_c"

def test_route_track_a():
    assert route(WorkbookClass.SUPPORTED, CompileDecision.PROCEED, Path("foo.xlsx")) == "track_a"
    assert route(WorkbookClass.RESTRICTED, CompileDecision.PROCEED_WITH_RESTRICTIONS, Path("foo.xlsx")) == "track_a"
