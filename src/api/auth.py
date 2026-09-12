"""
EXRS API — Autenticação e Autorização Multitenant (OWASP Multi-Tenant).
Valida credenciais (tokens internos) e vincula a requisição estritamente
aos tenants autorizados, impedindo ataques de impersonação (HTTP 403)
e path traversal em identificadores.
"""
import os
import re
import json
from fastapi import Header, HTTPException, Depends

TENANT_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

def get_token_registry() -> dict[str, dict]:
    raw_env = os.getenv("EXRS_API_TOKENS")
    if not raw_env:
        return {}
    try:
        data = json.loads(raw_env)
        if not isinstance(data, dict):
            raise HTTPException(
                status_code=500,
                detail="Configuração de autenticação EXRS_API_TOKENS deve ser um objeto JSON."
            )
        return data
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Configuração de autenticação EXRS_API_TOKENS corrompida: {exc}"
        )


def validate_identifier(value: str, name: str = "tenant_id") -> str:
    if not value or not TENANT_ID_REGEX.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"Identificador inválido para {name}. Permitido: [a-zA-Z0-9_-] até 64 caracteres."
        )
    return value


async def get_authenticated_tenant(
    authorization: str | None = Header(None),
    x_tenant_id: str | None = Header(None)
) -> str:
    """
    Dependency FastAPI que autentica a credencial e resolve o tenant autorizado.
    - Se credencial ausente: 401 Unauthorized (sem acesso anônimo).
    - Credencial inválida ou ausente no registro: 401 Unauthorized.
    - Credencial de B tentando acessar tenant A: 403 Forbidden (impersonação bloqueada).
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Credencial de autenticação obrigatória."
        )

    token = authorization
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    registry = get_token_registry()
    principal = registry.get(token)
    if not principal:
        raise HTTPException(status_code=401, detail="Credencial inválida ou expirada.")

    allowed_tenant = principal.get("tenant_id")
    if not allowed_tenant:
        raise HTTPException(status_code=401, detail="Credencial sem tenant associado.")

    # Validação contra impersonação
    if x_tenant_id and x_tenant_id != allowed_tenant:
        raise HTTPException(
            status_code=403,
            detail="Acesso negado: credencial não autorizada para o tenant solicitado."
        )

    return validate_identifier(allowed_tenant)


