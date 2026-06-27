import pytest
from pathlib import Path
from src.phase_a4.runner import execute_in_sandbox, _docker_available

# Os testes do sandbox exigem o engine Docker real (isolamento de SO, não whitelist).
# Pular explicitamente — sem mascarar — quando o engine não estiver disponível.
pytestmark = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker engine indisponível — sandbox de container não verificável (FACTORY_TOOL_UNAVAILABLE)",
)


def test_sandbox_normal_execution():
    code = """
def my_func(a, b):
    return a + b
"""
    result = execute_in_sandbox(code, "my_func", {"a": 10, "b": 20})
    assert result == 30


def test_sandbox_timeout():
    code = """
def infinite_loop():
    while True:
        pass
"""
    result = execute_in_sandbox(code, "infinite_loop", {}, timeout_sec=5)
    assert isinstance(result, str)
    assert "TimeoutError" in result


def test_sandbox_whitelist_failure():
    code = """
def malicious():
    import os
    return os.name
"""
    result = execute_in_sandbox(code, "malicious", {})
    assert isinstance(result, str)
    assert "RUNTIME_ERROR" in result
    assert "error" in result.lower() or "failed" in result.lower()


def test_sandbox_math_available():
    code = """
def compute():
    return math.sqrt(16)
"""
    result = execute_in_sandbox(code, "compute", {})
    assert result == 4.0


def test_sandbox_container_filesystem_isolation():
    """
    Mesmo que o código gerado ESCAPE do exec restrito (travessia de subclasses → __import__),
    o container --read-only --network none --user nobody não tem FS de host gravável.
    O escape pode até alcançar `os`, mas não pode tocar o host. Provamos a contenção real.
    """
    sentinel = Path("exrs_breach_marker.txt")
    if sentinel.exists():
        sentinel.unlink()

    code = (
        "def breach():\n"
        "    for c in ().__class__.__base__.__subclasses__():\n"
        "        try:\n"
        "            bi = c.__init__.__globals__['__builtins__']\n"
        "            imp = bi['__import__']\n"
        "            o = imp('os')\n"
        "            # tentar escrever no rootfs (read-only) e no cwd do host (não montado)\n"
        "            bi['open']('/exrs_breach_marker.txt', 'w').write('breach')\n"
        "            return 'WROTE ' + str(o.getcwd())\n"
        "        except:\n"
        "            continue\n"
        "    return 'CONTAINED'\n"
    )
    execute_in_sandbox(code, "breach", {})

    # Critério de contenção: o host permanece intacto, independente do resultado interno.
    assert not sentinel.exists(), "VAZAMENTO: o sandbox escreveu no filesystem do host!"


def test_sandbox_unavailable_never_falls_back_to_local(monkeypatch):
    """Se o Docker sumir, o sandbox falha explícito — nunca executa código localmente."""
    monkeypatch.setattr("src.phase_a4.runner._docker_available", lambda: False)
    result = execute_in_sandbox("def f():\n    return 1\n", "f", {})
    assert isinstance(result, str)
    assert "SANDBOX_UNAVAILABLE" in result
